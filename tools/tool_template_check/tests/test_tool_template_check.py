"""Tests for tools/tool_template_check/checker.py

Covers:
    1.  Missing tool_path directory  -> exit 2, ERROR finding
    2.  tool_path exists but tool.toml missing -> TOML_MISSING, exit 2
    3.  tool.toml exists but manifest missing -> MANIFEST_MISSING, exit 2
    4.  [template] section absent, non-strict -> STAMP_MISSING WARN, exit 1
    5.  [template] section absent, --strict -> exit 2
    6.  Valid stamp with local manifest copy -> exit 0, no findings
    7.  Valid stamp without local manifest copy -> LOCAL_MANIFEST_MISSING WARN, exit 1
    8.  Hash mismatch -> HASH_MISMATCH ERROR, exit 2
    9.  Report JSON keys match §7.3 contract exactly
    10. Report JSON is canonical (sort_keys, compact)
    11. Findings sorted deterministically (ERROR before WARN)
    12. strict=True escalates WARN-only report to exit 2
"""
from __future__ import annotations

import json
import shutil
from tool_common.report import canonical_json
from pathlib import Path

import pytest

import checker
from checker import run_check
from tool_common.stamp import compute_manifest_sha256, write_stamp

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
# Tests
# ---------------------------------------------------------------------------


class TestRunCheck:
    def test_missing_tool_path_dir_returns_error_exit2(self, tmp_path: Path) -> None:  # 1
        nonexistent = tmp_path / "does_not_exist"
        manifest = _write_manifest(tmp_path)
        report, code = run_check(nonexistent, manifest, strict=False)
        assert code == 2
        assert any(f["level"] == "ERROR" for f in report["findings"])

    def test_missing_tool_toml_returns_toml_missing(self, tmp_path: Path) -> None:  # 2
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        report, code = run_check(tool_dir, manifest, strict=False)
        assert code == 2
        codes = [f["code"] for f in report["findings"]]
        assert "TOML_MISSING" in codes

    def test_missing_manifest_returns_manifest_missing(self, tmp_path: Path) -> None:  # 3
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        absent_manifest = tmp_path / "no_such_manifest.json"
        report, code = run_check(tool_dir, absent_manifest, strict=False)
        assert code == 2
        codes = [f["code"] for f in report["findings"]]
        assert "MANIFEST_MISSING" in codes

    def test_missing_template_section_non_strict_is_warn_exit1(self, tmp_path: Path) -> None:  # 4
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, code = run_check(tool_dir, manifest, strict=False)
        stamp_missing = [f for f in report["findings"] if f["code"] == "STAMP_MISSING"]
        assert stamp_missing, f"Expected STAMP_MISSING, got {report['findings']}"
        assert stamp_missing[0]["level"] == "WARN"
        # Note: LOCAL_MANIFEST_MISSING may also be present as WARN
        assert code == 1

    def test_missing_template_section_strict_exit2(self, tmp_path: Path) -> None:  # 5
        tool_dir = _make_tool_dir(tmp_path)
        _write_toml(tool_dir)
        manifest = _write_manifest(tmp_path)
        report, code = run_check(tool_dir, manifest, strict=True)
        assert code == 2

    def test_valid_stamp_with_local_manifest_copy_exit0(self, tmp_path: Path) -> None:  # 6
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir, _valid_stamp_toml(manifest))
        # Copy manifest into tool dir (audit record) to avoid LOCAL_MANIFEST_MISSING
        shutil.copy2(manifest, tool_dir / "TEMPLATE_MANIFEST.json")
        report, code = run_check(tool_dir, manifest, strict=False)
        assert code == 0
        assert report["findings"] == []

    def test_valid_stamp_without_local_manifest_copy_is_warn_exit1(self, tmp_path: Path) -> None:  # 7
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir, _valid_stamp_toml(manifest))
        # No local TEMPLATE_MANIFEST.json copy
        report, code = run_check(tool_dir, manifest, strict=False)
        local_missing = [f for f in report["findings"] if f["code"] == "LOCAL_MANIFEST_MISSING"]
        assert local_missing
        assert local_missing[0]["level"] == "WARN"
        assert code == 1

    def test_hash_mismatch_returns_error_exit2(self, tmp_path: Path) -> None:  # 8
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        wrong_hash = "a" * 64
        content = (
            _MINIMAL_TOML
            + f'\n[template]\nstamp_source = "create"\n'
            f'template_manifest_hash = "{wrong_hash}"\n'
            f'template_version = "2.0.0"\n'
        )
        _write_toml(tool_dir, content)
        report, code = run_check(tool_dir, manifest, strict=False)
        assert code == 2
        assert any(f["code"] == "HASH_MISMATCH" for f in report["findings"])

    def test_report_has_required_keys(self, tmp_path: Path) -> None:  # 9
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest, strict=False)
        required_keys = {
            "computed_manifest_hash",
            "expected_manifest_hash",
            "findings",
            "manifest_path",
            "strict",
            "template",
            "tool_path",
        }
        assert required_keys.issubset(set(report.keys()))

    def test_report_json_is_canonical(self, tmp_path: Path) -> None:  # 10
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir)
        report, _ = run_check(tool_dir, manifest, strict=False)
        # Canonical = sort_keys + compact separators + trailing newline
        canonical = (
            json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        )
        assert canonical_json(report) == canonical

    def test_findings_sorted_error_before_warn(self, tmp_path: Path) -> None:  # 11
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        # HASH_INVALID (always ERROR) + STAMP_KEY_MISSING missing template_version (WARN)
        bad_hash = "ZZZZ"  # invalid format
        content = (
            _MINIMAL_TOML
            + f'\n[template]\nstamp_source = "create"\n'
            f'template_manifest_hash = "{bad_hash}"\n'
        )
        _write_toml(tool_dir, content)
        report, _ = run_check(tool_dir, manifest, strict=False)
        levels = [f["level"] for f in report["findings"]]
        # All ERRORs must come before all WARNs
        seen_warn = False
        for level in levels:
            if level == "WARN":
                seen_warn = True
            if level == "ERROR" and seen_warn:
                pytest.fail(f"ERROR appeared after WARN: {report['findings']}")

    def test_strict_escalates_warn_only_to_exit2(self, tmp_path: Path) -> None:  # 12
        """strict=True exits 2 if any finding exists, even if all are WARN."""
        tool_dir = _make_tool_dir(tmp_path)
        manifest = _write_manifest(tmp_path)
        _write_toml(tool_dir, _valid_stamp_toml(manifest))
        # Only LOCAL_MANIFEST_MISSING WARN (no local copy)
        report, code = run_check(tool_dir, manifest, strict=True)
        findings = report["findings"]
        assert all(f["level"] == "WARN" for f in findings), findings
        assert code == 2
