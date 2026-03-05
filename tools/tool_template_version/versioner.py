#!/usr/bin/env python3
"""
techvault-tool-template-version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reads or repairs the [template] stamp in a TechVault tool's tool.toml.

CLI contract (docs/TOOL_TOML_SPEC.md §10.2):
    techvault-tool-template-version <tool_path> (--check | --write) [--manifest <path>]

Exit codes:
    0  no findings
    1  WARN findings only
    2  ERROR findings present
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
_TOOL_DIR = Path(__file__).resolve().parent          # tools/tool_template_version/
_TOOLS_DIR = _TOOL_DIR.parent                         # tools/
for _p in (str(_TOOLS_DIR), str(_TOOL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tool_common.stamp import StampValidationError, compute_manifest_sha256, read_tool_toml, validate_stamp, write_stamp  # type: ignore  # noqa: E402
from tool_common.report import canonical_json  # type: ignore  # noqa: E402

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
    f: dict = {"code": code, "level": level, "message": message, "path": path}
    if details is not None:
        f["details"] = details
    return f


def _sort_findings(findings: list[dict]) -> list[dict]:
    return sorted(
        findings,
        key=lambda f: (
            _LEVEL_SEV.get(f.get("level", "WARN"), 99),
            f.get("code", ""),
            f.get("path", ""),
        ),
    )


def _exit_code(findings: list[dict]) -> int:
    if not findings:
        return 0
    if any(f.get("level") == "ERROR" for f in findings):
        return 2
    return 1


def _run_validate(tool_toml_path: Path, manifest_path: Path) -> list[dict]:
    """Run validate_stamp and always return findings (never raise)."""
    try:
        return validate_stamp(tool_toml_path, manifest_path, strict=False)
    except StampValidationError as exc:
        return exc.findings
    except Exception as exc:
        return [
            _make_finding(
                "ERROR",
                "UNHANDLED_EXCEPTION",
                f"Unexpected error: {type(exc).__name__}: {exc}",
                str(tool_toml_path),
                {"exception_message": str(exc), "exception_type": type(exc).__name__},
            )
        ]


# ---------------------------------------------------------------------------
# Mode: --check
# ---------------------------------------------------------------------------


def run_check(tool_path: Path, manifest_path: Path) -> tuple[dict, int]:
    """Validate the stamp and return (report_dict, exit_code). Never raises."""
    tool_toml_path = tool_path / "tool.toml"
    computed_hash: str | None = None
    template_section: dict | None = None

    if manifest_path.is_file():
        try:
            computed_hash = compute_manifest_sha256(manifest_path)
        except Exception:
            pass

    if tool_toml_path.is_file():
        try:
            template_section = read_tool_toml(tool_toml_path).get("template")
        except Exception:
            pass

    findings = _sort_findings(_run_validate(tool_toml_path, manifest_path))

    report: dict = {
        "computed_manifest_hash": computed_hash,
        "expected_manifest_hash": computed_hash,
        "findings": findings,
        "manifest_path": str(manifest_path),
        "mode": "check",
        "strict": False,
        "template": template_section,
        "tool_path": str(tool_path),
        "wrote_stamp": False,
    }
    return report, _exit_code(findings)


# ---------------------------------------------------------------------------
# Mode: --write
# ---------------------------------------------------------------------------


def run_write(tool_path: Path, manifest_path: Path) -> tuple[dict, int]:
    """Write (or overwrite) the stamp with stamp_source='manual'. Never raises."""
    tool_toml_path = tool_path / "tool.toml"
    findings: list[dict] = []
    wrote_stamp = False
    computed_hash: str | None = None
    template_section: dict | None = None

    # -- tool.toml must exist (write_stamp cannot create it from scratch) -----
    if not tool_toml_path.is_file():
        # Delegate to validate_stamp to produce the canonical TOML_MISSING finding
        findings = _sort_findings(_run_validate(tool_toml_path, manifest_path))
        report: dict = {
            "computed_manifest_hash": None,
            "expected_manifest_hash": None,
            "findings": findings,
            "manifest_path": str(manifest_path),
            "mode": "write",
            "strict": False,
            "template": None,
            "tool_path": str(tool_path),
            "wrote_stamp": False,
        }
        return report, _exit_code(findings)

    # -- Read and validate the manifest ---------------------------------------
    if not manifest_path.is_file():
        findings.append(
            _make_finding(
                "ERROR",
                "MANIFEST_MISSING",
                f"Cannot read manifest: file not found: {manifest_path}",
                str(manifest_path),
            )
        )
        findings = _sort_findings(findings)
        report = {
            "computed_manifest_hash": None,
            "expected_manifest_hash": None,
            "findings": findings,
            "manifest_path": str(manifest_path),
            "mode": "write",
            "strict": False,
            "template": None,
            "tool_path": str(tool_path),
            "wrote_stamp": False,
        }
        return report, _exit_code(findings)

    try:
        manifest_raw = manifest_path.read_bytes()
        manifest_data: dict = json.loads(manifest_raw.decode("utf-8", errors="strict"))
        computed_hash = compute_manifest_sha256(manifest_path)
    except Exception as exc:
        findings.append(
            _make_finding(
                "ERROR",
                "MANIFEST_MISSING",
                f"Cannot read manifest: {type(exc).__name__}: {exc}",
                str(manifest_path),
            )
        )
        findings = _sort_findings(findings)
        report = {
            "computed_manifest_hash": None,
            "expected_manifest_hash": None,
            "findings": findings,
            "manifest_path": str(manifest_path),
            "mode": "write",
            "strict": False,
            "template": None,
            "tool_path": str(tool_path),
            "wrote_stamp": False,
        }
        return report, _exit_code(findings)

    template_version = manifest_data.get("template_version")
    if not template_version:
        findings.append(
            _make_finding(
                "ERROR",
                "MANIFEST_INVALID",
                "TEMPLATE_MANIFEST.json is missing the required 'template_version' field",
                str(manifest_path),
            )
        )
        findings = _sort_findings(findings)
        report = {
            "computed_manifest_hash": computed_hash,
            "expected_manifest_hash": computed_hash,
            "findings": findings,
            "manifest_path": str(manifest_path),
            "mode": "write",
            "strict": False,
            "template": None,
            "tool_path": str(tool_path),
            "wrote_stamp": False,
        }
        return report, _exit_code(findings)

    # -- Write the stamp -------------------------------------------------------
    try:
        write_stamp(
            tool_toml_path,
            template_version=template_version,
            template_manifest_hash=computed_hash,
            stamp_source="manual",
        )
        wrote_stamp = True
    except Exception as exc:
        findings.append(
            _make_finding(
                "ERROR",
                "UNHANDLED_EXCEPTION",
                f"Failed to write stamp: {type(exc).__name__}: {exc}",
                str(tool_toml_path),
                {"exception_message": str(exc), "exception_type": type(exc).__name__},
            )
        )

    # -- Post-write validation (always run, even if write failed) -------------
    post_findings = _run_validate(tool_toml_path, manifest_path)
    findings.extend(post_findings)

    # -- Read template section from the (possibly updated) tool.toml ----------
    if tool_toml_path.is_file():
        try:
            template_section = read_tool_toml(tool_toml_path).get("template")
        except Exception:
            pass

    findings = _sort_findings(findings)
    report = {
        "computed_manifest_hash": computed_hash,
        "expected_manifest_hash": computed_hash,
        "findings": findings,
        "manifest_path": str(manifest_path),
        "mode": "write",
        "strict": False,
        "template": template_section,
        "tool_path": str(tool_path),
        "wrote_stamp": wrote_stamp,
    }
    return report, _exit_code(findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="techvault-tool-template-version",
        description="Read or repair the [template] stamp in a TechVault tool's tool.toml.",
    )
    p.add_argument(
        "tool_path",
        help="Path to the tool repo directory (must contain tool.toml).",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Validate the stamp and report findings (read-only).",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Write (or overwrite) the stamp with stamp_source='manual'.",
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
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    tool_path = Path(args.tool_path).resolve()
    manifest_path = (
        Path(args.manifest).resolve() if args.manifest else _DEFAULT_MANIFEST
    )

    try:
        if args.check:
            report, code = run_check(tool_path, manifest_path)
        else:
            report, code = run_write(tool_path, manifest_path)
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
            "mode": "check" if args.check else "write",
            "strict": False,
            "template": None,
            "tool_path": str(tool_path),
            "wrote_stamp": False,
        }
        code = 2

    print(canonical_json(report), end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
