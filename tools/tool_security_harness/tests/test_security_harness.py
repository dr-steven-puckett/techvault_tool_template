"""pytest suite for techvault-tool-security-scan harness.

Tests cover:
- Exit code 0 (PASS) for a clean tool repository
- Exit code 1 (FAIL) for a repository with policy violations
- Exit code 2 (ERROR) for a non-existent path
- Report structure: sections appear in the required order
- Findings include file paths and line numbers where available
- RESULT line is the last meaningful line of the report
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HARNESS_DIR = Path(__file__).resolve().parent.parent  # tools/tool_security_harness/
_SCANNER = _HARNESS_DIR / "scanner.py"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_GOOD_TOOL = _FIXTURES / "good_tool"
_BAD_TOOL = _FIXTURES / "bad_tool"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECTION_ORDER = [
    "Static Policy Checks",
    "Path Safety Checks",
    "CLI Error Leak Checks",
    "API Surface Sanity",
]


def _run_scanner(repo_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_SCANNER), str(repo_path)] + (extra_args or [])
    return subprocess.run(cmd, capture_output=True, text=True)


def _section_positions(output: str) -> dict[str, int]:
    """Return {section_name: line_index} for each section header in stdout."""
    lines = output.splitlines()
    positions: dict[str, int] = {}
    for i, line in enumerate(lines):
        for name in SECTION_ORDER:
            if f"[{name}]" in line:
                positions[name] = i
    return positions


# ---------------------------------------------------------------------------
# Fixture availability guards
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def good_repo() -> Path:
    assert _GOOD_TOOL.is_dir(), f"Good tool fixture missing: {_GOOD_TOOL}"
    return _GOOD_TOOL


@pytest.fixture(scope="session")
def bad_repo() -> Path:
    assert _BAD_TOOL.is_dir(), f"Bad tool fixture missing: {_BAD_TOOL}"
    return _BAD_TOOL


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------

class TestExitCodes:
    def test_good_tool_returns_0(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        assert result.returncode == 0, (
            f"Expected exit 0 for clean repo, got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_bad_tool_returns_1(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert result.returncode == 1, (
            f"Expected exit 1 for bad repo, got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_nonexistent_path_returns_2(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        result = _run_scanner(nonexistent)
        assert result.returncode == 2, (
            f"Expected exit 2 for nonexistent path, got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_nonexistent_path_message_on_stderr(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        result = _run_scanner(nonexistent)
        assert result.returncode == 2
        assert "ERROR" in result.stderr, "Expected 'ERROR' in stderr for missing path"
        assert result.stdout == "", "Expected empty stdout for error exit"


# ---------------------------------------------------------------------------
# Section ordering tests
# ---------------------------------------------------------------------------

class TestSectionOrder:
    def test_sections_appear_in_required_order(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        positions = _section_positions(result.stdout)

        present = [name for name in SECTION_ORDER if name in positions]
        assert len(present) >= 2, f"Expected at least 2 section headers; got: {present}"

        for i in range(len(present) - 1):
            a, b = present[i], present[i + 1]
            assert positions[a] < positions[b], (
                f"Section '{a}' (line {positions[a]}) appeared after '{b}' "
                f"(line {positions[b]}) — expected ordered output"
            )

    def test_sections_appear_in_required_order_bad_tool(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        positions = _section_positions(result.stdout)

        present = [name for name in SECTION_ORDER if name in positions]
        assert len(present) >= 1, "Expected at least one section header in bad_tool report"

        for i in range(len(present) - 1):
            a, b = present[i], present[i + 1]
            assert positions[a] < positions[b], (
                f"Section order violated: '{a}' after '{b}'"
            )


# ---------------------------------------------------------------------------
# Report structure tests
# ---------------------------------------------------------------------------

class TestReportStructure:
    def test_result_line_is_last_meaningful_line(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        assert lines, "Report stdout is empty"
        last = lines[-1]
        assert last.startswith("RESULT:"), (
            f"Last non-empty line must start with 'RESULT:', got: {last!r}"
        )

    def test_result_pass_for_good_tool(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        assert "RESULT: PASS" in result.stdout, (
            f"Expected 'RESULT: PASS' in output.\nstdout:\n{result.stdout}"
        )

    def test_result_fail_for_bad_tool(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "RESULT: FAIL" in result.stdout, (
            f"Expected 'RESULT: FAIL' in output.\nstdout:\n{result.stdout}"
        )

    def test_report_header_contains_repo_path(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        assert "TechVault Tool Security Scan" in first_line, (
            f"Expected report header in first output line, got: {first_line!r}"
        )

    def test_no_stack_trace_in_stdout_by_default(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "Traceback (most recent call last)" not in result.stdout, (
            "Stack traces must not appear in stdout without --verbose"
        )

    def test_no_stack_trace_in_stderr_by_default(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "Traceback (most recent call last)" not in result.stderr, (
            "Stack traces must not appear in stderr without --verbose"
        )


# ---------------------------------------------------------------------------
# Static policy finding tests
# ---------------------------------------------------------------------------

class TestStaticPolicyFindings:
    def test_bad_tool_static_findings_present(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "[FAIL]" in result.stdout, "Expected FAIL findings in bad_tool static scan"

    def test_bad_tool_evil_file_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "evil.py" in result.stdout, (
            "Expected evil.py to appear in findings"
        )

    def test_bad_tool_pickle_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "pickle" in result.stdout.lower(), "Expected pickle violation to be reported"

    def test_bad_tool_subprocess_shell_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "shell=True" in result.stdout, "Expected subprocess shell=True to be reported"

    def test_bad_tool_eval_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "eval" in result.stdout, "Expected eval() violation to be reported"

    def test_bad_tool_os_system_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "os.system" in result.stdout, "Expected os.system() violation to be reported"

    def test_bad_tool_yaml_load_flagged(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        assert "yaml.load" in result.stdout, "Expected yaml.load() violation to be reported"

    def test_good_tool_no_static_fail_findings(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        lines = result.stdout.splitlines()
        # Find lines inside the Static Policy Checks section
        in_section = False
        fail_lines = []
        for line in lines:
            if "[Static Policy Checks]" in line:
                in_section = True
            elif in_section and line.startswith("["):
                in_section = False
            elif in_section and "[FAIL]" in line:
                fail_lines.append(line)
        assert not fail_lines, (
            f"Good tool should have no FAIL findings in Static Policy Checks; got: {fail_lines}"
        )

    def test_findings_sorted_by_file_then_line(self, bad_repo: Path) -> None:
        """Within each section, findings must be sorted by (file_path, line)."""
        import re

        result = _run_scanner(bad_repo)
        lines = result.stdout.splitlines()

        # Walk through sections and collect per-section findings
        current_section: list[tuple[str, int]] = []
        sections_seen: dict[str, list[tuple[str, int]]] = {}
        current_name = ""

        for line in lines:
            # Section header — e.g. "[Static Policy Checks] FAIL"
            header_match = re.match(r"\[([^\]]+)\]\s*(PASS|FAIL|SKIPPED)", line)
            if header_match:
                if current_name and current_section:
                    sections_seen[current_name] = list(current_section)
                current_name = header_match.group(1)
                current_section = []
                continue

            stripped = line.strip()
            if stripped.startswith("[FAIL]") or stripped.startswith("[WARN]"):
                m = re.search(r"(\S+\.py):?(\d*)", stripped)
                if m:
                    fname = m.group(1)
                    lineno = int(m.group(2)) if m.group(2) else 0
                    current_section.append((fname, lineno))

        if current_name and current_section:
            sections_seen[current_name] = current_section

        assert sections_seen, "No section findings found to verify ordering"

        for section_name, refs in sections_seen.items():
            assert refs == sorted(refs), (
                f"Section '{section_name}' findings are not sorted by (file, line): {refs}"
            )


# ---------------------------------------------------------------------------
# Path safety findings tests
# ---------------------------------------------------------------------------

class TestPathSafetyFindings:
    def test_good_tool_path_safety_passes(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        lines = result.stdout.splitlines()
        for line in lines:
            if "[Path Safety Checks]" in line:
                assert "PASS" in line or "SKIPPED" in line, (
                    f"Good tool path safety should PASS or be SKIPPED; got: {line!r}"
                )
                return
        # Section not found means it was skipped — acceptable

    def test_bad_tool_path_safety_detected(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        # Either we get FAIL findings from static analysis or a dynamic test failure
        # The section may be FAIL or contain [FAIL] findings
        has_path_section = "[Path Safety Checks]" in result.stdout
        if has_path_section:
            lines = result.stdout.splitlines()
            in_path_section = False
            section_status_line = ""
            for line in lines:
                if "[Path Safety Checks]" in line:
                    in_path_section = True
                    section_status_line = line
                elif in_path_section and line.startswith("["):
                    in_path_section = False
            # For bad_tool the section should either be FAIL or contain findings
            assert "FAIL" in section_status_line or "[FAIL]" in result.stdout, (
                f"Bad tool should have path safety findings; section line: {section_status_line!r}"
            )


# ---------------------------------------------------------------------------
# CLI error leak findings tests
# ---------------------------------------------------------------------------

class TestCLIErrorLeakFindings:
    def test_good_tool_cli_check_passes(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo)
        lines = result.stdout.splitlines()
        for line in lines:
            if "[CLI Error Leak Checks]" in line:
                assert "PASS" in line or "SKIPPED" in line, (
                    f"Good tool CLI check should PASS or be SKIPPED; got: {line!r}"
                )
                return

    def test_bad_tool_cli_traceback_detected(self, bad_repo: Path) -> None:
        result = _run_scanner(bad_repo)
        lines = result.stdout.splitlines()
        in_cli_section = False
        fail_lines = []
        for line in lines:
            if "[CLI Error Leak Checks]" in line:
                in_cli_section = True
            elif in_cli_section and line.startswith("["):
                in_cli_section = False
            elif in_cli_section and "[FAIL]" in line:
                fail_lines.append(line)
        assert fail_lines, (
            "Expected [FAIL] findings in CLI Error Leak Checks for bad_tool.\n"
            f"stdout:\n{result.stdout}"
        )

    def test_scanner_stderr_contains_no_traceback_for_bad_tool(self, bad_repo: Path) -> None:
        """The scanner itself must not emit tracebacks, even when scanning a bad tool."""
        result = _run_scanner(bad_repo)
        assert "Traceback (most recent call last)" not in result.stderr


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_output_on_repeated_runs(self, bad_repo: Path) -> None:
        run1 = _run_scanner(bad_repo)
        run2 = _run_scanner(bad_repo)
        assert run1.stdout == run2.stdout, (
            "Scanner output is not deterministic across two runs.\n"
            f"Run1:\n{run1.stdout}\n\nRun2:\n{run2.stdout}"
        )
        assert run1.returncode == run2.returncode, "Return codes differ across runs"


# ---------------------------------------------------------------------------
# --verbose flag test
# ---------------------------------------------------------------------------

class TestVerboseFlag:
    def test_verbose_flag_accepted(self, good_repo: Path) -> None:
        result = _run_scanner(good_repo, ["--verbose"])
        assert result.returncode in (0, 1), (
            f"--verbose should not cause exit code 2; got {result.returncode}"
        )
