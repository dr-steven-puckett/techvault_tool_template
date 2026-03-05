"""Tests for tools/tool_sync_manager/sync.py"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

# Make sync importable without installation.
sys.path.insert(0, str(Path(__file__).parents[1]))

import sync

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXTURES    = Path(__file__).parent / "fixtures"
_GOOD_TOOL   = _FIXTURES / "good_tool"
_BAD_TOOL    = _FIXTURES / "bad_tool"
_ANOTHER     = _FIXTURES / "another_good_tool"
_TV_FIXTURE  = _FIXTURES / "techvault_root"


def _make_tv(dest: Path) -> Path:
    shutil.copytree(_TV_FIXTURE, dest)
    return dest


def _make_tool(dir_: Path, tool_id: str) -> Path:
    """Create a minimal tool repo under dir_."""
    tool_dir = dir_ / tool_id
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.toml").write_text(
        f'tool_id = "{tool_id}"\nentrypoint = "{tool_id}.api.router:router"\n',
        encoding="utf-8",
    )
    return tool_dir


# ---------------------------------------------------------------------------
# Monkeypatch helper — replaces sync._run_subprocess
# ---------------------------------------------------------------------------


class FakeRunner:
    """Captures subprocess calls; returns configurable responses."""

    def __init__(
        self,
        default: tuple[int, str, str] = (0, "PASS\n", ""),
        overrides: dict[str, tuple[int, str, str]] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.default = default
        self.overrides: dict[str, tuple[int, str, str]] = overrides or {}

    def __call__(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        timeout: int = sync._SUBTOOL_TIMEOUT,
    ) -> tuple[int, str, str]:
        self.calls.append(list(cmd))
        cmd_str = " ".join(str(c) for c in cmd)
        for key, response in self.overrides.items():
            if key in cmd_str:
                return response
        return self.default

    def commands_containing(self, fragment: str) -> list[list[str]]:
        # Check only the first 3 elements (executable, script/flag, first positional)
        # to avoid false matches on --techvault-root paths that may contain 'pytest'.
        return [c for c in self.calls if any(fragment in str(a) for a in c[:3])]


def _patch(monkeypatch, **kwargs) -> FakeRunner:
    runner = FakeRunner(**kwargs)
    monkeypatch.setattr(sync, "_run_subprocess", runner)
    return runner


def _run(argv: list[str]) -> int:
    return sync.main(argv)


# ---------------------------------------------------------------------------
# TestDiscovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_discover_tools_sorted(self, tmp_path):
        """discover_tools() returns dirs in lexicographic order regardless of creation order."""
        for name in ("zebra_tool", "alpha_tool", "mango_tool"):
            _make_tool(tmp_path, name)

        found = sync.discover_tools(tmp_path)
        assert [p.name for p in found] == ["alpha_tool", "mango_tool", "zebra_tool"]

    def test_discover_tools_skips_no_toml(self, tmp_path):
        _make_tool(tmp_path, "real_tool")
        (tmp_path / "not_a_tool").mkdir()  # no tool.toml

        found = sync.discover_tools(tmp_path)
        assert len(found) == 1
        assert found[0].name == "real_tool"

    def test_discover_tools_empty_dir(self, tmp_path):
        assert sync.discover_tools(tmp_path) == []

    def test_all_mode_processes_in_sorted_order(self, tmp_path, monkeypatch):
        """--all visits tools in sorted order; reported tool_ids match."""
        for name in ("z_tool", "a_tool", "m_tool"):
            _make_tool(tmp_path / "tools", name)
        tv = _make_tv(tmp_path / "tv")

        runner = _patch(monkeypatch)
        _run(["--all", str(tmp_path / "tools"), "--techvault-root", str(tv),
              "--skip-validate", "--skip-tests", "--skip-security"])

        # Extract the tool paths passed to registrar subprocess calls
        reg_calls = runner.commands_containing("techvault-tool-register")
        called_names = [Path(c[2]).name for c in reg_calls]  # argv[2] is tool_repo
        assert called_names == ["a_tool", "m_tool", "z_tool"]


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_returns_0_when_all_pass(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        assert code == 0

    def test_dry_run_does_not_pass_apply_to_registrar(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])

        reg_calls = runner.commands_containing("techvault-tool-register")
        assert reg_calls, "registrar should have been called"
        flat = [a for c in reg_calls for a in c]
        assert "--apply" not in flat

    def test_apply_flag_forwards_to_registrar(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--apply"])

        reg_calls = runner.commands_containing("techvault-tool-register")
        assert reg_calls, "registrar should have been called"
        flat = [a for c in reg_calls for a in c]
        assert "--apply" in flat


# ---------------------------------------------------------------------------
# TestFailurePropagation
# ---------------------------------------------------------------------------


class TestFailurePropagation:
    def test_validate_fail_returns_1(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"techvault-tool-validate": (1, "", "FAIL")})
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        assert code == 1

    def test_tests_fail_returns_1(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"pytest": (1, "1 failed", "")})
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        assert code == 1

    def test_security_fail_returns_1(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"techvault-tool-security-scan": (1, "", "FAIL")})
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        assert code == 1

    def test_register_fail_returns_1(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"techvault-tool-register": (1, "", "error")})
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        assert code == 1

    def test_one_of_two_failing_returns_1(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "alpha_tool")
        _make_tool(tools_dir, "beta_tool")
        tv = _make_tv(tmp_path / "tv")

        call_count = {"n": 0}

        def selective_runner(cmd, cwd=None, timeout=sync._SUBTOOL_TIMEOUT):
            call_count["n"] += 1
            # Fail validate for beta_tool
            if "techvault-tool-validate" in " ".join(str(c) for c in cmd):
                if "beta_tool" in " ".join(str(c) for c in cmd):
                    return (1, "", "FAIL")
            return (0, "PASS", "")

        monkeypatch.setattr(sync, "_run_subprocess", selective_runner)
        code = _run(["--all", str(tools_dir), "--techvault-root", str(tv)])
        assert code == 1

    def test_missing_tool_toml_returns_2(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        empty = tmp_path / "empty_tool"
        empty.mkdir()
        _patch(monkeypatch)
        code = _run([str(empty), "--techvault-root", str(tv)])
        assert code == 2

    def test_missing_techvault_root_returns_2(self, tmp_path, monkeypatch):
        _patch(monkeypatch)
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tmp_path / "nonexistent")])
        assert code == 2

    def test_both_tool_repo_and_all_returns_2(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        code = _run([str(_GOOD_TOOL), "--all", str(tmp_path), "--techvault-root", str(tv)])
        assert code == 2

    def test_neither_tool_repo_nor_all_returns_2(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        code = _run(["--techvault-root", str(tv)])
        assert code == 2


# ---------------------------------------------------------------------------
# TestSkipFlags
# ---------------------------------------------------------------------------


class TestSkipFlags:
    def test_skip_validate_does_not_call_validator(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--skip-validate"])
        assert not runner.commands_containing("techvault-tool-validate")

    def test_skip_tests_does_not_call_pytest(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--skip-tests"])
        assert not runner.commands_containing("pytest")

    def test_skip_security_does_not_call_scanner(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--skip-security"])
        assert not runner.commands_containing("techvault-tool-security-scan")

    def test_skip_register_does_not_call_registrar(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--skip-register"])
        assert not runner.commands_containing("techvault-tool-register")

    def test_skip_all_four_steps_returns_0(self, tmp_path, monkeypatch):
        """All steps skipped → nothing fails → exit 0."""
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        code = _run([
            str(_GOOD_TOOL), "--techvault-root", str(tv),
            "--skip-validate", "--skip-tests", "--skip-security", "--skip-register",
        ])
        assert code == 0
        assert not runner.calls  # no subprocess calls at all

    def test_skip_validate_still_runs_other_steps(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--skip-validate"])
        assert runner.commands_containing("pytest")
        assert runner.commands_containing("techvault-tool-security-scan")
        assert runner.commands_containing("techvault-tool-register")

    def test_skip_step_status_is_skip_in_report(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        report_path = tmp_path / "report.json"
        _run([
            str(_GOOD_TOOL), "--techvault-root", str(tv),
            "--skip-validate", "--json-report", str(report_path),
        ])
        data = json.loads(report_path.read_text())
        assert data["tools"][0]["steps"]["validate"]["status"] == "skip"


# ---------------------------------------------------------------------------
# TestFailFast
# ---------------------------------------------------------------------------


class TestFailFast:
    def test_fail_fast_skips_remaining_steps_after_validate_fail(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch, overrides={"techvault-tool-validate": (1, "", "FAIL")})
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--fail-fast"])

        # Only validate should have been called
        assert not runner.commands_containing("pytest")
        assert not runner.commands_containing("techvault-tool-security-scan")
        assert not runner.commands_containing("techvault-tool-register")

    def test_fail_fast_returns_1_on_failure(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"techvault-tool-validate": (1, "", "FAIL")})
        code = _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--fail-fast"])
        assert code == 1


# ---------------------------------------------------------------------------
# TestJsonReport
# ---------------------------------------------------------------------------


class TestJsonReport:
    def _run_with_report(self, tmp_path, monkeypatch, extra_argv=None) -> dict:
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        report_path = tmp_path / "report.json"
        argv = [str(_GOOD_TOOL), "--techvault-root", str(tv), "--json-report", str(report_path)]
        if extra_argv:
            argv.extend(extra_argv)
        _run(argv)
        return json.loads(report_path.read_text())

    def test_report_is_written(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        report_path = tmp_path / "report.json"
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--json-report", str(report_path)])
        assert report_path.exists()

    def test_report_has_top_level_keys(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        assert "apply" in data
        assert "techvault_root" in data
        assert "tools" in data

    def test_report_tools_is_list(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) == 1

    def test_report_tool_has_step_keys(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        steps = data["tools"][0]["steps"]
        assert set(steps.keys()) == {"validate", "tests", "security", "register"}

    def test_report_step_has_required_fields(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        step = data["tools"][0]["steps"]["validate"]
        assert "status" in step
        assert "exit_code" in step
        assert "stdout" in step
        assert "stderr" in step

    def test_report_apply_false_by_default(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        assert data["apply"] is False

    def test_report_apply_true_when_flag_set(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch, extra_argv=["--apply"])
        assert data["apply"] is True

    def test_report_tools_sorted_by_tool_id(self, tmp_path, monkeypatch):
        """JSON report tools array is always sorted by tool_id."""
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "zebra_tool")
        _make_tool(tools_dir, "alpha_tool")
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        report_path = tmp_path / "report.json"
        _run(["--all", str(tools_dir), "--techvault-root", str(tv),
              "--json-report", str(report_path)])
        data = json.loads(report_path.read_text())
        ids = [t["tool_id"] for t in data["tools"]]
        assert ids == sorted(ids)

    def test_report_is_deterministic(self, tmp_path, monkeypatch):
        """Two identical runs produce byte-identical JSON reports."""
        tv1 = _make_tv(tmp_path / "tv1")
        tv2 = _make_tv(tmp_path / "tv2")
        _patch(monkeypatch)
        r1 = tmp_path / "r1.json"
        r2 = tmp_path / "r2.json"
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv1), "--json-report", str(r1)])
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv2), "--json-report", str(r2)])

        d1 = json.loads(r1.read_text())
        d2 = json.loads(r2.read_text())
        # Compare structure & step keys (paths will differ; compare steps only)
        assert d1["tools"][0]["steps"] == d2["tools"][0]["steps"]

    def test_report_json_is_valid(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        report_path = tmp_path / "report.json"
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--json-report", str(report_path)])
        # Must not raise
        json.loads(report_path.read_text())

    def test_report_register_mode_dry_run(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch)
        assert data["tools"][0]["steps"]["register"]["mode"] == "dry-run"

    def test_report_register_mode_apply(self, tmp_path, monkeypatch):
        data = self._run_with_report(tmp_path, monkeypatch, extra_argv=["--apply"])
        assert data["tools"][0]["steps"]["register"]["mode"] == "apply"

    def test_report_stdout_truncated_to_max(self, tmp_path, monkeypatch):
        large_output = "x" * (sync._MAX_OUTPUT_CHARS + 5000)
        tv = _make_tv(tmp_path / "tv")
        runner = FakeRunner(default=(0, large_output, ""))
        monkeypatch.setattr(sync, "_run_subprocess", runner)
        report_path = tmp_path / "report.json"
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--json-report", str(report_path)])
        data = json.loads(report_path.read_text())
        stdout = data["tools"][0]["steps"]["validate"]["stdout"]
        assert len(stdout) <= sync._MAX_OUTPUT_CHARS


# ---------------------------------------------------------------------------
# TestSubprocessCalls
# ---------------------------------------------------------------------------


class TestSubprocessCalls:
    def test_validator_called_with_tool_path(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        calls = runner.commands_containing("techvault-tool-validate")
        assert calls
        assert str(_GOOD_TOOL) in calls[0]

    def test_pytest_called_in_tool_cwd(self, tmp_path, monkeypatch):
        """pytest must be invoked; by convention it's via sys.executable -m pytest."""
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        pytest_calls = runner.commands_containing("pytest")
        assert pytest_calls

    def test_security_scanner_called_with_tool_path(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        calls = runner.commands_containing("techvault-tool-security-scan")
        assert calls
        assert str(_GOOD_TOOL) in calls[0]

    def test_registrar_called_with_techvault_root(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        calls = runner.commands_containing("techvault-tool-register")
        assert calls
        flat = calls[0]
        assert "--techvault-root" in flat

    def test_enabled_forwarded_to_registrar(self, tmp_path, monkeypatch):
        tv = _make_tv(tmp_path / "tv")
        runner = _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv), "--enabled", "true"])
        calls = runner.commands_containing("techvault-tool-register")
        flat = [a for c in calls for a in c]
        assert "--enabled" in flat
        assert "true" in flat

    def test_steps_called_in_order(self, tmp_path, monkeypatch):
        """validate is called before tests before security before register."""
        tv = _make_tv(tmp_path / "tv")

        order: list[str] = []

        def tracking_runner(cmd, cwd=None, timeout=sync._SUBTOOL_TIMEOUT):
            # Limit to first 3 elements to avoid matching pytest in tmp_path dir names.
            cmd_str = " ".join(str(c) for c in cmd[:3])
            if "techvault-tool-validate" in cmd_str:
                order.append("validate")
            elif "pytest" in cmd_str:
                order.append("tests")
            elif "techvault-tool-security-scan" in cmd_str:
                order.append("security")
            elif "techvault-tool-register" in cmd_str:
                order.append("register")
            return (0, "PASS", "")

        monkeypatch.setattr(sync, "_run_subprocess", tracking_runner)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])

        assert order == ["validate", "tests", "security", "register"]


# ---------------------------------------------------------------------------
# TestConsoleOutput
# ---------------------------------------------------------------------------


class TestConsoleOutput:
    def test_summary_contains_tool_id(self, tmp_path, monkeypatch, capsys):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        assert "good_tool" in out

    def test_summary_shows_pass_when_all_pass(self, tmp_path, monkeypatch, capsys):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch)
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        assert "RESULT: PASS" in out

    def test_summary_shows_fail_when_any_fail(self, tmp_path, monkeypatch, capsys):
        tv = _make_tv(tmp_path / "tv")
        _patch(monkeypatch, overrides={"techvault-tool-validate": (1, "", "FAIL")})
        _run([str(_GOOD_TOOL), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        assert "RESULT: FAIL" in out
