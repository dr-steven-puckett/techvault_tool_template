#!/usr/bin/env python3
"""TechVault Tool Sync — deterministic orchestrator for the tool lifecycle.

For each tool repo (single or --all), runs in fixed order:
  1) validate  — techvault-tool-validate
  2) tests     — pytest -q
  3) security  — techvault-tool-security-scan
  4) register  — techvault-tool-register  (dry-run unless --apply)

Exit codes:
  0  all steps passed (or skipped) for all tools
  1  one or more tools failed a step
  2  usage / configuration error (missing paths, bad arguments)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Sibling tool launcher paths (resolved relative to THIS file)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_TOOLS_ROOT = _HERE.parent   # tools/

_VALIDATOR_SCRIPT  = _TOOLS_ROOT / "tool_template_validator"   / "techvault-tool-validate"
_SECURITY_SCRIPT   = _TOOLS_ROOT / "tool_security_harness"     / "techvault-tool-security-scan"
_REGISTRAR_SCRIPT  = _TOOLS_ROOT / "tool_registration_manager" / "techvault-tool-register"

# Timeouts (seconds)
_SUBTOOL_TIMEOUT = 120
_PYTEST_TIMEOUT  = 600

# Max captured output kept in JSON report
_MAX_OUTPUT_CHARS = 20_000

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    status: str              # "pass" | "fail" | "skip" | "error"
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    mode: str | None = None  # "dry-run" | "apply"  (register step only)


@dataclass
class ToolReport:
    tool_id: str
    path: str
    # steps always in insertion order: validate, tests, security, register
    steps: dict[str, StepResult]


# ---------------------------------------------------------------------------
# Subprocess runner — extracted so tests can monkeypatch it
# ---------------------------------------------------------------------------


def _run_subprocess(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = _SUBTOOL_TIMEOUT,
) -> tuple[int, str, str]:
    """Run *cmd*; return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return -1, out, err + f"\n[TIMEOUT after {timeout}s]"
    except Exception as exc:
        return -1, "", f"[subprocess error] {exc}"


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


def _read_tool_id(tool_repo: Path) -> str:
    """Return tool_id from tool.toml, falling back to directory name."""
    toml_path = tool_repo / "tool.toml"
    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
        return data.get("tool_id") or tool_repo.name
    except Exception:
        return tool_repo.name


def discover_tools(tools_dir: Path) -> list[Path]:
    """Return immediate subdirectories that contain tool.toml, sorted by name."""
    return [
        child
        for child in sorted(tools_dir.iterdir())
        if child.is_dir() and (child / "tool.toml").exists()
    ]


# ---------------------------------------------------------------------------
# Individual step runners
# ---------------------------------------------------------------------------


def _step_skip(mode: str | None = None) -> StepResult:
    return StepResult(status="skip", exit_code=None, mode=mode)


def step_validate(tool_repo: Path) -> StepResult:
    code, out, err = _run_subprocess(
        [sys.executable, str(_VALIDATOR_SCRIPT), str(tool_repo)]
    )
    return StepResult(
        status="pass" if code == 0 else "fail",
        exit_code=code,
        stdout=out,
        stderr=err,
    )


def step_tests(tool_repo: Path) -> StepResult:
    code, out, err = _run_subprocess(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tool_repo,
        timeout=_PYTEST_TIMEOUT,
    )
    return StepResult(
        status="pass" if code == 0 else "fail",
        exit_code=code,
        stdout=out,
        stderr=err,
    )


def step_security(tool_repo: Path) -> StepResult:
    code, out, err = _run_subprocess(
        [sys.executable, str(_SECURITY_SCRIPT), str(tool_repo)]
    )
    return StepResult(
        status="pass" if code == 0 else "fail",
        exit_code=code,
        stdout=out,
        stderr=err,
    )


def step_register(
    tool_repo: Path,
    techvault_root: Path,
    apply: bool,
    enabled: str | None,
) -> StepResult:
    cmd = [
        sys.executable,
        str(_REGISTRAR_SCRIPT),
        str(tool_repo),
        "--techvault-root",
        str(techvault_root),
    ]
    if apply:
        cmd.append("--apply")
    if enabled:
        cmd.extend(["--enabled", enabled])
    code, out, err = _run_subprocess(cmd)
    return StepResult(
        status="pass" if code == 0 else "fail",
        exit_code=code,
        stdout=out,
        stderr=err,
        mode="apply" if apply else "dry-run",
    )


