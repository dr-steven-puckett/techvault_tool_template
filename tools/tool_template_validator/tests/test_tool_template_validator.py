"""Tests for tools/tool_template_validator/validator.py — --check-catalog flag."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add tool_template_validator/ and tools/ to sys.path.
sys.path.insert(0, str(Path(__file__).parents[1]))   # tools/tool_template_validator/
sys.path.insert(0, str(Path(__file__).parents[2]))   # tools/ (for tool_common)

import validator  # type: ignore
from tool_common.catalog import generate_catalog  # type: ignore
from tool_common.report import canonical_json  # type: ignore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_launcher(tool_dir: Path, name: str = "techvault-tool-fake") -> None:
    (tool_dir / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")


def _setup_tools_dir(base: Path, tool_names: list[str]) -> Path:
    """Create a tools/ dir with minimal valid tool subdirs."""
    tools_dir = base / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    for name in tool_names:
        d = tools_dir / name
        d.mkdir()
        _make_launcher(d)
        (d / "tool.toml").write_text(f'tool_id = "{name}"\n', encoding="utf-8")
    return tools_dir


def _write_catalog(tools_dir: Path, catalog_path: Path) -> None:
    """Write the canonical catalog for *tools_dir* to *catalog_path*."""
    data = generate_catalog(tools_dir)
    catalog_path.write_text(canonical_json(data), encoding="utf-8")


def _run_check_catalog(tools_root: Path, catalog_path: Path) -> dict:
    """Call validator.check_catalog and return the result dict."""
    return validator.check_catalog(tools_root, catalog_path)


# ---------------------------------------------------------------------------
# TestCheckCatalog
# ---------------------------------------------------------------------------


class TestCheckCatalog:
    def test_passes_when_catalog_matches(self, tmp_path: Path) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool", "beta_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        _write_catalog(tools_dir, catalog_path)

        result = _run_check_catalog(tools_dir, catalog_path)
        assert result["status"] == "match"
        assert result["catalog_mismatch"] is False

    def test_fails_when_catalog_differs(self, tmp_path: Path) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool", "beta_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        # Write stale catalog (only one tool).
        stale = {"tools": [{"id": "alpha_tool", "path": "tools/alpha_tool"}], "version": 1}
        catalog_path.write_text(canonical_json(stale), encoding="utf-8")

        result = _run_check_catalog(tools_dir, catalog_path)
        assert result["status"] == "mismatch"
        assert result["catalog_mismatch"] is True
        assert "first_diff_index" in result

    def test_fails_when_file_missing(self, tmp_path: Path) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool"])
        catalog_path = tmp_path / "nonexistent.catalog.json"

        result = _run_check_catalog(tools_dir, catalog_path)
        assert result["status"] == "file_missing"
        assert result["catalog_mismatch"] is True

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        """Two identical runs must produce byte-identical JSON outputs."""
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool", "beta_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        _write_catalog(tools_dir, catalog_path)

        r1 = _run_check_catalog(tools_dir, catalog_path)
        r2 = _run_check_catalog(tools_dir, catalog_path)
        assert canonical_json(r1) == canonical_json(r2)

    def test_exit_0_on_match_via_main(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        _write_catalog(tools_dir, catalog_path)

        monkeypatch.setattr(validator, "_TOOLS_ROOT", tools_dir)
        monkeypatch.setattr(validator, "_CATALOG_PATH", catalog_path)

        code = validator.main(["--check-catalog"])
        assert code == 0

    def test_exit_1_on_mismatch_via_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool", "beta_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        # Write a catalog that doesn't match (missing beta_tool).
        stale = {"tools": [{"id": "alpha_tool", "path": "tools/alpha_tool"}], "version": 1}
        catalog_path.write_text(canonical_json(stale), encoding="utf-8")

        monkeypatch.setattr(validator, "_TOOLS_ROOT", tools_dir)
        monkeypatch.setattr(validator, "_CATALOG_PATH", catalog_path)

        code = validator.main(["--check-catalog"])
        assert code == 1

    def test_check_catalog_output_contains_status_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        _write_catalog(tools_dir, catalog_path)

        monkeypatch.setattr(validator, "_TOOLS_ROOT", tools_dir)
        monkeypatch.setattr(validator, "_CATALOG_PATH", catalog_path)

        validator.main(["--check-catalog"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "status" in data

    def test_first_diff_index_is_deterministic(self, tmp_path: Path) -> None:
        """First differing byte index is stable across calls."""
        tools_dir = _setup_tools_dir(tmp_path, ["alpha_tool", "beta_tool"])
        catalog_path = tmp_path / "tools.catalog.json"
        # Write deliberately wrong content.
        catalog_path.write_text('{"tools":[],"version":99}\n', encoding="utf-8")

        r1 = _run_check_catalog(tools_dir, catalog_path)
        r2 = _run_check_catalog(tools_dir, catalog_path)
        assert r1.get("first_diff_index") == r2.get("first_diff_index")
