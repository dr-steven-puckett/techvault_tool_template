"""Tests for tools/tool_template_version/versioner.py

Covers:
    1.  --check with missing tool.toml -> TOML_MISSING, exit 2
    2.  --check with missing [template] -> STAMP_MISSING WARN, exit 1
    3.  --check with valid stamp -> exit 0, no findings
    4.  --write creates stamp with stamp_source="manual"
    5.  --write then --check -> exit 0 (no findings)
    6.  --write is deterministic (run twice, compare tool.toml bytes)
    7.  --write with missing manifest -> MANIFEST_MISSING, exit 2, wrote_stamp=False
    8.  --write with manifest missing template_version -> MANIFEST_INVALID, exit 2
    9.  --write populates report.template from written tool.toml
    10. --manifest override uses specified manifest path
    11. Report has mode="check" or mode="write"
    12. Report has wrote_stamp bool key
    13. --check report is read-only (tool.toml bytes unchanged)
    14. Report JSON has required base contract keys (§7.3)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomllib

import versioner
from versioner import run_check, run_write
from tool_common.stamp import compute_manifest_sha256

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SAMPLE_MANIFEST: dict = {
    "policies": {"response_hash_enabled_default": False},
    "required_root_files": ["README.md", "tool.toml"],
    "template_version": "2.0.0",
}

_MINIMAL_TOML = 'tool_id = "sample"\nname = "sample"\nversion = "0.1.0"\n'


def _write_manifest(path: Path, data: dict | None = None) -> Path:
    p = path / "TEMPLATE_MANIFEST.json"
    p.write_text(
        json.dumps(data or _SAMPLE_MANIFEST, indent=2) + "\n", encoding="utf-8"
    )
    return p


def _write_toml(path: Path, content: str = _MINIMAL_TOML) -> Path:
    p = path / "tool.toml"
    p.write_text(content, encoding="utf-8")
    return p


def _make_tool_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sample_tool"
    d.mkdir()
    return d


def _valid_stamp_toml(manifest: Path) -> str:
    h = compute_manifest_sha256(manifest)
    return (
        _MINIMAL_TOML
        + f'\n[template]\nstamp_source = "create"\n'
        f'template_manifest_hash = "{h}"\n'
        f'template_version = "2.0.0"\n'
    )


# ---------------------------------------------------------------------------
# Tests: --check mode
# ---------------------------------------------------------------------------


class TestCheckMode:
    def test_check_missing_tool_toml_returns_toml_missing_exit2(self, tmp_path: Path) -> None:  # 1
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        report, code = run_check(tool_dir, manifest)
        assert code == 2
        codes = [f["code"] for f in report["findings"]]
        assert "TOML_MISSING" in codes

    def test_check_missing_stamp_is_warn_exit1(self, tmp_path: Path) -> None:  # 2
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, code = run_check(tool_dir, manifest)
        assert code == 1
        stamp_findings = [f for f in report["findings"] if f["code"] == "STAMP_MISSING"]
        assert stamp_findings
        assert stamp_findings[0]["level"] == "WARN"

    def test_check_valid_stamp_exit0(self, tmp_path: Path) -> None:  # 3
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir, _valid_stamp_toml(manifest))
        report, code = run_check(tool_dir, manifest)
        assert code == 0
        assert report["findings"] == []

    def test_check_mode_is_readonly(self, tmp_path: Path) -> None:  # 13
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        before = (tool_dir / "tool.toml").read_bytes()
        run_check(tool_dir, manifest)
        after = (tool_dir / "tool.toml").read_bytes()
        assert before == after

    def test_check_report_has_mode_check(self, tmp_path: Path) -> None:  # 11a
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest)
        assert report["mode"] == "check"

    def test_check_report_has_wrote_stamp_false(self, tmp_path: Path) -> None:  # 12a
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest)
        assert report["wrote_stamp"] is False


# ---------------------------------------------------------------------------
# Tests: --write mode
# ---------------------------------------------------------------------------


class TestWriteMode:
    def test_write_creates_manual_stamp(self, tmp_path: Path) -> None:  # 4
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, code = run_write(tool_dir, manifest)
        assert report["wrote_stamp"] is True
        data = tomllib.loads((tool_dir / "tool.toml").read_text(encoding="utf-8"))
        assert data["template"]["stamp_source"] == "manual"

    def test_write_then_check_exits0(self, tmp_path: Path) -> None:  # 5
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        run_write(tool_dir, manifest)
        check_report, code = run_check(tool_dir, manifest)
        assert code == 0
        assert check_report["findings"] == []

    def test_write_is_deterministic(self, tmp_path: Path) -> None:  # 6
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        run_write(tool_dir, manifest)
        bytes1 = (tool_dir / "tool.toml").read_bytes()
        run_write(tool_dir, manifest)
        bytes2 = (tool_dir / "tool.toml").read_bytes()
        assert bytes1 == bytes2

    def test_write_missing_manifest_exits2_no_stamp(self, tmp_path: Path) -> None:  # 7
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        absent = tmp_path / "no_manifest.json"
        report, code = run_write(tool_dir, absent)
        assert code == 2
        assert report["wrote_stamp"] is False
        codes = [f["code"] for f in report["findings"]]
        assert "MANIFEST_MISSING" in codes

    def test_write_manifest_missing_template_version_exits2(self, tmp_path: Path) -> None:  # 8
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        # Manifest without template_version field
        bad_manifest = _write_manifest(tmp_path, {"policies": {}})
        report, code = run_write(tool_dir, bad_manifest)
        assert code == 2
        codes = [f["code"] for f in report["findings"]]
        assert "MANIFEST_INVALID" in codes
        assert report["wrote_stamp"] is False

    def test_write_populates_template_in_report(self, tmp_path: Path) -> None:  # 9
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, _ = run_write(tool_dir, manifest)
        assert report["template"] is not None
        assert report["template"]["stamp_source"] == "manual"
        assert report["template"]["template_version"] == "2.0.0"

    def test_write_manifest_override_uses_custom_manifest(self, tmp_path: Path) -> None:  # 10
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        # Create a custom manifest with a different version
        custom_manifest = tmp_path / "custom.json"
        custom_manifest.write_text(
            json.dumps({"template_version": "99.0.0"}, indent=2) + "\n",
            encoding="utf-8",
        )
        run_write(tool_dir, custom_manifest)
        data = tomllib.loads((tool_dir / "tool.toml").read_text(encoding="utf-8"))
        assert data["template"]["template_version"] == "99.0.0"
        expected_hash = compute_manifest_sha256(custom_manifest)
        assert data["template"]["template_manifest_hash"] == expected_hash

    def test_write_report_has_mode_write(self, tmp_path: Path) -> None:  # 11b
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, _ = run_write(tool_dir, manifest)
        assert report["mode"] == "write"

    def test_write_report_has_wrote_stamp_bool(self, tmp_path: Path) -> None:  # 12b
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, _ = run_write(tool_dir, manifest)
        assert isinstance(report["wrote_stamp"], bool)
        assert report["wrote_stamp"] is True


# ---------------------------------------------------------------------------
# Tests: common report contract
# ---------------------------------------------------------------------------


class TestReportContract:
    _BASE_KEYS = {
        "computed_manifest_hash",
        "expected_manifest_hash",
        "findings",
        "manifest_path",
        "mode",
        "strict",
        "template",
        "tool_path",
        "wrote_stamp",
    }

    def test_check_report_has_required_keys(self, tmp_path: Path) -> None:  # 14a
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest)
        assert self._BASE_KEYS.issubset(set(report.keys()))

    def test_write_report_has_required_keys(self, tmp_path: Path) -> None:  # 14b
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_write(tool_dir, manifest)
        assert self._BASE_KEYS.issubset(set(report.keys()))

    def test_report_json_is_canonical(self, tmp_path: Path) -> None:
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest)
        canonical = (
            json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        )
        assert versioner._canonical_json(report) == canonical
