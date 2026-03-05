#!/usr/bin/env python3
"""
techvault-tool-template-check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates the [template] stamp in a TechVault tool's tool.toml against a
TEMPLATE_MANIFEST.json.

CLI contract (docs/TOOL_TOML_SPEC.md §10.1):
    techvault-tool-template-check <tool_path> [--manifest <path>] [--strict]

Exit codes:
    0  no findings
    1  WARN findings only (non-strict)
    2  ERROR findings present, or any finding when --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: ensure tools/ is on sys.path so tool_common is importable whether
# this file is run directly, via the shell-script shim, or via pytest.
# ---------------------------------------------------------------------------
_TOOL_DIR = Path(__file__).resolve().parent          # tools/tool_template_check/
_TOOLS_DIR = _TOOL_DIR.parent                         # tools/
for _p in (str(_TOOLS_DIR), str(_TOOL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tool_common.stamp import (  # noqa: E402  # type: ignore
    StampValidationError,
    compute_manifest_sha256,
    read_tool_toml,
    validate_stamp,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Workspace-canonical manifest path (default when --manifest is not given).
_DEFAULT_MANIFEST: Path = _TOOLS_DIR / "tool_template" / "TEMPLATE_MANIFEST.json"

#: Sort-order for finding levels (lower = higher priority).
_LEVEL_SEV: dict[str, int] = {"ERROR": 0, "WARN": 1}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    level: str,
    code: str,
    message: str,
    path: str,
    details: dict | None = None,
) -> dict:
    """Build a finding dict with required keys in stable order."""
    f: dict = {"code": code, "level": level, "message": message, "path": path}
    if details is not None:
        f["details"] = details
    return f


def _sort_findings(findings: list[dict]) -> list[dict]:
    """Sort findings: ERROR before WARN, then by code, then by path (§7.6)."""
    return sorted(
        findings,
        key=lambda f: (
            _LEVEL_SEV.get(f.get("level", "WARN"), 99),
            f.get("code", ""),
            f.get("path", ""),
        ),
    )


def _canonical_json(obj: object) -> str:
    """Return canonical JSON string (sort_keys, compact, single trailing newline)."""
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    )


def _exit_code(findings: list[dict], strict: bool) -> int:
    """Derive exit code from findings list (§7.1)."""
    if not findings:
        return 0
    if strict:
        return 2
    if any(f.get("level") == "ERROR" for f in findings):
        return 2
    return 1


# ---------------------------------------------------------------------------
# Core check logic (importable for tests)
# ---------------------------------------------------------------------------


def run_check(tool_path: Path, manifest_path: Path, strict: bool) -> tuple[dict, int]:
    """
    Run a full template stamp check.

    Returns (report_dict, exit_code).  Never raises; all errors are captured
    into findings.
    """
    findings: list[dict] = []
    computed_hash: str | None = None
    template_section: dict | None = None
    tool_toml_path = tool_path / "tool.toml"

    # --- Pre-read tool.toml for template section (report preview) ------------
    if tool_toml_path.is_file():
        try:
            template_section = read_tool_toml(tool_toml_path).get("template")
        except Exception:
            pass  # validate_stamp will produce the canonical TOML_INVALID finding

    # --- Compute manifest hash (for the report) ------------------------------
    if manifest_path.is_file():
        try:
            computed_hash = compute_manifest_sha256(manifest_path)
        except Exception:
            pass  # validate_stamp will produce the canonical MANIFEST_MISSING finding

    # --- Run stamp validation ------------------------------------------------
    try:
        stamp_findings = validate_stamp(
            tool_toml_path, manifest_path, strict=False
        )
        findings.extend(stamp_findings)
    except StampValidationError as exc:
        findings.extend(exc.findings)
    except Exception as exc:
        findings.append(
            _make_finding(
                "ERROR",
                "UNHANDLED_EXCEPTION",
                f"Unexpected error during stamp validation: {type(exc).__name__}: {exc}",
                str(tool_toml_path),
                {"exception_message": str(exc), "exception_type": type(exc).__name__},
            )
        )

    # --- Check for local TEMPLATE_MANIFEST.json (audit record) ---------------
    if tool_path.is_dir():
        local_manifest = tool_path / "TEMPLATE_MANIFEST.json"
        if not local_manifest.is_file():
            findings.append(
                _make_finding(
                    "WARN",
                    "LOCAL_MANIFEST_MISSING",
                    (
                        "TEMPLATE_MANIFEST.json is absent from the tool repo root. "
                        "Run techvault-tool-template-version --write to create it."
                    ),
                    str(local_manifest),
                )
            )

    findings = _sort_findings(findings)

    report: dict = {
        "computed_manifest_hash": computed_hash,
        "expected_manifest_hash": computed_hash,
        "findings": findings,
        "manifest_path": str(manifest_path),
        "strict": strict,
        "template": template_section,
        "tool_path": str(tool_path),
    }
    return report, _exit_code(findings, strict)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="techvault-tool-template-check",
        description="Validate the [template] stamp in a TechVault tool's tool.toml.",
    )
    p.add_argument(
        "tool_path",
        help="Path to the tool repo directory (must contain tool.toml).",
    )
    p.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help=(
            "Path to TEMPLATE_MANIFEST.json. "
            "Default: tools/tool_template/TEMPLATE_MANIFEST.json in the workspace."
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 2 if any finding exists (treats WARN as ERROR for exit code).",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    tool_path = Path(args.tool_path).resolve()
    manifest_path = (
        Path(args.manifest).resolve() if args.manifest else _DEFAULT_MANIFEST
    )

    try:
        report, code = run_check(tool_path, manifest_path, args.strict)
    except Exception as exc:  # noqa: BLE001
        report = {
            "computed_manifest_hash": None,
            "expected_manifest_hash": None,
            "findings": [
                _make_finding(
                    "ERROR",
                    "UNHANDLED_EXCEPTION",
                    f"Unexpected top-level error: {type(exc).__name__}: {exc}",
                    str(tool_path),
                    {
                        "exception_message": str(exc),
                        "exception_type": type(exc).__name__,
                    },
                )
            ],
            "manifest_path": str(manifest_path),
            "strict": args.strict,
            "template": None,
            "tool_path": str(tool_path),
        }
        code = 2

    print(_canonical_json(report), end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
