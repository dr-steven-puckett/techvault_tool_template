"""Tests for tools/tool_fleet_manager/fleet.py

Covers:
    1.  Catalog validation — unsorted tools list => exit 2, CATALOG_UNSORTED
    2.  Catalog validation — duplicate id => exit 2, CATALOG_DUPLICATE_ID
    3.  Results ordering — sorted by (tool_id, step) ascending
    4.  Canonical JSON output stability — byte-identical across two runs
    5.  Summary counts — mix of exit codes 0/1/2
    6.  Strict propagation — strict=True forwarded to template-check step
    7.  Per-tool TOML_MISSING error — tool dir present but no tool.toml
    8.  Per-tool dir-missing error — tool dir absent
    9.  Unknown step produces error result (exit 2)
    10. Summary total_tools / total_steps counts
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import fleet  # type: ignore
from fleet import CatalogError, canonical_json, read_catalog, run_fleet  # type: ignore
from tool_common.report import canonical_json as tc_canonical_json  # type: ignore

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MANIFEST_DATA: dict = {"template_version": "1.0.0"}


def _make_tool_dir(parent: Path, tool_id: str) -> Path:
    """Create a minimal tool directory containing tool.toml."""
    d = parent / tool_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "tool.toml").write_text(f'tool_id = "{tool_id}"\n', encoding="utf-8")
    return d


def _make_catalog(
    catalog_dir: Path,
    tools: list[dict],
    *,
    filename: str = "catalog.json",
) -> Path:
    """Write a catalog JSON file (NOT pre-sorted — caller controls order)."""
    obj = {"version": 1, "tools": tools}
    p = catalog_dir / filename
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _make_manifest(tmp_path: Path) -> Path:
    """Write a minimal TEMPLATE_MANIFEST.json."""
    p = tmp_path / "TEMPLATE_MANIFEST.json"
    p.write_text(canonical_json(_MANIFEST_DATA), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1 & 2 — Catalog validation
# ---------------------------------------------------------------------------


class TestCatalogValidation:
    def test_unsorted_tools_list_gives_exit_2(self, tmp_path: Path) -> None:
        # Deliberately place z_tool before a_tool (wrong sort order).
        catalog_path = _make_catalog(
            tmp_path,
            [
                {"id": "z_tool", "path": "tools/z_tool"},
                {"id": "a_tool", "path": "tools/a_tool"},
            ],
        )
        manifest = _make_manifest(tmp_path)
        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )
        assert code == 2
        assert "catalog_error" in report
        assert report["catalog_error"]["code"] == "CATALOG_UNSORTED"
        assert report["results"] == []

    def test_unsorted_error_message_is_stable(self, tmp_path: Path) -> None:
        """The error message text must be deterministic across runs."""
        catalog_path = _make_catalog(
            tmp_path,
            [
                {"id": "z_tool", "path": "tools/z_tool"},
                {"id": "a_tool", "path": "tools/a_tool"},
            ],
        )
        manifest = _make_manifest(tmp_path)
        r1, _ = run_fleet(
            catalog_path=catalog_path, manifest_path=manifest, strict=False,
            steps=["template-check"],
        )
        r2, _ = run_fleet(
            catalog_path=catalog_path, manifest_path=manifest, strict=False,
            steps=["template-check"],
        )
        assert r1["catalog_error"]["message"] == r2["catalog_error"]["message"]
        assert r1["catalog_error"]["code"] == r2["catalog_error"]["code"]

    def test_duplicate_id_gives_exit_2(self, tmp_path: Path) -> None:
        catalog_path = _make_catalog(
            tmp_path,
            [
                {"id": "a_tool", "path": "tools/a_tool"},
                {"id": "a_tool", "path": "tools/b_tool"},
            ],
        )
        manifest = _make_manifest(tmp_path)
        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )
        assert code == 2
        assert report["catalog_error"]["code"] == "CATALOG_DUPLICATE_ID"
        assert report["results"] == []


# ---------------------------------------------------------------------------
# 3 — Results ordering
# ---------------------------------------------------------------------------


class TestResultsOrdering:
    def test_results_sorted_by_tool_id_then_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Results must be sorted by (tool_id, step) regardless of catalog order."""
        tools_base = tmp_path / "tools"
        ids = ["gamma_tool", "alpha_tool", "beta_tool"]
        for tid in ids:
            _make_tool_dir(tools_base, tid)

        # Catalog must be sorted by id (fleet validates this).
        sorted_ids = sorted(ids)
        catalog_tools = [
            {"id": tid, "path": f"tools/{tid}"} for tid in sorted_ids
        ]
        catalog_path = _make_catalog(tmp_path, catalog_tools)
        manifest = _make_manifest(tmp_path)

        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        def _mock_check(
            tool_path: Path, manifest_path: Path, strict: bool
        ) -> tuple[dict, int]:
            return {"mock": "check", "tool": tool_path.name}, 0

        def _mock_version(
            tool_path: Path, manifest_path: Path, strict: bool
        ) -> tuple[dict, int]:
            return {"mock": "version", "tool": tool_path.name}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _mock_check)
        monkeypatch.setattr(fleet, "_step_template_version_check", _mock_version)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-version-check", "template-check"],  # reversed input order
        )

        assert code == 0
        keys = [(r["tool_id"], r["step"]) for r in report["results"]]
        # Must equal the sorted order regardless of input step order.
        assert keys == sorted(keys), f"Results not sorted: {keys}"
        # 3 tools × 2 steps = 6 results
        assert len(keys) == 6

    def test_results_one_tool_two_steps_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "my_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        def _noop(tool_path, manifest_path, strict):
            return {"ok": True}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _noop)
        monkeypatch.setattr(fleet, "_step_template_version_check", _noop)

        report, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-version-check", "template-check"],
        )
        steps_order = [r["step"] for r in report["results"]]
        assert steps_order == sorted(steps_order)


