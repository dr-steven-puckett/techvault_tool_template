#!/usr/bin/env python3
"""
techvault-tool-fleet
~~~~~~~~~~~~~~~~~~~~
Fleet runner: executes stamp-related steps across all tools listed in a
catalog file (tools/tools.catalog.json).

CLI contract:
    techvault-tool-fleet [--catalog PATH] [--manifest PATH] [--strict]
                         [--steps STEPS]

Exit codes:
    0  all steps OK
    1  at least one WARN, no errors
    2  at least one ERROR (catalog failure, step failure, or per-tool error)
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Bootstrap: ensure tools/ is on sys.path so tool_common is importable
# whether run directly, via the shell-script shim, or via pytest.
# ---------------------------------------------------------------------------
_TOOL_DIR = Path(__file__).resolve().parent      # tools/tool_fleet_manager/
_TOOLS_DIR = _TOOL_DIR.parent                    # tools/
_WORKSPACE_ROOT = _TOOLS_DIR.parent              # repository root

for _p in (str(_TOOLS_DIR), str(_TOOL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tool_common.report import canonical_json  # type: ignore  # noqa: E402

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

_DEFAULT_CATALOG: Path = _TOOLS_DIR / "tools.catalog.json"
_DEFAULT_MANIFEST: Path = _TOOLS_DIR / "tool_template" / "TEMPLATE_MANIFEST.json"

# ---------------------------------------------------------------------------
# Catalog validation exception
# ---------------------------------------------------------------------------


class CatalogError(Exception):
    """Raised by read_catalog when the catalog fails schema/rules validation."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        # Sort keys for deterministic serialization of error details.
        self.details: dict = dict(sorted((details or {}).items()))


# ---------------------------------------------------------------------------
# read_catalog
# ---------------------------------------------------------------------------


def read_catalog(catalog_path: str | Path) -> dict:
    """
    Read and validate tools.catalog.json.

    Returns the parsed catalog dict on success.

    Raises
    ------
    CatalogError        if the catalog fails schema or ordering validation.
    FileNotFoundError   if the file does not exist.
    json.JSONDecodeError if the file is not valid JSON.
    """
    catalog_path = Path(catalog_path)
    raw = catalog_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    if not isinstance(data, dict):
        raise CatalogError("CATALOG_INVALID", "catalog root must be a JSON object")

    if data.get("version") != 1:
        raise CatalogError(
            "CATALOG_VERSION_UNKNOWN",
            f"catalog 'version' must be 1, got {data.get('version')!r}",
        )

    tools = data.get("tools")
    if not isinstance(tools, list):
        raise CatalogError("CATALOG_INVALID", "'tools' must be a JSON array")

    ids_seen: set[str] = set()
    for i, entry in enumerate(tools):
        if not isinstance(entry, dict):
            raise CatalogError(
                "CATALOG_INVALID",
                f"tools[{i}] must be a JSON object",
                {"index": i},
            )
        entry_keys = set(entry.keys())
        if entry_keys != {"id", "path"}:
            extra = sorted(entry_keys - {"id", "path"})
            missing = sorted({"id", "path"} - entry_keys)
            raise CatalogError(
                "CATALOG_INVALID",
                f"tools[{i}] must have exactly 'id' and 'path' keys",
                {"extra_keys": extra, "index": i, "missing_keys": missing},
            )
        path_val: str = entry["path"]
        if not path_val.startswith("tools/"):
            raise CatalogError(
                "CATALOG_INVALID",
                f"tools[{i}]['path'] must start with 'tools/', got {path_val!r}",
                {"index": i, "path": path_val},
            )
        tid: str = entry["id"]
        if tid in ids_seen:
            raise CatalogError(
                "CATALOG_DUPLICATE_ID",
                f"duplicate tool id {tid!r} at index {i}",
                {"duplicate_id": tid, "index": i},
            )
        ids_seen.add(tid)

    # Sort check: must be after the per-entry loop so we know every entry has "id".
    ids_list: list[str] = [e["id"] for e in tools]
    if ids_list != sorted(ids_list):
        raise CatalogError(
            "CATALOG_UNSORTED",
            "tools list must be sorted ascending by 'id'",
            {"actual_order": ids_list, "expected_order": sorted(ids_list)},
        )

    return data


