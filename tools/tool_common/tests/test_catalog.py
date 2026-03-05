"""Foundation invariant tests for tool_common.catalog."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure tools/ is on sys.path.
sys.path.insert(0, str(Path(__file__).parents[2]))  # tools/

from tool_common.catalog import generate_catalog, load_catalog  # type: ignore
from tool_common.report import canonical_json  # type: ignore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_launcher(tool_dir: Path, name: str = "techvault-tool-fake") -> None:
    (tool_dir / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")


def _make_tool(tools_dir: Path, name: str, *, with_toml: bool = True) -> Path:
    d = tools_dir / name
    d.mkdir(parents=True, exist_ok=True)
    _make_launcher(d)
    if with_toml:
        (d / "tool.toml").write_text(f'tool_id = "{name}"\n', encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# TestGenerateCatalog invariants
# ---------------------------------------------------------------------------


class TestGenerateCatalogInvariants:
    def test_schema_has_version_and_tools(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "alpha")
        result = generate_catalog(tools_dir)
        assert set(result.keys()) == {"version", "tools"}
        assert result["version"] == 1

    def test_tools_entries_have_id_and_path_only(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "alpha")
        result = generate_catalog(tools_dir)
        for entry in result["tools"]:
            assert set(entry.keys()) == {"id", "path"}

    def test_path_format_is_tools_slash_dirname(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "my_tool")
        result = generate_catalog(tools_dir)
        assert result["tools"][0]["path"] == "tools/my_tool"

    def test_stable_order_with_swapped_dirs(self, tmp_path: Path) -> None:
        """Creating dirs in reverse order still yields sorted catalog."""
        tools_dir = tmp_path / "tools"
        for name in ["zebra", "alpha", "mango"]:
            _make_tool(tools_dir, name)
        result = generate_catalog(tools_dir)
        ids = [e["id"] for e in result["tools"]]
        assert ids == sorted(ids)

    def test_byte_identical_across_two_calls(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        for name in ["a_tool", "b_tool", "c_tool"]:
            _make_tool(tools_dir, name)
        r1 = generate_catalog(tools_dir)
        r2 = generate_catalog(tools_dir)
        assert canonical_json(r1) == canonical_json(r2)

    def test_excludes_non_launcher_dirs(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "real_tool")
        (tools_dir / "not_a_tool").mkdir()  # no launcher
        result = generate_catalog(tools_dir)
        ids = [e["id"] for e in result["tools"]]
        assert "real_tool" in ids
        assert "not_a_tool" not in ids

    def test_empty_tools_dir_returns_empty_list(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        result = generate_catalog(tools_dir)
        assert result["tools"] == []

    def test_falls_back_to_dirname_without_toml(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "no_toml", with_toml=False)
        result = generate_catalog(tools_dir)
        assert result["tools"][0]["id"] == "no_toml"


# ---------------------------------------------------------------------------
# TestLoadCatalog invariants
# ---------------------------------------------------------------------------


class TestLoadCatalogInvariants:
    def test_round_trip_canonical_json(self, tmp_path: Path) -> None:
        tools_dir = tmp_path / "tools"
        _make_tool(tools_dir, "alpha")
        _make_tool(tools_dir, "beta")
        catalog = generate_catalog(tools_dir)
        path = tmp_path / "catalog.json"
        path.write_text(canonical_json(catalog), encoding="utf-8")
        loaded = load_catalog(path)
        assert loaded == catalog

    def test_load_catalog_raises_on_missing_file(self, tmp_path: Path) -> None:
        import pytest
        with pytest.raises(FileNotFoundError):
            load_catalog(tmp_path / "nonexistent.json")

    def test_load_catalog_raises_on_invalid_json(self, tmp_path: Path) -> None:
        import pytest
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_catalog(bad)