# ---------------------------------------------------------------------------
# Per-tool orchestration
# ---------------------------------------------------------------------------


def sync_one(
    tool_repo: Path,
    techvault_root: Path,
    *,
    apply: bool,
    enabled: str | None,
    skip_validate: bool,
    skip_tests: bool,
    skip_security: bool,
    skip_register: bool,
    fail_fast: bool,
    verbose: bool,
) -> ToolReport:
    tool_id = _read_tool_id(tool_repo)
    steps: dict[str, StepResult] = {}

    def _run_step(name: str, fn, skip: bool, **kw) -> StepResult:
        if skip:
            result = _step_skip(**kw)
        else:
            result = fn()
        steps[name] = result
        if verbose and not skip:
            _print_step_verbose(name, result)
        return result

    # 1) validate
    r = _run_step("validate", lambda: step_validate(tool_repo), skip_validate)
    if fail_fast and r.status == "fail":
        # Fill remaining steps as skip
        for name in ("tests", "security", "register"):
            steps[name] = _step_skip()
        return ToolReport(tool_id=tool_id, path=str(tool_repo), steps=steps)

    # 2) tests
    r = _run_step("tests", lambda: step_tests(tool_repo), skip_tests)
    if fail_fast and r.status == "fail":
        for name in ("security", "register"):
            steps[name] = _step_skip()
        return ToolReport(tool_id=tool_id, path=str(tool_repo), steps=steps)

    # 3) security
    r = _run_step("security", lambda: step_security(tool_repo), skip_security)
    if fail_fast and r.status == "fail":
        steps["register"] = _step_skip()
        return ToolReport(tool_id=tool_id, path=str(tool_repo), steps=steps)

    # 4) register
    _run_step(
        "register",
        lambda: step_register(tool_repo, techvault_root, apply, enabled),
        skip_register,
        mode="apply" if apply else "dry-run",
    )

    return ToolReport(tool_id=tool_id, path=str(tool_repo), steps=steps)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def _print_step_verbose(name: str, result: StepResult) -> None:
    if result.stdout.strip():
        print(f"    [stdout]\n{result.stdout.rstrip()}")
    if result.stderr.strip():
        print(f"    [stderr]\n{result.stderr.rstrip()}")


def print_summary(reports: list[ToolReport], apply: bool) -> None:
    reg_mode = "apply" if apply else "dry-run"
    for report in reports:
        print(f"\n{'=' * 60}")
        print(f"TOOL: {report.tool_id}  ({report.path})")
        steps = report.steps
        print(f"  Validate : {steps['validate'].status.upper()}")
        print(f"  Tests    : {steps['tests'].status.upper()}")
        print(f"  Security : {steps['security'].status.upper()}")
        reg = steps["register"]
        mode_label = reg.mode or reg_mode
        print(f"  Register : {reg.status.upper()}  [{mode_label}]")


def overall_passed(reports: list[ToolReport]) -> bool:
    for report in reports:
        for result in report.steps.values():
            if result.status in ("fail", "error"):
                return False
    return True


def _truncate(s: str) -> str:
    return s[:_MAX_OUTPUT_CHARS] if len(s) > _MAX_OUTPUT_CHARS else s


def _step_to_dict(result: StepResult) -> dict:
    d: dict = {
        "exit_code": result.exit_code,
        "status": result.status,
        "stderr": _truncate(result.stderr),
        "stdout": _truncate(result.stdout),
    }
    if result.mode is not None:
        d["mode"] = result.mode
    return d


def build_json_report(
    reports: list[ToolReport],
    techvault_root: Path,
    tools_dir: Path | None,
    apply: bool,
) -> dict:
    return {
        "apply": apply,
        "techvault_root": str(techvault_root),
        "tools": [
            {
                "path": r.path,
                "steps": {k: _step_to_dict(v) for k, v in r.steps.items()},
                "tool_id": r.tool_id,
            }
            for r in sorted(reports, key=lambda r: r.tool_id)
        ],
        "tools_dir": str(tools_dir) if tools_dir else None,
    }


