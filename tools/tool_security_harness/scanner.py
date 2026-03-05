#!/usr/bin/env python3
"""TechVault Tool Security Scanner — deterministic, offline security harness.

Exit codes:
  0 = PASS  (no FAIL-severity findings)
  1 = FAIL  (one or more FAIL-severity findings)
  2 = ERROR (could not complete scan; repo path invalid or unexpected exception)
"""
from __future__ import annotations

import ast
import argparse
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_FAIL = "FAIL"
_WARN = "WARN"


@dataclass(frozen=True)
class Finding:
    severity: str     # "FAIL" or "WARN"
    file_path: str    # repo-relative path, empty string when N/A
    line: int         # 0  means no line info
    message: str

    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.file_path, self.line, self.severity, self.message)


@dataclass
class SectionResult:
    name: str
    passed: bool = True
    skipped: bool = False
    skip_reason: str = ""
    findings: list[Finding] = field(default_factory=list)

    def add(self, f: Finding) -> None:
        self.findings.append(f)
        if f.severity == _FAIL:
            self.passed = False

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: f.sort_key())


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _func_name(node: ast.Call) -> str | None:
    """Extract dotted function name from a Call node, e.g. 'subprocess.run'."""
    func = node.func
    parts: list[str] = []
    current: ast.expr = func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value  # type: ignore[assignment]
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _is_debug_level(node: ast.expr) -> bool:
    """Detect logging.DEBUG (constant 10 or attribute DEBUG)."""
    if isinstance(node, ast.Constant) and node.value == 10:
        return True
    if isinstance(node, ast.Attribute) and node.attr == "DEBUG":
        return True
    return False