# ---------------------------------------------------------------------------
# 4 — Canonical JSON output stability
# ---------------------------------------------------------------------------


class TestCanonicalJsonStability:
    def test_byte_identical_output_on_same_inputs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "alpha_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "alpha_tool", "path": "tools/alpha_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        def _mock_check(tool_path, manifest_path, strict):
            return {"findings": [], "result": "ok"}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _mock_check)

        kwargs: dict = dict(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )
        r1, _ = run_fleet(**kwargs)
        r2, _ = run_fleet(**kwargs)

        assert canonical_json(r1) == canonical_json(r2)

    def test_canonical_json_matches_tool_common(self) -> None:
        """fleet.canonical_json and tool_common.report.canonical_json must agree."""
        obj = {"b": 2, "a": 1, "z": [3, 1, 2]}
        assert canonical_json(obj) == tc_canonical_json(obj)


# ---------------------------------------------------------------------------
# 5 — Summary counts
# ---------------------------------------------------------------------------


class TestSummaryCounts:
    def test_mixed_exit_codes_counted_correctly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ok=1, warn=1, error=1 when tools return 0, 1, 2 respectively."""
        tools_base = tmp_path / "tools"
        ids = ["a_tool", "b_tool", "c_tool"]
        for tid in ids:
            _make_tool_dir(tools_base, tid)

        catalog_tools = [{"id": tid, "path": f"tools/{tid}"} for tid in ids]
        catalog_path = _make_catalog(tmp_path, catalog_tools)
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        exit_codes = {"a_tool": 0, "b_tool": 1, "c_tool": 2}

        def _mock_check(tool_path, manifest_path, strict):
            return {"tool": tool_path.name}, exit_codes[tool_path.name]

        monkeypatch.setattr(fleet, "_step_template_check", _mock_check)

        report, fleet_code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )

        assert report["summary"]["ok"] == 1
        assert report["summary"]["warn"] == 1
        assert report["summary"]["error"] == 1
        assert fleet_code == 2

    def test_all_ok_fleet_code_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        for tid in ["a_tool", "b_tool"]:
            _make_tool_dir(tools_base, tid)
        catalog_path = _make_catalog(
            tmp_path,
            [{"id": "a_tool", "path": "tools/a_tool"},
             {"id": "b_tool", "path": "tools/b_tool"}],
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fleet, "_step_template_check",
                            lambda tp, mp, s: ({"ok": True}, 0))

        _, fleet_code = run_fleet(
            catalog_path=catalog_path, manifest_path=manifest,
            strict=False, steps=["template-check"],
        )
        assert fleet_code == 0

    def test_warn_only_fleet_code_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "a_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "a_tool", "path": "tools/a_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fleet, "_step_template_check",
                            lambda tp, mp, s: ({"warn": True}, 1))

        _, fleet_code = run_fleet(
            catalog_path=catalog_path, manifest_path=manifest,
            strict=False, steps=["template-check"],
        )
        assert fleet_code == 1

    def test_total_tools_and_steps_in_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        ids = ["a_tool", "b_tool", "c_tool"]
        for tid in ids:
            _make_tool_dir(tools_base, tid)
        catalog_tools = [{"id": tid, "path": f"tools/{tid}"} for tid in ids]
        catalog_path = _make_catalog(tmp_path, catalog_tools)
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        def _noop(tp, mp, s):
            return {}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _noop)
        monkeypatch.setattr(fleet, "_step_template_version_check", _noop)

        report, _ = run_fleet(
            catalog_path=catalog_path, manifest_path=manifest,
            strict=False, steps=["template-check", "template-version-check"],
        )
        assert report["summary"]["total_tools"] == 3
        assert report["summary"]["total_steps"] == 2


# ---------------------------------------------------------------------------
# 6 — Strict propagation
# ---------------------------------------------------------------------------


class TestStrictPropagation:
    def test_strict_true_forwarded_to_template_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "my_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        captured: list[bool] = []

        def _capture_strict(tool_path, manifest_path, strict):
            captured.append(strict)
            return {"ok": True}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _capture_strict)

        run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=True,
            steps=["template-check"],
        )

        assert captured == [True], f"strict was not True: {captured}"

    def test_strict_false_forwarded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "my_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        captured: list[bool] = []

        def _capture_strict(tool_path, manifest_path, strict):
            captured.append(strict)
            return {}, 0

        monkeypatch.setattr(fleet, "_step_template_check", _capture_strict)
        run_fleet(
            catalog_path=catalog_path, manifest_path=manifest,
            strict=False, steps=["template-check"],
        )
        assert captured == [False]


# ---------------------------------------------------------------------------
# 7 — Per-tool TOML_MISSING error
# ---------------------------------------------------------------------------


class TestPerToolErrors:
    def test_tool_dir_present_but_no_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        d = tools_base / "my_tool"
        d.mkdir(parents=True)
        # No tool.toml created.
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )
        assert code == 2
        assert len(report["results"]) == 1
        r = report["results"][0]
        assert r["exit_code"] == 2
        assert r["error"] is not None
        assert r["report"] is None

    def test_tool_dir_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Do not create any tool directory.
        catalog_path = _make_catalog(
            tmp_path, [{"id": "missing_tool", "path": "tools/missing_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check"],
        )
        assert code == 2
        assert report["results"][0]["exit_code"] == 2
        assert report["results"][0]["error"]["type"] == "FileNotFoundError"

    def test_unknown_step_produces_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "my_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["nonexistent-step"],
        )
        assert code == 2
        assert report["results"][0]["exit_code"] == 2
        assert report["results"][0]["error"]["type"] == "ValueError"


# ---------------------------------------------------------------------------
# 11 — Steps header normalisation (B)
# ---------------------------------------------------------------------------


class TestStepsNormalization:
    """Run fleet with steps supplied in different orders; assert determinism."""

    def _two_tool_catalog(self, tmp_path: Path) -> tuple[Path, Path]:
        tools_base = tmp_path / "tools"
        for tid in ["alpha_tool", "beta_tool"]:
            _make_tool_dir(tools_base, tid)
        catalog_path = _make_catalog(
            tmp_path,
            [
                {"id": "alpha_tool", "path": "tools/alpha_tool"},
                {"id": "beta_tool", "path": "tools/beta_tool"},
            ],
        )
        manifest = _make_manifest(tmp_path)
        return catalog_path, manifest

    def test_report_header_steps_is_sorted_regardless_of_input_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._two_tool_catalog(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fleet, "_step_template_check", lambda tp, mp, s: ({}, 0))
        monkeypatch.setattr(fleet, "_step_template_version_check", lambda tp, mp, s: ({}, 0))

        # Pass steps in reversed order.
        report_rev, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-version-check", "template-check"],
        )
        # Pass steps in sorted order.
        report_sorted, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check", "template-version-check"],
        )

        assert report_rev["steps"] == sorted(["template-version-check", "template-check"])
        assert report_rev["steps"] == report_sorted["steps"]

    def test_execution_order_matches_sorted_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._two_tool_catalog(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fleet, "_step_template_check", lambda tp, mp, s: ({}, 0))
        monkeypatch.setattr(fleet, "_step_template_version_check", lambda tp, mp, s: ({}, 0))

        report, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-version-check", "template-check"],  # reversed input
        )

        actual_pairs = [(r["tool_id"], r["step"]) for r in report["results"]]
        assert actual_pairs == sorted(actual_pairs)

    def test_byte_identical_output_regardless_of_step_input_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._two_tool_catalog(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fleet, "_step_template_check", lambda tp, mp, s: ({"result": "ok"}, 0))
        monkeypatch.setattr(fleet, "_step_template_version_check", lambda tp, mp, s: ({"result": "ok"}, 0))

        report_a, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-check", "template-version-check"],
        )
        report_b, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["template-version-check", "template-check"],  # reversed
        )

        assert canonical_json(report_a) == canonical_json(report_b)


# ---------------------------------------------------------------------------
# 12 — Subprocess steps: validate, security-scan, underscore normalization
# ---------------------------------------------------------------------------


class TestSubprocessSteps:
    """validate and security-scan dispatch + underscore-alias normalization."""

    def _single_tool_setup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, Path]:
        tools_base = tmp_path / "tools"
        _make_tool_dir(tools_base, "my_tool")
        catalog_path = _make_catalog(
            tmp_path, [{"id": "my_tool", "path": "tools/my_tool"}]
        )
        manifest = _make_manifest(tmp_path)
        monkeypatch.setattr(fleet, "_WORKSPACE_ROOT", tmp_path)
        return catalog_path, manifest

    def test_validate_step_dispatches_to_step_validate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)
        called: list[str] = []

        def _mock_validate(tool_path: Path, manifest_path: Path, strict: bool):
            called.append(tool_path.name)
            return {"stdout": "ok", "stderr": ""}, 0

        monkeypatch.setattr(fleet, "_step_validate", _mock_validate)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["validate"],
        )
        assert code == 0
        assert called == ["my_tool"]
        assert report["results"][0]["step"] == "validate"

    def test_security_scan_step_dispatches_to_step_security_scan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)
        called: list[str] = []

        def _mock_scan(tool_path: Path, manifest_path: Path, strict: bool):
            called.append(tool_path.name)
            return {"stdout": "PASS", "stderr": ""}, 0

        monkeypatch.setattr(fleet, "_step_security_scan", _mock_scan)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["security-scan"],
        )
        assert code == 0
        assert called == ["my_tool"]
        assert report["results"][0]["step"] == "security-scan"

    def test_underscore_alias_normalizes_to_hyphen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """security_scan (underscore) must normalize to security-scan (hyphen)."""
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)

        def _mock_scan(tool_path, manifest_path, strict):
            return {"stdout": "PASS", "stderr": ""}, 0

        monkeypatch.setattr(fleet, "_step_security_scan", _mock_scan)

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["security_scan"],  # underscore input
        )
        assert code == 0
        # Report header must use normalized hyphen name.
        assert "security-scan" in report["steps"]
        assert "security_scan" not in report["steps"]
        assert report["results"][0]["step"] == "security-scan"

    def test_validate_step_report_has_stdout_stderr_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)

        monkeypatch.setattr(
            fleet, "_step_validate",
            lambda tp, mp, s: ({"stdout": "repo ok", "stderr": ""}, 0),
        )

        report, _ = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["validate"],
        )
        result_report = report["results"][0]["report"]
        assert "stdout" in result_report
        assert "stderr" in result_report

    def test_failed_validate_step_counts_as_warn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)

        monkeypatch.setattr(
            fleet, "_step_validate",
            lambda tp, mp, s: ({"stdout": "FAIL", "stderr": ""}, 1),
        )

        report, fleet_code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["validate"],
        )
        assert fleet_code == 1
        assert report["summary"]["warn"] == 1
        assert report["summary"]["ok"] == 0

    def test_error_security_scan_counts_as_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)

        monkeypatch.setattr(
            fleet, "_step_security_scan",
            lambda tp, mp, s: ({"stdout": "", "stderr": "crash"}, 2),
        )

        report, fleet_code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["security-scan"],
        )
        assert fleet_code == 2
        assert report["summary"]["error"] == 1

    def test_mixed_steps_underscore_and_hyphen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """validate + security_scan + template-check all normalize correctly."""
        catalog_path, manifest = self._single_tool_setup(tmp_path, monkeypatch)

        monkeypatch.setattr(fleet, "_step_validate",
                            lambda tp, mp, s: ({"stdout": "ok", "stderr": ""}, 0))
        monkeypatch.setattr(fleet, "_step_security_scan",
                            lambda tp, mp, s: ({"stdout": "PASS", "stderr": ""}, 0))
        monkeypatch.setattr(fleet, "_step_template_check",
                            lambda tp, mp, s: ({}, 0))

        report, code = run_fleet(
            catalog_path=catalog_path,
            manifest_path=manifest,
            strict=False,
            steps=["validate", "security_scan", "template-check"],
        )
        assert code == 0
        assert report["steps"] == sorted(["validate", "security-scan", "template-check"])
        step_names = {r["step"] for r in report["results"]}
        assert step_names == {"validate", "security-scan", "template-check"}