def write_json_report(
    reports: list[ToolReport],
    techvault_root: Path,
    tools_dir: Path | None,
    apply: bool,
    out_path: Path,
) -> None:
    data = build_json_report(reports, techvault_root, tools_dir, apply)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-sync",
        description="Deterministic tool lifecycle orchestrator: validate → test → security → register.",
    )
    parser.add_argument(
        "tool_repo",
        nargs="?",
        metavar="TOOL_REPO",
        help="Path to a single tool repository (mutually exclusive with --all).",
    )
    parser.add_argument(
        "--all",
        dest="all_dir",
        metavar="TOOLS_DIR",
        help="Sync all tool repos found in TOOLS_DIR.",
    )
    parser.add_argument(
        "--techvault-root",
        required=True,
        metavar="PATH",
        help="Root of the TechVault project.",
    )
    parser.add_argument(
        "--tools-dir",
        metavar="PATH",
        help="Where tool repos live (default: <techvault-root>/tools).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Pass --apply to techvault-tool-register.",
    )
    parser.add_argument(
        "--enabled",
        choices=["true", "false"],
        help="Forward --enabled to registrar.",
    )
    parser.add_argument("--skip-validate",  action="store_true", default=False)
    parser.add_argument("--skip-tests",     action="store_true", default=False)
    parser.add_argument("--skip-security",  action="store_true", default=False)
    parser.add_argument("--skip-register",  action="store_true", default=False)
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help="Stop processing a tool after its first failed step.",
    )
    parser.add_argument(
        "--json-report",
        metavar="PATH",
        help="Write deterministic JSON report to this file.",
    )
    parser.add_argument("--verbose", action="store_true", default=False)

    args = parser.parse_args(argv)

    # ---- Validate argv ----
    if args.tool_repo and args.all_dir:
        print("error: TOOL_REPO and --all are mutually exclusive.", file=sys.stderr)
        return 2
    if not args.tool_repo and not args.all_dir:
        print("error: Provide either TOOL_REPO or --all TOOLS_DIR.", file=sys.stderr)
        return 2

    techvault_root = Path(args.techvault_root)
    if not techvault_root.exists():
        print(f"error: --techvault-root does not exist: {techvault_root}", file=sys.stderr)
        return 2

    # ---- Discover tool repos ----
    if args.all_dir:
        tools_dir = Path(args.all_dir)
        if not tools_dir.exists():
            print(f"error: --all TOOLS_DIR does not exist: {tools_dir}", file=sys.stderr)
            return 2
        tool_repos = discover_tools(tools_dir)
        if not tool_repos:
            print("warning: no tool repos found under --all directory.", file=sys.stderr)
        report_tools_dir: Path | None = tools_dir
    else:
        tool_repo = Path(args.tool_repo)
        if not (tool_repo / "tool.toml").exists():
            print(f"error: no tool.toml found in: {tool_repo}", file=sys.stderr)
            return 2
        tool_repos = [tool_repo]
        report_tools_dir = args.tools_dir and Path(args.tools_dir)

    # ---- Sync each tool ----
    reports: list[ToolReport] = []
    mode_label = "APPLY" if args.apply else "DRY-RUN"
    print(f"techvault-tool-sync  [{mode_label}]")
    print(f"techvault-root: {techvault_root}")

    for tool_repo in tool_repos:
        report = sync_one(
            tool_repo,
            techvault_root,
            apply=args.apply,
            enabled=args.enabled,
            skip_validate=args.skip_validate,
            skip_tests=args.skip_tests,
            skip_security=args.skip_security,
            skip_register=args.skip_register,
            fail_fast=args.fail_fast,
            verbose=args.verbose,
        )
        reports.append(report)

    # ---- Print summary ----
    print_summary(reports, args.apply)

    passed = overall_passed(reports)
    print(f"\n{'=' * 60}")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")

    # ---- JSON report ----
    if args.json_report:
        out_path = Path(args.json_report)
        write_json_report(reports, techvault_root, report_tools_dir, args.apply, out_path)
        print(f"JSON report written: {out_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