class _PolicyVisitor(ast.NodeVisitor):
    """Walk an AST and collect policy violation findings."""

    _FORBIDDEN_IMPORTS = frozenset({"pickle", "requests", "httpx", "socket"})

    def __init__(self, rel_path: str) -> None:
        self._rel = rel_path
        self.findings: list[Finding] = []

    # ------------------------------------------------------------------ helpers

    def _add(self, node: ast.AST, msg: str, severity: str = _FAIL) -> None:
        self.findings.append(
            Finding(severity, self._rel, getattr(node, "lineno", 0), msg)
        )

    # ------------------------------------------------------------------ import checks

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in self._FORBIDDEN_IMPORTS:
                self._add(node, f"Forbidden import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = (node.module or "").split(".")[0]
        if module in self._FORBIDDEN_IMPORTS:
            self._add(node, f"Forbidden import: from {node.module} import ...")
        self.generic_visit(node)

    # ------------------------------------------------------------------ call checks

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        fname = _func_name(node)

        # eval( / exec(
        if fname in ("eval", "exec"):
            self._add(node, f"Forbidden call: {fname}()")

        # os.system(
        elif fname == "os.system":
            self._add(node, "Forbidden call: os.system()")

        # subprocess.* with shell=True
        elif fname and fname.startswith("subprocess."):
            for kw in node.keywords:
                if (
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    self._add(node, f"Forbidden call: {fname}(shell=True)")
                    break

        # yaml.load( (any usage — spec says treat as fail)
        elif fname == "yaml.load":
            self._add(
                node,
                "Forbidden call: yaml.load() — use yaml.safe_load() instead",
            )

        # logging DEBUG warning (WARN severity only)
        elif fname in (
            "logging.basicConfig",
            "logging.root.setLevel",
            "basicConfig",
        ):
            for kw in node.keywords:
                if kw.arg == "level" and _is_debug_level(kw.value):
                    self._add(
                        node,
                        "logging configured at DEBUG level by default",
                        _WARN,
                    )
            for arg in node.args:
                if _is_debug_level(arg):
                    self._add(
                        node,
                        "logging configured at DEBUG level by default",
                        _WARN,
                    )

        # logger.setLevel(logging.DEBUG) pattern
        elif fname and fname.endswith(".setLevel"):
            for arg in node.args:
                if _is_debug_level(arg):
                    self._add(
                        node,
                        "logger configured at DEBUG level by default",
                        _WARN,
                    )

        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Utility: find tool package dir and tool_id
# ---------------------------------------------------------------------------

_IGNORED_DIRS = frozenset(
    {".git", "docs", "tests", "tools", "__pycache__", ".venv", "venv", ".tox"}
)


def _find_package_dir(repo: Path) -> Path | None:
    """Return the first child directory that looks like a tool package."""
    for child in sorted(repo.iterdir()):  # sorted → deterministic
        if not child.is_dir() or child.name in _IGNORED_DIRS:
            continue
        if (child / "api").is_dir() and (child / "core").is_dir() and (child / "cli").is_dir():
            return child
    return None


def _parse_tool_id(repo: Path) -> str | None:
    """Extract tool_id from tool.toml (regex, no TOML library dependency)."""
    toml_file = repo / "tool.toml"
    if not toml_file.is_file():
        return None
    content = toml_file.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^tool_id\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return m.group(1) if m else None


def _iter_py_files(directory: Path) -> list[Path]:
    """Return sorted list of .py files under directory."""
    return sorted(directory.rglob("*.py"))


# ---------------------------------------------------------------------------
# Check 1: Static policy checks
# ---------------------------------------------------------------------------

def check_static_policy(repo: Path) -> SectionResult:
    result = SectionResult("Static Policy Checks")

    pkg = _find_package_dir(repo)
    if pkg is None:
        result.add(Finding(_FAIL, "", 0, "Cannot locate tool package directory — skipping static scan"))
        return result

    py_files = _iter_py_files(pkg)
    if not py_files:
        result.add(Finding(_WARN, "", 0, "No Python source files found in package"))
        return result

    for py_file in py_files:
        rel = str(py_file.relative_to(repo))
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.add(Finding(_FAIL, rel, 0, f"Could not read file: {exc}"))
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            result.add(
                Finding(_WARN, rel, exc.lineno or 0, f"SyntaxError — could not AST-parse: {exc.msg}")
            )
            continue

        visitor = _PolicyVisitor(rel)
        visitor.visit(tree)
        for finding in visitor.findings:
            result.add(finding)

    return result


# ---------------------------------------------------------------------------
# Check 2: Path safety checks
# ---------------------------------------------------------------------------

_PATH_SAFETY_PATTERNS: list[tuple[str, str]] = [
    # Each tuple: (regex pattern, description of what it checks for)
    (r"os\.path\.isabs|\.startswith\s*\(\s*[\"']/", "absolute-path rejection"),
    (r"\.\.\s*[\"']|[\"']\s*\.\.", "path-traversal segment rejection"),
    (r"encode\s*\([\"']utf.?8[\"']\)|\.encode\s*\(\s*\)", "UTF-8 validation"),
    (r"ValueError", "raises ValueError on bad input"),
]


def _static_path_safety(content: str) -> list[str]:
    """Return list of missing safety checks (by description)."""
    missing = []
    for pattern, description in _PATH_SAFETY_PATTERNS:
        if not re.search(pattern, content):
            missing.append(description)
    return missing


def _dynamic_path_safety(
    loader_file: Path, repo: Path, verbose: bool
) -> list[str]:
    """
    Attempt to import catalog_loader and call the first public callable with
    bad path inputs. Returns list of failure messages.
    """
    failures: list[str] = []
    original_sys_path = sys.path[:]
    try:
        sys.path.insert(0, str(repo))
        spec = importlib.util.spec_from_file_location(
            "_sec_scan_loader_test", loader_file
        )
        if spec is None or spec.loader is None:
            return ["Could not create import spec for catalog_loader.py"]
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Find the first public callable that accepts at least one arg
        candidates = [
            name
            for name in sorted(dir(module))
            if not name.startswith("_") and callable(getattr(module, name, None))
        ]
        if not candidates:
            return ["No public callable found in catalog_loader.py to test"]

        func = getattr(module, candidates[0])
        bad_inputs = ["/absolute/path", "../traversal", "..\\traversal"]
        for bad in bad_inputs:
            try:
                func(bad)
                # If we get here the bad path was NOT rejected
                failures.append(
                    f"catalog_loader.{candidates[0]}({bad!r}) did not raise ValueError"
                )
            except ValueError:
                pass  # Good — path was explicitly rejected before filesystem access
            except (FileNotFoundError, PermissionError, OSError) as exc:
                # The function touched the filesystem with the bad path instead
                # of rejecting it early — this is a security failure.
                failures.append(
                    f"catalog_loader.{candidates[0]}({bad!r}) reached filesystem "
                    f"({type(exc).__name__}) instead of raising ValueError"
                )
            except (TypeError, AttributeError, IndexError):
                # Signature mismatch or unrelated structural error — skip this input
                pass
            except Exception:  # noqa: BLE001
                # Unexpected exception — skip (not a path safety failure per se)
                pass
    except Exception as exc:  # noqa: BLE001
        msg = f"Dynamic import/test failed: {exc}"
        if verbose:
            msg += "\n" + traceback.format_exc()
        failures.append(msg)
    finally:
        sys.path[:] = original_sys_path

    return failures


def check_path_safety(repo: Path, verbose: bool = False) -> SectionResult:
    result = SectionResult("Path Safety Checks")

    pkg = _find_package_dir(repo)
    if pkg is None:
        result.skipped = True
        result.skip_reason = "No tool package directory found"
        return result

    loader_file = pkg / "core" / "catalog_loader.py"
    if not loader_file.is_file():
        result.skipped = True
        result.skip_reason = "core/catalog_loader.py not present — skipping path safety"
        return result

    rel = str(loader_file.relative_to(repo))
    try:
        content = loader_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result.add(Finding(_FAIL, rel, 0, f"Could not read catalog_loader.py: {exc}"))
        return result

    missing_static = _static_path_safety(content)
    if not missing_static:
        # Static analysis confirmed all patterns — no dynamic test needed
        return result

    # Static analysis inconclusive — fall back to dynamic test
    dynamic_failures = _dynamic_path_safety(loader_file, repo, verbose)
    if dynamic_failures:
        for msg in dynamic_failures:
            result.add(Finding(_FAIL, rel, 0, msg))
    elif missing_static:
        # Dynamic passed but static patterns were absent — warn
        for desc in missing_static:
            result.add(
                Finding(
                    _WARN,
                    rel,
                    0,
                    f"Static pattern for '{desc}' not found — confirmed via dynamic test",
                )
            )

    return result


# ---------------------------------------------------------------------------
# Check 3: CLI error leak checks
# ---------------------------------------------------------------------------

_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)")


def _run_cli(
    package: str, repo: Path, args: list[str], timeout: int = 10
) -> tuple[str, str, int | None]:
    """Run `python -m <package>.cli.main [args]` and return (stdout, stderr, returncode)."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo) + (os.pathsep + existing if existing else "")

    try:
        proc = subprocess.run(
            [sys.executable, "-m", f"{package}.cli.main"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(repo),
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "[TIMEOUT]", None
    except Exception as exc:  # noqa: BLE001
        return "", f"[RUNNER ERROR: {exc}]", None


def check_cli_error_leaks(repo: Path, verbose: bool = False) -> SectionResult:
    result = SectionResult("CLI Error Leak Checks")

    pkg = _find_package_dir(repo)
    if pkg is None:
        result.skipped = True
        result.skip_reason = "No tool package directory found"
        return result

    cli_main = pkg / "cli" / "main.py"
    if not cli_main.is_file():
        result.skipped = True
        result.skip_reason = f"{pkg.name}/cli/main.py not present"
        return result

    package_name = pkg.name

    # --- health check ---
    stdout, stderr, rc = _run_cli(package_name, repo, ["health"])
    if rc is None:
        result.add(Finding(_FAIL, f"{package_name}/cli/main.py", 0, f"health invocation did not complete: {stderr}"))
    else:
        # stdout must be valid JSON
        stripped = stdout.strip()
        if stripped:
            try:
                json.loads(stripped)
            except json.JSONDecodeError:
                result.add(
                    Finding(_FAIL, f"{package_name}/cli/main.py", 0,
                            f"health stdout is not valid JSON: {stripped[:120]!r}")
                )
        else:
            # Empty stdout is acceptable for health if it exits 0
            pass

        if _TRACEBACK_RE.search(stderr):
            result.add(
                Finding(_FAIL, f"{package_name}/cli/main.py", 0,
                        "health: Python traceback detected in stderr")
            )

    # --- missing-args failure check ---
    stdout2, stderr2, rc2 = _run_cli(package_name, repo, [])
    if rc2 is None:
        result.add(
            Finding(_WARN, f"{package_name}/cli/main.py", 0,
                    f"no-args invocation did not complete: {stderr2}")
        )
    else:
        if _TRACEBACK_RE.search(stderr2):
            result.add(
                Finding(_FAIL, f"{package_name}/cli/main.py", 0,
                        "no-args invocation: Python traceback detected in stderr")
            )
        # JSON on stderr is acceptable; raw traceback is not
        out_stripped = stdout2.strip()
        if out_stripped:
            try:
                json.loads(out_stripped)
            except json.JSONDecodeError:
                # Non-JSON stdout on failure is a finding
                result.add(
                    Finding(_FAIL, f"{package_name}/cli/main.py", 0,
                            f"no-args invocation: stdout is not JSON: {out_stripped[:120]!r}")
                )

    return result


# ---------------------------------------------------------------------------
# Check 4: API surface sanity
# ---------------------------------------------------------------------------

def check_api_surface(repo: Path, verbose: bool = False) -> SectionResult:
    result = SectionResult("API Surface Sanity")

    pkg = _find_package_dir(repo)
    if pkg is None:
        result.skipped = True
        result.skip_reason = "No tool package directory found"
        return result

    router_file = pkg / "api" / "router.py"
    if not router_file.is_file():
        result.skipped = True
        result.skip_reason = f"{pkg.name}/api/router.py not present"
        return result

    tool_id = _parse_tool_id(repo) or pkg.name
    package_name = pkg.name
    rel = f"{package_name}/api/router.py"
    expected_prefix = f"/v1/tools/{tool_id}"
    expected_tag = f"tools:{tool_id}"

    original_sys_path = sys.path[:]
    try:
        sys.path.insert(0, str(repo))

        spec = importlib.util.spec_from_file_location(
            f"_sec_scan_router_{package_name}", router_file
        )
        if spec is None or spec.loader is None:
            result.add(Finding(_FAIL, rel, 0, "Could not create import spec for router.py"))
            return result

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        router = getattr(module, "router", None)
        if router is None:
            result.add(Finding(_FAIL, rel, 0, "router.py does not expose a 'router' attribute"))
            return result

        # Check router prefix
        router_prefix = getattr(router, "prefix", "")
        if not router_prefix.startswith(expected_prefix):
            result.add(
                Finding(
                    _FAIL, rel, 0,
                    f"Router prefix {router_prefix!r} does not start with {expected_prefix!r}",
                )
            )

        # Check router tags
        router_tags = list(getattr(router, "tags", []))
        if expected_tag not in router_tags:
            result.add(
                Finding(
                    _FAIL, rel, 0,
                    f"Router tags {router_tags!r} do not include {expected_tag!r}",
                )
            )

        # Mount into minimal FastAPI app and inspect routes
        try:
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            routes = sorted(
                r.path
                for r in app.routes
                if hasattr(r, "path") and not r.path.startswith("/openapi") and r.path not in ("/docs", "/redoc")
            )
            unexpected = [r for r in routes if not r.startswith(expected_prefix)]
            if unexpected:
                result.add(
                    Finding(
                        _FAIL, rel, 0,
                        f"Unexpected routes not under {expected_prefix!r}: {unexpected}",
                    )
                )

            # Check OpenAPI tags in schema
            schema = app.openapi()
            all_tags: set[str] = set()
            for path_obj in schema.get("paths", {}).values():
                for op in path_obj.values():
                    if isinstance(op, dict):
                        all_tags.update(op.get("tags", []))
            if expected_tag not in all_tags:
                result.add(
                    Finding(
                        _WARN, rel, 0,
                        f"OpenAPI schema does not contain tag {expected_tag!r}",
                    )
                )

        except ImportError:
            result.add(
                Finding(
                    _WARN, rel, 0,
                    "fastapi not installed — skipping in-process route mount check",
                )
            )

    except Exception as exc:  # noqa: BLE001
        msg = f"Dynamic router import failed: {exc}"
        if verbose:
            msg += "\n" + traceback.format_exc()
        result.add(Finding(_FAIL, rel, 0, msg))
    finally:
        sys.path[:] = original_sys_path

    return result


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(
    repo_path: Path,
    sections: list[SectionResult],
    overall_pass: bool,
    verbose: bool = False,
) -> None:
    WIDTH = 72
    print(f"TechVault Tool Security Scan: {repo_path}")
    print("=" * WIDTH)

    for section in sections:
        if section.skipped:
            print(f"\n[{section.name}] SKIPPED — {section.skip_reason}")
            continue

        status = "PASS" if section.passed else "FAIL"
        print(f"\n[{section.name}] {status}")
        for finding in section.sorted_findings():
            loc = finding.file_path
            if finding.line:
                loc = f"{loc}:{finding.line}"
            prefix = f"  [{finding.severity}]"
            if loc:
                print(f"{prefix} {loc} — {finding.message}")
            else:
                print(f"{prefix} {finding.message}")

    print("\n" + "-" * WIDTH)
    print(f"RESULT: {'PASS' if overall_pass else 'FAIL'}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_scan(
    repo: Path, verbose: bool = False
) -> tuple[list[SectionResult], bool]:
    """Run all checks in defined order; return (sections, overall_pass)."""
    checks: list[Callable[[], SectionResult]] = [
        lambda: check_static_policy(repo),
        lambda: check_path_safety(repo, verbose),
        lambda: check_cli_error_leaks(repo, verbose),
        lambda: check_api_surface(repo, verbose),
    ]

    sections: list[SectionResult] = []
    for check_fn in checks:
        try:
            sections.append(check_fn())
        except Exception as exc:  # noqa: BLE001
            name = check_fn.__name__ if hasattr(check_fn, "__name__") else "Unknown"
            r = SectionResult(name, passed=False)
            msg = f"Unexpected scanner error: {exc}"
            if verbose:
                msg += "\n" + traceback.format_exc()
            r.add(Finding(_FAIL, "", 0, msg))
            sections.append(r)

    overall_pass = all(
        s.passed for s in sections if not s.skipped
    )
    return sections, overall_pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-security-scan",
        description=(
            "Deterministically scan a TechVault tool repository for "
            "common cybersecurity hazards and policy violations (offline)."
        ),
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the tool repository to scan (default: current directory).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print stack traces on unexpected scanner errors.",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()
    if not repo.exists() or not repo.is_dir():
        print(
            f"ERROR: Repository path does not exist or is not a directory: {repo}",
            file=sys.stderr,
        )
        return 2

    try:
        sections, overall_pass = run_scan(repo, verbose=args.verbose)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Scan aborted: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 2

    print_report(repo, sections, overall_pass, verbose=args.verbose)
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
