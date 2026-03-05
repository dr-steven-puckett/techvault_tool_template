#!/usr/bin/env python3
"""TechVault Tool Registration Manager — deterministic, idempotent tool registrar.

Registers a TechVault tool into:

    backend/techvault/app/api/__init__.py

Two auto-managed blocks are written (or updated in-place):

    # BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
    from <tool_id>.api.router import router as <tool_id>_router
    # END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)

    # BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
    api_router.include_router(
        <tool_id>_router,
        tags=["tools:<tool_id>"]
    )
    # END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)

Imports block is inserted after existing router imports; mounts block is
inserted before ``__all__ = ["api_router"]``.

All entries are sorted lexicographically by tool_id within each block.
Single-tool mode preserves other tools already registered in the blocks.
--all mode replaces both blocks with exactly the discovered set of tools.

Dry-run is the default; pass --apply to write.

Exit codes:
  0  success (dry-run complete, or changes applied successfully)
  1  validation / configuration error
  2  apply failure (compile error — reverted)
"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Block marker constants — CONTRACTUAL; must not change.
# ---------------------------------------------------------------------------

_IMP_BEGIN = "# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)"
_IMP_END   = "# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)"
_MNT_BEGIN = "# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)"
_MNT_END   = "# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)"

# Pattern that matches a managed import line:
#   from <tool_id>.api.router import router as <tool_id>_router
_IMPORT_LINE_RE = re.compile(
    r"^from (\w+)\.api\.router import router as \1_router$"
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ToolMeta:
    tool_id: str
    entrypoint: str


@dataclass
class ChangeSet:
    path: Path
    original: str
    updated: str

    @property
    def changed(self) -> bool:
        return self.original != self.updated

    def unified_diff(self) -> str:
        a = self.original.splitlines(keepends=True)
        b = self.updated.splitlines(keepends=True)
        diff = difflib.unified_diff(
            a, b,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            lineterm="",
        )
        return "".join(diff)


# ---------------------------------------------------------------------------
# Tool metadata loading
# ---------------------------------------------------------------------------


def load_tool_meta(
    tool_repo: Path,
    allow_mismatch: bool = False,
) -> ToolMeta:
    """Load and validate tool.toml from *tool_repo*."""
    toml_path = tool_repo / "tool.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"tool.toml not found: {toml_path}")

    with open(toml_path, "rb") as fh:
        data = tomllib.load(fh)

    tool_id = data.get("tool_id")
    entrypoint = data.get("entrypoint")

    if not tool_id:
        raise ValueError("tool.toml missing required field 'tool_id'")
    if not entrypoint:
        raise ValueError("tool.toml missing required field 'entrypoint'")
    if ":" not in entrypoint:
        raise ValueError(
            f"entrypoint must be '<module>:<symbol>', got: {entrypoint!r}"
        )

    folder_name = tool_repo.resolve().name
    if not allow_mismatch and folder_name != tool_id:
        raise ValueError(
            f"tool_id {tool_id!r} does not match folder name {folder_name!r}. "
            "Use --allow-mismatch to override."
        )

    return ToolMeta(tool_id=tool_id, entrypoint=entrypoint)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_API_INIT_CANDIDATES = [
    "backend/techvault/app/api/__init__.py",
    "techvault/app/api/__init__.py",
    "app/api/__init__.py",
]


def discover_api_init(
    techvault_root: Path,
    override: Path | None = None,
) -> Path:
    """Return the path to api/__init__.py, searching standard candidate locations."""
    if override is not None:
        if not override.exists():
            raise FileNotFoundError(f"--api-init override not found: {override}")
        return override

    for rel in _API_INIT_CANDIDATES:
        candidate = techvault_root / rel
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not find api/__init__.py under {techvault_root}. "
        f"Tried: {_API_INIT_CANDIDATES}"
    )


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------


def render_imports_block(tools: list[ToolMeta]) -> str:
    """Render the inner content of the IMPORTS block (no markers)."""
    lines = [
        f"from {t.tool_id}.api.router import router as {t.tool_id}_router"
        for t in sorted(tools, key=lambda t: t.tool_id)
    ]
    return "\n".join(lines)


def render_mounts_block(tools: list[ToolMeta]) -> str:
    """Render the inner content of the MOUNTS block (no markers)."""
    parts = [
        f"api_router.include_router(\n    {t.tool_id}_router,\n    tags=[\"tools:{t.tool_id}\"]\n)"
        for t in sorted(tools, key=lambda t: t.tool_id)
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Block extraction helpers
# ---------------------------------------------------------------------------


def _find_block(lines: list[str], begin: str, end: str) -> tuple[int, int]:
    """Return (start_idx, end_idx) of the block markers, or (-1, -1)."""
    si = ei = -1
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if stripped == begin:
            si = i
        elif stripped == end:
            ei = i
            break
    return si, ei


def _make_block_lines(begin: str, inner: str, end: str) -> list[str]:
    """Build a list of lines (each ending in \\n) for the full block."""
    result = [begin + "\n"]
    if inner:
        for l in inner.splitlines():
            result.append(l + "\n")
    result.append(end + "\n")
    return result


def _parse_tool_ids_from_imports_block(lines: list[str], si: int, ei: int) -> list[str]:
    """Extract tool_ids from lines between (exclusive) si and ei."""
    tool_ids: list[str] = []
    for line in lines[si + 1 : ei]:
        m = _IMPORT_LINE_RE.match(line.rstrip("\n"))
        if m:
            tool_ids.append(m.group(1))
    return tool_ids


# ---------------------------------------------------------------------------
# Content transformation
# ---------------------------------------------------------------------------


def update_api_init_content(
    content: str,
    new_tools: list[ToolMeta],
    replace_all: bool = False,
) -> str:
    """Return updated content with both managed blocks written.

    *new_tools* are the tools being registered in this invocation.
    If *replace_all* is True the blocks are replaced with exactly *new_tools*
    (used for ``--all`` mode).  Otherwise existing tool_ids in the current
    blocks are preserved and *new_tools* are merged in.
    """
    lines = content.splitlines(keepends=True)

    # ---- Determine merged tool set for imports block ----
    imp_si, imp_ei = _find_block(lines, _IMP_BEGIN, _IMP_END)
    if not replace_all and imp_si != -1 and imp_ei != -1:
        existing_ids = _parse_tool_ids_from_imports_block(lines, imp_si, imp_ei)
        merged_ids: dict[str, ToolMeta] = {t.tool_id: t for t in new_tools}
        for tid in existing_ids:
            if tid not in merged_ids:
                merged_ids[tid] = ToolMeta(tool_id=tid, entrypoint=f"{tid}.api.router:router")
        all_tools = list(merged_ids.values())
    else:
        all_tools = list(new_tools)

    imports_inner = render_imports_block(all_tools)
    mounts_inner = render_mounts_block(all_tools)

    # ---- Update or insert imports block ----
    imp_si, imp_ei = _find_block(lines, _IMP_BEGIN, _IMP_END)
    if imp_si != -1 and imp_ei != -1:
        new_block = _make_block_lines(_IMP_BEGIN, imports_inner, _IMP_END)
        lines = lines[: imp_si] + new_block + lines[imp_ei + 1 :]
    else:
        # Insert after the last import/from line
        last_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                last_import_idx = i
        insert_at = last_import_idx + 1
        new_block = _make_block_lines(_IMP_BEGIN, imports_inner, _IMP_END)
        lines = lines[:insert_at] + ["\n"] + new_block + lines[insert_at:]

    # ---- Update or insert mounts block ----
    # Re-search after the imports edit may have shifted line indices.
    mnt_si, mnt_ei = _find_block(lines, _MNT_BEGIN, _MNT_END)
    if mnt_si != -1 and mnt_ei != -1:
        new_block = _make_block_lines(_MNT_BEGIN, mounts_inner, _MNT_END)
        lines = lines[: mnt_si] + new_block + lines[mnt_ei + 1 :]
    else:
        # Insert before __all__ = ["api_router"]
        all_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("__all__"):
                all_idx = i
                break
        new_block = _make_block_lines(_MNT_BEGIN, mounts_inner, _MNT_END)
        if all_idx != -1:
            lines = lines[:all_idx] + new_block + ["\n"] + lines[all_idx:]
        else:
            # Fall back: append to end
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines = lines + ["\n"] + new_block

    return "".join(lines)


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def apply_changeset(cs: ChangeSet) -> None:
    """Write *cs.updated* to *cs.path* atomically; revert + raise on compile failure."""
    import py_compile  # stdlib

    # Write to a temp file in the same directory for atomic rename.
    dir_ = cs.path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(cs.updated)

        py_compile.compile(tmp_path, doraise=True)

        shutil.move(tmp_path, cs.path)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# --all discovery
# ---------------------------------------------------------------------------


def discover_all_tools(tools_dir: Path, allow_mismatch: bool = False) -> list[ToolMeta]:
    """Scan *tools_dir* for immediate subdirectories containing tool.toml."""
    found: list[ToolMeta] = []
    for child in sorted(tools_dir.iterdir()):
        if not child.is_dir():
            continue
        toml = child / "tool.toml"
        if not toml.exists():
            continue
        try:
            meta = load_tool_meta(child, allow_mismatch=allow_mismatch)
            found.append(meta)
        except (ValueError, FileNotFoundError):
            # Skip invalid entries silently in --all mode
            continue
    return found


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_changeset_report(cs: ChangeSet, verbose: bool) -> None:
    label = f"[WOULD CHANGE]" if cs.changed else "[NO CHANGE]"
    print(f"\n{label} {cs.path}")
    if cs.changed and verbose:
        print(cs.unified_diff())
    elif cs.changed:
        diff_lines = cs.unified_diff().splitlines()
        preview = "\n".join(diff_lines[:40])
        if len(diff_lines) > 40:
            preview += f"\n... ({len(diff_lines) - 40} more lines)"
        print(preview)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-register",
        description="Register TechVault tool(s) into backend/techvault/app/api/__init__.py.",
    )
    parser.add_argument(
        "tool_repo",
        nargs="?",
        metavar="TOOL_REPO",
        help="Path to tool repository (mutually exclusive with --all).",
    )
    parser.add_argument(
        "--all",
        dest="all_dir",
        metavar="TOOLS_DIR",
        help="Register all tool repos found under TOOLS_DIR.",
    )
    parser.add_argument(
        "--techvault-root",
        required=True,
        metavar="PATH",
        help="Root directory of the TechVault project.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write changes to disk (default: dry-run).",
    )
    parser.add_argument(
        "--enabled",
        choices=["true", "false"],
        help="Override enabled flag (not used in api/__init__.py blocks, accepted for compatibility).",
    )
    parser.add_argument(
        "--allow-mismatch",
        action="store_true",
        default=False,
        help="Allow tool_id to differ from the folder name.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full unified diff in dry-run output.",
    )
    parser.add_argument(
        "--api-init",
        metavar="PATH",
        help="Override path to api/__init__.py (for testing).",
    )

    args = parser.parse_args(argv)

    # ---- Mutual exclusion ----
    if args.tool_repo and args.all_dir:
        print(
            "error: TOOL_REPO and --all are mutually exclusive.",
            file=sys.stderr,
        )
        return 1
    if not args.tool_repo and not args.all_dir:
        print(
            "error: Provide either TOOL_REPO or --all TOOLS_DIR.",
            file=sys.stderr,
        )
        return 1

    techvault_root = Path(args.techvault_root)
    if not techvault_root.exists():
        print(
            f"error: --techvault-root does not exist: {techvault_root}",
            file=sys.stderr,
        )
        return 1

    # ---- Discover target file ----
    api_init_override = Path(args.api_init) if args.api_init else None
    try:
        api_init_path = discover_api_init(techvault_root, api_init_override)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # ---- Load tool metadata ----
    replace_all = bool(args.all_dir)
    try:
        if args.all_dir:
            tools_dir = Path(args.all_dir)
            if not tools_dir.exists():
                print(
                    f"error: --all TOOLS_DIR does not exist: {tools_dir}",
                    file=sys.stderr,
                )
                return 1
            tools = discover_all_tools(tools_dir, allow_mismatch=args.allow_mismatch)
            if not tools:
                print("warning: no valid tool repos found under --all directory.", file=sys.stderr)
        else:
            tool_repo = Path(args.tool_repo)
            tools = [load_tool_meta(tool_repo, allow_mismatch=args.allow_mismatch)]
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # ---- Compute changeset ----
    original = api_init_path.read_text(encoding="utf-8")
    updated = update_api_init_content(original, tools, replace_all=replace_all)
    cs = ChangeSet(path=api_init_path, original=original, updated=updated)

    # ---- Report ----
    if not args.apply:
        print("DRY-RUN — no files will be written (pass --apply to write)")
        print("=" * 72)
        _print_changeset_report(cs, verbose=args.verbose)
        print("\nRESULT: DRY-RUN COMPLETE (no files written)")
        return 0

    # ---- Apply ----
    if not cs.changed:
        print("RESULT: NO CHANGES (already up to date)")
        return 0

    try:
        apply_changeset(cs)
    except Exception as exc:  # py_compile.PyCompileError or OSError
        print(f"error: compile/write failed — changes NOT written: {exc}", file=sys.stderr)
        return 2

    print(f"APPLIED: {cs.path}")
    print("RESULT: CHANGES WRITTEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
