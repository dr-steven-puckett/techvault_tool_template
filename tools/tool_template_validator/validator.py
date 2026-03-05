#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Bootstrap: ensure tools/ is on sys.path so tool_common is importable
# whether run directly, via the shell-script shim, or via pytest.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # tools/tool_template_validator/
_TOOLS_ROOT = _HERE.parent                       # tools/
_CATALOG_PATH = _TOOLS_ROOT / "tools.catalog.json"

for _p in (str(_TOOLS_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tool_common.catalog import generate_catalog, load_catalog  # type: ignore  # noqa: E402
from tool_common.report import canonical_json                    # type: ignore  # noqa: E402


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: list[str]


def _find_package_dir(repo: Path) -> tuple[Path | None, str | None]:
    ignored = {".git", "docs", "tests", "tools", "__pycache__", ".venv", "venv"}

    for child in repo.iterdir():
        if not child.is_dir() or child.name in ignored:
            continue
        if (child / "api").is_dir() and (child / "core").is_dir() and (child / "cli").is_dir():
            return child, None

    return None, "Could not find a tool package directory containing api/, core/, and cli/."


def _check_repository_structure(repo: Path) -> CheckResult:
    errors: list[str] = []

    for required_file in ("tool.toml", "README.md", "openapi.snapshot.json"):
        if not (repo / required_file).is_file():
            errors.append(f"Missing required root file: {required_file}")

    docs_dir = repo / "docs"
    if not docs_dir.is_dir():
        errors.append("Missing docs/ directory")
    else:
        if not list(docs_dir.glob("TOOL_*_SOT.md")):
            errors.append("Missing docs/TOOL_*_SOT.md")
        if not list(docs_dir.glob("TOOL_*_EXECUTION_PLAN.md")):
            errors.append("Missing docs/TOOL_*_EXECUTION_PLAN.md")
        if not list(docs_dir.glob("TOOL_*_ROADMAP.md")):
            errors.append("Missing docs/TOOL_*_ROADMAP.md")
        if not (docs_dir / "prompts").is_dir():
            errors.append("Missing docs/prompts/ directory")

    package_dir, package_err = _find_package_dir(repo)
    if package_err:
        errors.append(package_err)
    elif package_dir is not None:
        for subdir in ("api", "core", "cli"):
            if not (package_dir / subdir).is_dir():
                errors.append(f"Missing package subdirectory: {package_dir.name}/{subdir}/")

    if not (repo / "tests").is_dir():
        errors.append("Missing tests/ directory")

    return CheckResult("Repository Structure", not errors, errors)


def _check_prompt_pack_integrity(repo: Path) -> CheckResult:
    errors: list[str] = []
    prompts_dir = repo / "docs" / "prompts"

    required = [
        "00_scaffold_repo.md",
        "01_contracts_and_determinism.md",
        "02_catalog_loader.md",
        "03_service_layer_ordering.md",
        "04_api_interface.md",
        "05_openapi_snapshot.md",
        "06_determinism_and_hash_tests.md",
        "07_final_gate.md",
        "08_cli_interface.md",
        "09_release_readiness.md",
        "10_sot_invariant_check.md",
        "README.md",
    ]

    if not prompts_dir.is_dir():
        errors.append("Missing docs/prompts/ directory")
    else:
        for filename in required:
            if not (prompts_dir / filename).is_file():
                errors.append(f"Missing prompt file: docs/prompts/{filename}")

    return CheckResult("Prompt Pack Integrity", not errors, errors)


def _check_determinism_enforcement(repo: Path) -> CheckResult:
    errors: list[str] = []
    package_dir, package_err = _find_package_dir(repo)

    if package_err:
        errors.append(package_err)
    elif package_dir is not None and not (package_dir / "core" / "determinism.py").is_file():
        errors.append(f"Missing file: {package_dir.name}/core/determinism.py")

    if not (repo / "tests" / "test_determinism_json.py").is_file():
        errors.append("Missing file: tests/test_determinism_json.py")

    return CheckResult("Determinism Enforcement", not errors, errors)


def _check_cli_requirements(repo: Path) -> CheckResult:
    errors: list[str] = []
    package_dir, package_err = _find_package_dir(repo)

    if package_err:
        errors.append(package_err)
    elif package_dir is not None:
        cli_main = package_dir / "cli" / "main.py"
        if not cli_main.is_file():
            errors.append(f"Missing file: {package_dir.name}/cli/main.py")
        else:
            content = cli_main.read_text(encoding="utf-8", errors="replace")
            if "--catalog-file" not in content:
                errors.append(f"{package_dir.name}/cli/main.py does not contain '--catalog-file'")

    return CheckResult("CLI Requirements", not errors, errors)


def _check_service_layer_contract(repo: Path) -> CheckResult:
    errors: list[str] = []
    package_dir, package_err = _find_package_dir(repo)

    if package_err:
        errors.append(package_err)
    elif package_dir is not None:
        service_file = package_dir / "core" / "service.py"
        if not service_file.is_file():
            errors.append(f"Missing file: {package_dir.name}/core/service.py")
        else:
            content = service_file.read_text(encoding="utf-8", errors="replace")
            if "ValueError" not in content:
                errors.append(f"{package_dir.name}/core/service.py does not reference 'ValueError'")
            if "PermissionError" not in content:
                errors.append(f"{package_dir.name}/core/service.py does not reference 'PermissionError'")

    return CheckResult("Service Layer Contract", not errors, errors)


def _check_test_coverage(repo: Path) -> CheckResult:
    errors: list[str] = []
    tests_dir = repo / "tests"

    required_tests = [
        "test_contract_schemas.py",
        "test_ordering_pagination.py",
        "test_determinism_json.py",
        "test_cli_smoke.py",
        "test_api_smoke.py",
        "test_openapi_snapshot.py",
    ]

    if not tests_dir.is_dir():
        errors.append("Missing tests/ directory")
    else:
        for filename in required_tests:
            if not (tests_dir / filename).is_file():
                errors.append(f"Missing test file: tests/{filename}")

    return CheckResult("Test Coverage", not errors, errors)


def _check_openapi_snapshot(repo: Path) -> CheckResult:
    errors: list[str] = []

    if not (repo / "openapi.snapshot.json").is_file():
        errors.append("Missing file: openapi.snapshot.json")

    return CheckResult("OpenAPI Snapshot", not errors, errors)


def _safe_run(name: str, check_fn: Callable[[Path], CheckResult], repo: Path) -> CheckResult:
    try:
        return check_fn(repo)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name, False, [f"Unexpected validator error: {exc.__class__.__name__}: {exc}"])


def run_validation(repo_path: Path) -> tuple[list[CheckResult], bool]:
    checks: list[tuple[str, Callable[[Path], CheckResult]]] = [
        ("Repository Structure", _check_repository_structure),
        ("Prompt Pack Integrity", _check_prompt_pack_integrity),
        ("Determinism Enforcement", _check_determinism_enforcement),
        ("CLI Requirements", _check_cli_requirements),
        ("Service Layer Contract", _check_service_layer_contract),
        ("Test Coverage", _check_test_coverage),
        ("OpenAPI Snapshot", _check_openapi_snapshot),
    ]

    results = [_safe_run(name, fn, repo_path) for name, fn in checks]
    compliant = all(result.passed for result in results)
    return results, compliant


def print_report(repo_path: Path, results: list[CheckResult], compliant: bool) -> None:
    print(f"TechVault Tool Template Compliance Report: {repo_path}")
    print("=" * 72)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{result.name}: {status}")
        for detail in result.details:
            print(f"  - {detail}")

    print("-" * 72)
    print(f"Final Compliance: {'PASS' if compliant else 'FAIL'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techvault-tool-validate",
        description="Validate a TechVault tool repository against template SOT requirements.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=None,
        help="Path to the repository to validate (optional when --check-catalog is used).",
    )
    parser.add_argument(
        "--check-catalog",
        action="store_true",
        default=False,
        help=(
            "Generate the expected tools.catalog.json in-memory and compare it "
            "byte-for-byte with the file on disk.  Outputs a deterministic JSON "
            "result.  Exit 0 = match, 1 = mismatch / file missing, 2 = error."
        ),
    )
    args = parser.parse_args(argv)

    if not args.repo_path and not args.check_catalog:
        parser.print_usage(sys.stderr)
        print("error: provide REPO_PATH or --check-catalog (or both).", file=sys.stderr)
        return 2

    exit_code = 0

    if args.repo_path:
        repo = Path(args.repo_path).resolve()
        if not repo.exists() or not repo.is_dir():
            print(f"Repository path is not a directory: {repo}")
            return 1
        results, compliant = run_validation(repo)
        print_report(repo, results, compliant)
        if not compliant:
            exit_code = 1

    if args.check_catalog:
        catalog_result = check_catalog(_TOOLS_ROOT, _CATALOG_PATH)
        print(canonical_json(catalog_result), end="")
        if catalog_result["status"] != "match":
            exit_code = max(exit_code, 1)

    return exit_code


def check_catalog(tools_root: Path, catalog_path: Path) -> dict:
    """Compare generated catalog against the file at *catalog_path*.

    Parameters
    ----------
    tools_root:
        The ``tools/`` directory to scan for tool dirs.
    catalog_path:
        Path to the existing ``tools.catalog.json`` file.

    Returns
    -------
    dict with keys:
        ``status``         -- ``"match"`` | ``"mismatch"`` | ``"file_missing"`` | ``"error"``
        ``catalog_path``   -- str path of the checked file
        ``catalog_mismatch`` -- True if content differs (only when status=mismatch)
        ``expected_path``  -- str path (same as catalog_path; for report clarity)
        ``first_diff_index`` -- int byte index of first difference (only when status=mismatch)
    """
    try:
        expected_dict = generate_catalog(tools_root)
        expected_str = canonical_json(expected_dict)
    except Exception as exc:  # noqa: BLE001
        return {
            "catalog_path": str(catalog_path),
            "error": f"{type(exc).__name__}: {exc}",
            "expected_path": str(catalog_path),
            "status": "error",
        }

    if not catalog_path.is_file():
        return {
            "catalog_mismatch": True,
            "catalog_path": str(catalog_path),
            "expected_path": str(catalog_path),
            "status": "file_missing",
        }

    try:
        actual_str = catalog_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {
            "catalog_path": str(catalog_path),
            "error": f"{type(exc).__name__}: {exc}",
            "expected_path": str(catalog_path),
            "status": "error",
        }

    if expected_str == actual_str:
        return {
            "catalog_path": str(catalog_path),
            "catalog_mismatch": False,
            "expected_path": str(catalog_path),
            "status": "match",
        }

    # Find first differing byte index for deterministic diagnostics.
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(expected_str, actual_str)) if a != b),
        min(len(expected_str), len(actual_str)),
    )
    return {
        "catalog_mismatch": True,
        "catalog_path": str(catalog_path),
        "expected_path": str(catalog_path),
        "first_diff_index": first_diff,
        "status": "mismatch",
    }


if __name__ == "__main__":
    raise SystemExit(main())