# ---------------------------------------------------------------------------
# Step runners (module-level for monkeypatching in tests)
# ---------------------------------------------------------------------------


def _step_template_check(
    tool_path: Path,
    manifest_path: Path,
    strict: bool,
) -> tuple[dict, int]:
    """
    Run the template-check step via the importable checker API.
    Monkeypatch target for tests.
    """
    checker_py = _TOOLS_DIR / "tool_template_check" / "checker.py"
    g = runpy.run_path(str(checker_py))
    return g["run_check"](tool_path, manifest_path, strict)  # type: ignore[return-value]


def _step_template_version_check(
    tool_path: Path,
    manifest_path: Path,
    strict: bool,  # kept for uniform dispatch signature; versioner run_check ignores it
) -> tuple[dict, int]:
    """
    Run the template-version-check step via the importable versioner API.
    Monkeypatch target for tests.
    """
    versioner_py = _TOOLS_DIR / "tool_template_version" / "versioner.py"
    g = runpy.run_path(str(versioner_py))
    return g["run_check"](tool_path, manifest_path)  # type: ignore[return-value]


def _dispatch_step(
    step: str,
    tool_path: Path,
    manifest_path: Path,
    strict: bool,
) -> tuple[dict | None, int, dict | None]:
    """
    Dispatch a single step for a single tool.

    Returns ``(report_dict_or_None, exit_code, error_dict_or_None)``.
    Never raises.
    """
    try:
        if step == "template-check":
            report, code = _step_template_check(tool_path, manifest_path, strict)
        elif step == "template-version-check":
            report, code = _step_template_version_check(tool_path, manifest_path, strict)
        else:
            return (
                None,
                2,
                {
                    "details": {"step": step},
                    "message": f"Unknown step: {step!r}",
                    "type": "ValueError",
                },
            )
        return report, code, None
    except Exception as exc:  # noqa: BLE001
        return (
            None,
            2,
            {
                "details": {"exception_type": type(exc).__name__},
                "message": str(exc),
                "type": type(exc).__name__,
            },
        )


# ---------------------------------------------------------------------------
# run_fleet — importable entrypoint
# ---------------------------------------------------------------------------


