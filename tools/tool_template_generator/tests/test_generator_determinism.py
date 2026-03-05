"""Determinism invariant tests for techvault-tool-create scaffold generator.

Verifies that creating the same tool ID twice (with identical inputs) produces
byte-for-byte identical file contents.  This guards against hidden non-determinism
(random IDs, timestamps baked into content, unordered file writes, etc.).
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

# Allow importing generator.py directly.
_GENERATOR_DIR = Path(__file__).resolve().parents[1]   # tools/tool_template_generator/
_TOOLS_DIR = _GENERATOR_DIR.parent                     # tools/

for _p in (str(_TOOLS_DIR), str(_GENERATOR_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import generator  # type: ignore

_TEMPLATE_ROOT: Path = _TOOLS_DIR / "tool_template"
_TOOL_ID = "example_tmp_tool"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dir_digest(root: Path) -> dict[str, str]:
    """Return mapping of ``relative_path → sha256_hex`` for every file under root."""
    return {
        str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(root.rglob("*"))
        if f.is_file()
    }


# ---------------------------------------------------------------------------
# TestGeneratorDeterminism
# ---------------------------------------------------------------------------


class TestGeneratorDeterminism:
    """create_scaffold must be byte-identical on repeated runs with the same inputs."""

    def test_byte_identical_file_contents_on_repeated_generation(
        self, tmp_path: Path
    ) -> None:
        """Generate → hash → delete → generate again; all file contents must match."""
        base_dir = tmp_path / "tools"
        base_dir.mkdir()

        # First generation.
        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)
        digest_1 = _dir_digest(base_dir / _TOOL_ID)

        shutil.rmtree(base_dir / _TOOL_ID)

        # Second generation with identical inputs.
        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)
        digest_2 = _dir_digest(base_dir / _TOOL_ID)

        differing = {
            path: (digest_1[path], digest_2[path])
            for path in digest_1
            if digest_1[path] != digest_2[path]
        }
        assert not differing, (
            f"Generator is non-deterministic — {len(differing)} file(s) differ:\n"
            + "\n".join(f"  {p}: {h1!r} vs {h2!r}" for p, (h1, h2) in sorted(differing.items()))
        )

    def test_identical_file_set_on_repeated_generation(self, tmp_path: Path) -> None:
        """The set of generated relative file paths must be identical across runs."""
        base_dir = tmp_path / "tools"
        base_dir.mkdir()

        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)
        files_1 = {
            str(f.relative_to(base_dir / _TOOL_ID))
            for f in (base_dir / _TOOL_ID).rglob("*")
            if f.is_file()
        }

        shutil.rmtree(base_dir / _TOOL_ID)

        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)
        files_2 = {
            str(f.relative_to(base_dir / _TOOL_ID))
            for f in (base_dir / _TOOL_ID).rglob("*")
            if f.is_file()
        }

        assert files_1 == files_2, (
            f"File sets differ.\n"
            f"  Only in run 1: {sorted(files_1 - files_2)}\n"
            f"  Only in run 2: {sorted(files_2 - files_1)}"
        )

    def test_refuses_to_overwrite_existing_directory(self, tmp_path: Path) -> None:
        """create_scaffold must raise FileExistsError if the target dir already exists."""
        base_dir = tmp_path / "tools"
        base_dir.mkdir()

        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)

        with pytest.raises(FileExistsError, match=_TOOL_ID):
            generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)

    def test_tool_toml_contains_tool_id(self, tmp_path: Path) -> None:
        """Generated tool.toml must embed the requested tool_id."""
        base_dir = tmp_path / "tools"
        base_dir.mkdir()

        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)
        toml_text = (base_dir / _TOOL_ID / "tool.toml").read_text(encoding="utf-8")

        assert f'tool_id = "{_TOOL_ID}"' in toml_text

    def test_template_manifest_copied_into_tool_root(self, tmp_path: Path) -> None:
        """TEMPLATE_MANIFEST.json must be copied verbatim into the new tool root."""
        base_dir = tmp_path / "tools"
        base_dir.mkdir()

        generator.create_scaffold(base_dir, _TEMPLATE_ROOT, _TOOL_ID)

        source_bytes = (_TEMPLATE_ROOT / "TEMPLATE_MANIFEST.json").read_bytes()
        copied_bytes = (base_dir / _TOOL_ID / "TEMPLATE_MANIFEST.json").read_bytes()
        assert source_bytes == copied_bytes
