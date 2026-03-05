"""Tests for tools/tool_registration_manager/registrar.py"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Make registrar importable without installation.
sys.path.insert(0, str(Path(__file__).parents[1]))

import registrar as reg

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_FIXTURES   = Path(__file__).parent / "fixtures"
_SAMPLE     = _FIXTURES / "sample_tool"
_ANOTHER    = _FIXTURES / "another_tool"
_BAD_EP     = _FIXTURES / "bad_entrypoint_tool"
_TV_REPO    = _FIXTURES / "techvault_repo"


def _copy_tv(dest: Path) -> Path:
    """Copy the techvault_repo fixture into dest and return dest."""
    return shutil.copytree(_TV_REPO, dest)


def _copy_tool(src: Path, dest_parent: Path) -> Path:
    """Copy a tool fixture into dest_parent/<name> and return its path."""
    dest = dest_parent / src.name
    shutil.copytree(src, dest)
    return dest


def _api_init(tv_root: Path) -> Path:
    return tv_root / "backend" / "techvault" / "app" / "api" / "__init__.py"


def _run(argv: list[str]) -> int:
    return reg.main(argv)


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_leaves_file_unchanged(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        original = _api_init(tv).read_text()

        _run([str(_SAMPLE), "--techvault-root", str(tv)])

        assert _api_init(tv).read_text() == original

    def test_dry_run_returns_0(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        code = _run([str(_SAMPLE), "--techvault-root", str(tv)])
        assert code == 0

    def test_dry_run_prints_would_change(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        assert "WOULD CHANGE" in out or "DRY-RUN" in out

    def test_dry_run_shows_import_in_output(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        assert "sample_tool" in out


# ---------------------------------------------------------------------------
# TestApply
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_returns_0(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        code = _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        assert code == 0

    def test_apply_writes_import_block(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert reg._IMP_BEGIN in content
        assert reg._IMP_END in content

    def test_apply_writes_mount_block(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert reg._MNT_BEGIN in content
        assert reg._MNT_END in content

    def test_apply_import_line_correct(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        expected = "from sample_tool.api.router import router as sample_tool_router"
        assert expected in content

    def test_apply_mount_block_correct(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert "api_router.include_router(" in content
        assert "sample_tool_router," in content
        assert 'tags=["tools:sample_tool"]' in content

    def test_apply_import_before_api_router(self, tmp_path):
        """Import block must appear before api_router = APIRouter()."""
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        imp_pos = content.index(reg._IMP_BEGIN)
        api_pos = content.index("api_router = APIRouter()")
        assert imp_pos < api_pos

    def test_apply_mount_before_all(self, tmp_path):
        """Mount block must appear before __all__."""
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        mnt_pos = content.index(reg._MNT_BEGIN)
        all_pos = content.index('__all__')
        assert mnt_pos < all_pos

    def test_apply_file_is_valid_python(self, tmp_path):
        import py_compile
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        py_compile.compile(str(_api_init(tv)), doraise=True)  # must not raise


# ---------------------------------------------------------------------------
# TestIdempotent
# ---------------------------------------------------------------------------


class TestIdempotent:
    def test_second_apply_returns_0(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        code = _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        assert code == 0

    def test_second_apply_no_content_change(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        after_first = _api_init(tv).read_text()
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        after_second = _api_init(tv).read_text()
        assert after_first == after_second

    def test_second_apply_reports_no_changes(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        capsys.readouterr()  # discard first run output
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        out = capsys.readouterr().out
        assert "NO CHANGES" in out

    def test_third_dry_run_shows_no_change(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        capsys.readouterr()
        _run([str(_SAMPLE), "--techvault-root", str(tv)])
        out = capsys.readouterr().out
        # Dry-run always runs but should show NO CHANGE (not WOULD CHANGE)
        # with identical content.
        assert "WOULD CHANGE" not in out


# ---------------------------------------------------------------------------
# TestSortedOutput
# ---------------------------------------------------------------------------


class TestSortedOutput:
    def _setup_two_tools(self, tmp_path):
        """Register two tools and return the final content."""
        tv = _copy_tv(tmp_path / "tv")
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        _copy_tool(_SAMPLE, tools_dir)
        _copy_tool(_ANOTHER, tools_dir)
        _run(["--all", str(tools_dir), "--techvault-root", str(tv), "--apply"])
        return _api_init(tv).read_text()

    def test_two_tools_both_imports_present(self, tmp_path):
        content = self._setup_two_tools(tmp_path)
        assert "from another_tool.api.router import router as another_tool_router" in content
        assert "from sample_tool.api.router import router as sample_tool_router" in content

    def test_import_block_sorted_lexicographically(self, tmp_path):
        content = self._setup_two_tools(tmp_path)
        # another_tool < sample_tool alphabetically
        another_pos = content.index("another_tool_router")
        sample_pos  = content.index("sample_tool_router")
        assert another_pos < sample_pos

    def test_mount_block_sorted_lexicographically(self, tmp_path):
        content = self._setup_two_tools(tmp_path)
        # Find positions within the mounts block
        mnt_start = content.index(reg._MNT_BEGIN)
        mnt_end   = content.index(reg._MNT_END)
        block = content[mnt_start:mnt_end]
        another_pos = block.index("another_tool_router")
        sample_pos  = block.index("sample_tool_router")
        assert another_pos < sample_pos

    def test_deterministic_repeated_runs(self, tmp_path):
        """Two independent apply runs from scratch produce identical output."""
        tv1 = _copy_tv(tmp_path / "tv1")
        tv2 = _copy_tv(tmp_path / "tv2")
        tools1 = tmp_path / "tools1"
        tools2 = tmp_path / "tools2"
        tools1.mkdir()
        tools2.mkdir()
        _copy_tool(_SAMPLE, tools1)
        _copy_tool(_ANOTHER, tools1)
        _copy_tool(_SAMPLE, tools2)
        _copy_tool(_ANOTHER, tools2)

        _run(["--all", str(tools1), "--techvault-root", str(tv1), "--apply"])
        _run(["--all", str(tools2), "--techvault-root", str(tv2), "--apply"])

        assert _api_init(tv1).read_text() == _api_init(tv2).read_text()


# ---------------------------------------------------------------------------
# TestValidationErrors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_missing_tool_toml_exits_1(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        empty_repo = tmp_path / "empty_tool"
        empty_repo.mkdir()
        code = _run([str(empty_repo), "--techvault-root", str(tv)])
        assert code == 1

    def test_missing_tool_toml_error_on_stderr(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        empty_repo = tmp_path / "empty_tool"
        empty_repo.mkdir()
        _run([str(empty_repo), "--techvault-root", str(tv)])
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_invalid_entrypoint_exits_1(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        code = _run([str(_BAD_EP), "--techvault-root", str(tv)])
        assert code == 1

    def test_invalid_entrypoint_error_message(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_BAD_EP), "--techvault-root", str(tv)])
        err = capsys.readouterr().err
        assert "entrypoint" in err.lower() or "error" in err.lower()

    def test_no_args_exits_nonzero(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        code = _run(["--techvault-root", str(tv)])
        assert code != 0

    def test_both_tool_repo_and_all_exits_1(self, tmp_path, capsys):
        tv = _copy_tv(tmp_path / "tv")
        code = _run([
            str(_SAMPLE), "--all", str(tmp_path),
            "--techvault-root", str(tv),
        ])
        assert code == 1

    def test_nonexistent_techvault_root_exits_1(self, tmp_path):
        code = _run([str(_SAMPLE), "--techvault-root", str(tmp_path / "nonexistent")])
        assert code == 1

    def test_missing_api_init_exits_1(self, tmp_path):
        """If techvault_root exists but api/__init__.py is absent, exit 1."""
        tv = tmp_path / "empty_tv"
        tv.mkdir()
        code = _run([str(_SAMPLE), "--techvault-root", str(tv)])
        assert code == 1


# ---------------------------------------------------------------------------
# TestBlockMarkers
# ---------------------------------------------------------------------------


class TestBlockMarkers:
    def test_import_block_markers_present(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert reg._IMP_BEGIN in content
        assert reg._IMP_END in content

    def test_mount_block_markers_present(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert reg._MNT_BEGIN in content
        assert reg._MNT_END in content

    def test_import_block_marker_text(self):
        assert reg._IMP_BEGIN == "# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)"
        assert reg._IMP_END   == "# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)"

    def test_mount_block_marker_text(self):
        assert reg._MNT_BEGIN == "# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)"
        assert reg._MNT_END   == "# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)"

    def test_original_content_outside_blocks_preserved(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert "from fastapi import APIRouter" in content
        assert "api_router = APIRouter()" in content
        assert '__all__ = ["api_router"]' in content


# ---------------------------------------------------------------------------
# TestAllFlag
# ---------------------------------------------------------------------------


class TestAllFlag:
    def test_all_registers_multiple_tools(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        _copy_tool(_SAMPLE, tools_dir)
        _copy_tool(_ANOTHER, tools_dir)

        code = _run(["--all", str(tools_dir), "--techvault-root", str(tv), "--apply"])
        assert code == 0

        content = _api_init(tv).read_text()
        assert "sample_tool_router" in content
        assert "another_tool_router" in content

    def test_all_skips_dirs_without_tool_toml(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        _copy_tool(_SAMPLE, tools_dir)
        (tools_dir / "not_a_tool").mkdir()  # no tool.toml

        code = _run(["--all", str(tools_dir), "--techvault-root", str(tv), "--apply"])
        assert code == 0

    def test_all_and_positional_mutually_exclusive(self, tmp_path):
        tv = _copy_tv(tmp_path / "tv")
        code = _run([
            str(_SAMPLE), "--all", str(tmp_path),
            "--techvault-root", str(tv),
        ])
        assert code == 1


# ---------------------------------------------------------------------------
# TestSingleToolPreservesExisting
# ---------------------------------------------------------------------------


class TestSingleToolPreservesExisting:
    def test_second_tool_preserves_first(self, tmp_path):
        """Registering tool B single-tool should not remove tool A."""
        tv = _copy_tv(tmp_path / "tv")
        _run([str(_SAMPLE), "--techvault-root", str(tv), "--apply"])
        _run([str(_ANOTHER), "--techvault-root", str(tv), "--apply"])
        content = _api_init(tv).read_text()
        assert "sample_tool_router" in content
        assert "another_tool_router" in content