def run_fleet(
    *,
    catalog_path: str | Path,
    manifest_path: str | Path | None = None,
    strict: bool = False,
    steps: list[str],
) -> tuple[dict, int]:
    """
    Run fleet steps across all tools listed in the catalog.

    Parameters
    ----------
    catalog_path  : path to tools.catalog.json
    manifest_path : path to TEMPLATE_MANIFEST.json (None → workspace canonical)
    strict        : pass --strict to steps that support it
    steps         : list of step names to run per tool

    Returns
    -------
    (report_dict, fleet_exit_code)
    """
    catalog_path = Path(catalog_path)
    resolved_manifest = (
        Path(manifest_path) if manifest_path is not None else _DEFAULT_MANIFEST
    )

    # Normalize steps once so both the report header and execution order match.
    normalized_steps: list[str] = sorted(steps)

    # Report header (common to all outcomes).
    base: dict = {
        "catalog_path": str(catalog_path),
        "manifest_path": str(resolved_manifest),
        "steps": normalized_steps,
        "strict": strict,
    }

    # -- Load and validate catalog -------------------------------------------
    try:
        catalog = read_catalog(catalog_path)
    except CatalogError as exc:
        return (
            {
                **base,
                "catalog_error": {
                    "code": exc.code,
                    "details": exc.details,
                    "message": str(exc),
                },
                "results": [],
                "summary": {
                    "error": 0,
                    "ok": 0,
                    "total_steps": len(normalized_steps),
                    "total_tools": 0,
                    "warn": 0,
                },
            },
            2,
        )
    except Exception as exc:  # noqa: BLE001
        return (
            {
                **base,
                "catalog_error": {
                    "code": "CATALOG_READ_ERROR",
                    "details": {"exception_type": type(exc).__name__},
                    "message": f"{type(exc).__name__}: {exc}",
                },
                "results": [],
                "summary": {
                    "error": 0,
                    "ok": 0,
                    "total_steps": len(normalized_steps),
                    "total_tools": 0,
                    "warn": 0,
                },
            },
            2,
        )

    tools: list[dict] = catalog["tools"]  # sorted by id (validated by read_catalog)
    sorted_steps = normalized_steps

    results: list[dict] = []

    for entry in tools:
        tool_id: str = entry["id"]
        tool_rel_path: str = entry["path"]
        tool_abs_path: Path = _WORKSPACE_ROOT / tool_rel_path

        # Validate tool directory exists.
        if not tool_abs_path.is_dir():
            for step in sorted_steps:
                results.append(
                    {
                        "error": {
                            "details": {"expected_path": str(tool_abs_path)},
                            "message": f"Tool directory not found: {tool_abs_path}",
                            "type": "FileNotFoundError",
                        },
                        "exit_code": 2,
                        "report": None,
                        "step": step,
                        "tool_id": tool_id,
                        "tool_path": str(tool_abs_path),
                    }
                )
            continue

        # Validate tool.toml exists.
        if not (tool_abs_path / "tool.toml").is_file():
            for step in sorted_steps:
                results.append(
                    {
                        "error": {
                            "details": {
                                "expected_path": str(tool_abs_path / "tool.toml")
                            },
                            "message": f"tool.toml not found in: {tool_abs_path}",
                            "type": "FileNotFoundError",
                        },
                        "exit_code": 2,
                        "report": None,
                        "step": step,
                        "tool_id": tool_id,
                        "tool_path": str(tool_abs_path),
                    }
                )
            continue

        # Dispatch each step.
        for step in sorted_steps:
            report_dict, exit_code, error = _dispatch_step(
                step, tool_abs_path, resolved_manifest, strict
            )
            results.append(
                {
                    "error": error,
                    "exit_code": exit_code,
                    "report": report_dict,
                    "step": step,
                    "tool_id": tool_id,
                    "tool_path": str(tool_abs_path),
                }
            )

    # Final sort guarantee: (tool_id, step) ascending.
    results = sorted(results, key=lambda r: (r["tool_id"], r["step"]))

    # Summary counts.
    ok: int = sum(1 for r in results if r["exit_code"] == 0)
    warn: int = sum(1 for r in results if r["exit_code"] == 1)
    error_count: int = sum(1 for r in results if r["exit_code"] not in (0, 1))

    fleet_report: dict = {
        **base,
        "results": results,
        "summary": {
            "error": error_count,
            "ok": ok,
            "total_steps": len(steps),
            "total_tools": len(tools),
            "warn": warn,
        },
    }

    # Fleet exit code.
    if error_count > 0:
        fleet_code = 2
    elif warn > 0:
        fleet_code = 1
    else:
        fleet_code = 0

    return fleet_report, fleet_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-fleet",
        description=(
            "Run stamp-checking steps across all tools listed in a catalog."
        ),
    )
    parser.add_argument(
        "--catalog",
        default=None,
        metavar="PATH",
        help=(
            "Path to tools.catalog.json. "
            "Default: tools/tools.catalog.json in the workspace."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help=(
            "Path to TEMPLATE_MANIFEST.json. "
            "Default: tools/tool_template/TEMPLATE_MANIFEST.json in the workspace."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Pass --strict to steps that support it (exit 2 on any finding).",
    )
    parser.add_argument(
        "--steps",
        default="template-check",
        metavar="STEPS",
        help=(
            "Comma-separated list of steps to run per tool. "
            "Default: template-check. "
            "Supported: template-check, template-version-check."
        ),
    )
    args = parser.parse_args(argv)

    catalog_p = (
        Path(args.catalog).resolve() if args.catalog else _DEFAULT_CATALOG
    )
    manifest_p: Path | None = (
        Path(args.manifest).resolve() if args.manifest else None
    )
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]

    report, code = run_fleet(
        catalog_path=catalog_p,
        manifest_path=manifest_p,
        strict=args.strict,
        steps=steps,
    )
    print(canonical_json(report), end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
