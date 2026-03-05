"""
Tests for tool_common.stamp
============================
Covers:
  - normalize_manifest_bytes: key sorting, UTF-8, trailing newline, stability
  - compute_manifest_sha256: stability, canonical (whitespace-insensitive)
  - read_tool_toml: happy path, file missing
  - _build_template_block: key order, invalid stamp_source
  - _strip_template_section: removes end-of-file section, mid-file section,
                              no-op when absent, preserves other sections
  - write_stamp: create, overwrite, preserve, deterministic, invalid source
  - validate_stamp: pass, missing section (warn/strict), hash mismatch,
                    missing fields (warn/strict), invalid stamp_source (warn),
                    strict mode raises
"""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from tool_common.stamp import (
    VALID_STAMP_SOURCES,
    StampValidationError,
    _build_template_block,
    _strip_template_section,
    compute_manifest_sha256,
    normalize_manifest_bytes,
    read_tool_toml,
    validate_stamp,
    write_stamp,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST: dict = {
    "policies": {
        "cli_invocation": "python -m <tool_id>.cli <command>",
        "response_hash_enabled_default": False,
    },
    "required_dirs": ["docs", "tests"],
    "required_root_files": ["README.md", "tool.toml"],
    "template_version": "2.0.0",
}

MINIMAL_TOOL_TOML = """\
tool_id = "sample_tool"
name = "sample_tool"
version = "0.1.0"
entrypoint = "sample_tool.api.router:router"
enabled_by_default = false

[api]
mount_prefix = ""
tags = ["tools:sample_tool"]

[capabilities]
actions = ["search"]
"""


def _write_manifest(path: Path, data: dict | None = None) -> Path:
    manifest = path / "TEMPLATE_MANIFEST.json"
    manifest.write_text(
        json.dumps(data or SAMPLE_MANIFEST, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_tool_toml(path: Path, content: str = MINIMAL_TOOL_TOML) -> Path:
    toml = path / "tool.toml"
    toml.write_text(content, encoding="utf-8")
    return toml


# ---------------------------------------------------------------------------
# normalize_manifest_bytes
# ---------------------------------------------------------------------------


class TestNormalizeManifestBytes:
    def test_returns_bytes(self) -> None:
        result = normalize_manifest_bytes(SAMPLE_MANIFEST)
        assert isinstance(result, bytes)

    def test_trailing_newline(self) -> None:
        result = normalize_manifest_bytes(SAMPLE_MANIFEST)
        assert result.endswith(b"\n")
        assert not result.endswith(b"\n\n")

    def test_utf8_encoding(self) -> None:
        data = {"key": "café"}
        result = normalize_manifest_bytes(data)
        assert "café".encode("utf-8") in result

    def test_sort_keys(self) -> None:
        # Keys appear in sorted order in output
        data = {"z_key": 1, "a_key": 2, "m_key": 3}
        result = normalize_manifest_bytes(data).decode("utf-8")
        a_pos = result.index("a_key")
        m_pos = result.index("m_key")
        z_pos = result.index("z_key")
        assert a_pos < m_pos < z_pos

    def test_stable_across_calls(self) -> None:
        r1 = normalize_manifest_bytes(SAMPLE_MANIFEST)
        r2 = normalize_manifest_bytes(SAMPLE_MANIFEST)
        assert r1 == r2

    def test_same_data_different_insertion_order(self) -> None:
        # Dict insertion order must not affect output
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert normalize_manifest_bytes(d1) == normalize_manifest_bytes(d2)

    def test_compact_separators(self) -> None:
        result = normalize_manifest_bytes({"a": 1}).decode("utf-8")
        # Compact: no spaces around : or ,
        assert ": " not in result
        assert ", " not in result


# ---------------------------------------------------------------------------
# compute_manifest_sha256
# ---------------------------------------------------------------------------


class TestComputeManifestSha256:
    def test_returns_hex_string(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        result = compute_manifest_sha256(manifest)
        assert isinstance(result, str)
        assert len(result) == 64
        int(result, 16)  # must be valid hex

    def test_stable_across_calls(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        assert compute_manifest_sha256(manifest) == compute_manifest_sha256(manifest)

    def test_canonical_whitespace_insensitive(self, tmp_path: Path) -> None:
        """Two JSON files with different whitespace produce the same hash."""
        m1 = tmp_path / "m1.json"
        m2 = tmp_path / "m2.json"
        data = SAMPLE_MANIFEST
        m1.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        m2.write_text(json.dumps(data, indent=4) + "\n\n", encoding="utf-8")
        assert compute_manifest_sha256(m1) == compute_manifest_sha256(m2)

    def test_different_data_different_hash(self, tmp_path: Path) -> None:
        m1 = tmp_path / "m1.json"
        m2 = tmp_path / "m2.json"
        m1.write_text(json.dumps({"a": 1}), encoding="utf-8")
        m2.write_text(json.dumps({"a": 2}), encoding="utf-8")
        assert compute_manifest_sha256(m1) != compute_manifest_sha256(m2)

    def test_matches_manual_computation(self, tmp_path: Path) -> None:
        """Verify against a hand-rolled computation to detect algorithm drift."""
        manifest = _write_manifest(tmp_path)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        canonical = (
            json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        expected = hashlib.sha256(canonical).hexdigest()
        assert compute_manifest_sha256(manifest) == expected

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            compute_manifest_sha256(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# read_tool_toml
# ---------------------------------------------------------------------------


class TestReadToolToml:
    def test_reads_root_fields(self, tmp_path: Path) -> None:
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["tool_id"] == "sample_tool"
        assert data["version"] == "0.1.0"
        assert data["enabled_by_default"] is False

    def test_reads_api_section(self, tmp_path: Path) -> None:
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["api"]["mount_prefix"] == ""
        assert data["api"]["tags"] == ["tools:sample_tool"]

    def test_reads_capabilities_section(self, tmp_path: Path) -> None:
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["capabilities"]["actions"] == ["search"]

    def test_reads_template_section(self, tmp_path: Path) -> None:
        content = MINIMAL_TOOL_TOML + '\n[template]\nmanifest_hash = "abc"\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        data = read_tool_toml(toml)
        assert data["template"]["manifest_hash"] == "abc"
        assert data["template"]["template_version"] == "2.0.0"

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_tool_toml(tmp_path / "missing.toml")

    def test_raises_on_invalid_toml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not = valid = toml !!!\n", encoding="utf-8")
        with pytest.raises(tomllib.TOMLDecodeError):
            read_tool_toml(bad)


# ---------------------------------------------------------------------------
# _build_template_block
# ---------------------------------------------------------------------------


class TestBuildTemplateBlock:
    def test_keys_in_alphabetical_order(self) -> None:
        block = _build_template_block("2.0.0", "abc123", "create")
        mh_pos = block.index("manifest_hash")
        ss_pos = block.index("stamp_source")
        tv_pos = block.index("template_version")
        assert mh_pos < ss_pos < tv_pos

    def test_header_present(self) -> None:
        block = _build_template_block("2.0.0", "abc123", "create")
        assert block.startswith("[template]\n")

    def test_values_quoted(self) -> None:
        block = _build_template_block("2.0.0", "deadbeef", "patch")
        assert '"deadbeef"' in block
        assert '"patch"' in block
        assert '"2.0.0"' in block

    def test_all_stamp_sources_accepted(self) -> None:
        for src in sorted(VALID_STAMP_SOURCES):
            block = _build_template_block("2.0.0", "abc", src)
            assert f'stamp_source     = "{src}"' in block

    def test_invalid_stamp_source_raises(self) -> None:
        with pytest.raises(ValueError, match="stamp_source must be one of"):
            _build_template_block("2.0.0", "abc", "auto")

    def test_deterministic(self) -> None:
        b1 = _build_template_block("2.0.0", "abc", "create")
        b2 = _build_template_block("2.0.0", "abc", "create")
        assert b1 == b2


# ---------------------------------------------------------------------------
# _strip_template_section
# ---------------------------------------------------------------------------


class TestStripTemplateSection:
    def test_removes_end_of_file_section(self) -> None:
        text = MINIMAL_TOOL_TOML + "\n[template]\nmanifest_hash = \"x\"\ntemplate_version = \"2\"\n"
        result = _strip_template_section(text)
        assert "[template]" not in result
        assert "manifest_hash" not in result
        assert "template_version" not in result

    def test_preserves_api_and_capabilities(self) -> None:
        text = MINIMAL_TOOL_TOML + "\n[template]\nmanifest_hash = \"x\"\n"
        result = _strip_template_section(text)
        assert "[api]" in result
        assert "[capabilities]" in result

    def test_no_op_when_absent(self) -> None:
        result = _strip_template_section(MINIMAL_TOOL_TOML)
        # Content should be equivalent (may differ in trailing whitespace)
        assert "tool_id" in result
        assert "[template]" not in result

    def test_preserves_root_fields(self) -> None:
        text = MINIMAL_TOOL_TOML + "\n[template]\nmanifest_hash = \"x\"\n"
        result = _strip_template_section(text)
        assert 'tool_id = "sample_tool"' in result
        assert 'version = "0.1.0"' in result

    def test_section_in_middle_removed(self) -> None:
        """[template] between two other sections: the section after is preserved."""
        text = (
            'tool_id = "x"\n'
            "\n[template]\n"
            'manifest_hash = "y"\n'
            "\n[api]\n"
            'mount_prefix = ""\n'
        )
        result = _strip_template_section(text)
        assert "[template]" not in result
        assert "manifest_hash" not in result
        assert "[api]" in result
        assert 'mount_prefix = ""' in result

    def test_idempotent(self) -> None:
        text = MINIMAL_TOOL_TOML + "\n[template]\nmanifest_hash = \"x\"\n"
        once = _strip_template_section(text)
        twice = _strip_template_section(once)
        assert once == twice


# ---------------------------------------------------------------------------
# write_stamp
# ---------------------------------------------------------------------------


class TestWriteStamp:
    def _expected_hash(self, manifest: Path) -> str:
        return compute_manifest_sha256(manifest)

    def test_creates_template_section(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        data = read_tool_toml(toml)
        assert data["template"]["template_version"] == "2.0.0"
        assert data["template"]["manifest_hash"] == h
        assert data["template"]["stamp_source"] == "create"

    def test_overwrites_existing_template_section(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        old_content = MINIMAL_TOOL_TOML + "\n[template]\nmanifest_hash = \"old\"\ntemplate_version = \"1.0.0\"\n"
        toml = _write_tool_toml(tmp_path, old_content)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "patch")
        data = read_tool_toml(toml)
        assert data["template"]["manifest_hash"] == h
        assert data["template"]["template_version"] == "2.0.0"
        assert data["template"]["stamp_source"] == "patch"

    def test_preserves_other_fields(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        data = read_tool_toml(toml)
        assert data["tool_id"] == "sample_tool"
        assert data["api"]["mount_prefix"] == ""
        assert data["capabilities"]["actions"] == ["search"]

    def test_template_section_last(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        content = toml.read_text(encoding="utf-8")
        template_pos = content.rindex("[template]")
        api_pos = content.rindex("[api]")
        cap_pos = content.rindex("[capabilities]")
        assert template_pos > api_pos
        assert template_pos > cap_pos

    def test_deterministic_double_write(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        content1 = toml.read_text(encoding="utf-8")
        write_stamp(toml, "2.0.0", h, "create")
        content2 = toml.read_text(encoding="utf-8")
        assert content1 == content2

    def test_single_trailing_newline(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        content = toml.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert not content.endswith("\n\n")

    def test_invalid_stamp_source_raises(self, tmp_path: Path) -> None:
        toml = _write_tool_toml(tmp_path)
        with pytest.raises(ValueError, match="stamp_source must be one of"):
            write_stamp(toml, "2.0.0", "abc", "automated")

    def test_keys_in_alphabetical_order_in_file(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = self._expected_hash(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        content = toml.read_text(encoding="utf-8")
        segment = content[content.rindex("[template]"):]
        mh = segment.index("manifest_hash")
        ss = segment.index("stamp_source")
        tv = segment.index("template_version")
        assert mh < ss < tv


# ---------------------------------------------------------------------------
# validate_stamp
# ---------------------------------------------------------------------------


class TestValidateStamp:
    def _make_stamped_toml(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (tool.toml, manifest.json) with a valid stamp written."""
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = compute_manifest_sha256(manifest)
        write_stamp(toml, "2.0.0", h, "create")
        return toml, manifest

    def test_pass_on_valid_stamp(self, tmp_path: Path) -> None:
        toml, manifest = self._make_stamped_toml(tmp_path)
        findings = validate_stamp(toml, manifest)
        assert findings == []

    # Missing [template] section ─────────────────────────────────────────────

    def test_missing_section_produces_warn_in_non_strict(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)  # no stamp
        findings = validate_stamp(toml, manifest, strict=False)
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARN"
        assert findings[0]["field"] == "template"

    def test_missing_section_produces_error_in_strict(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        with pytest.raises(StampValidationError, match="Missing \\[template\\] section"):
            validate_stamp(toml, manifest, strict=True)

    def test_missing_section_returns_early(self, tmp_path: Path) -> None:
        """When the whole section is missing, only one finding is returned."""
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        findings = validate_stamp(toml, manifest)
        assert len(findings) == 1

    # Missing individual fields ───────────────────────────────────────────────

    def test_missing_template_version_warn(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = MINIMAL_TOOL_TOML + f'\n[template]\nmanifest_hash = "{h}"\n'
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        fields = {f["field"] for f in findings}
        assert "template.template_version" in fields
        sevs = {f["severity"] for f in findings if f["field"] == "template.template_version"}
        assert sevs == {"WARN"}

    def test_missing_manifest_hash_warn(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        fields = {f["field"] for f in findings}
        assert "template.manifest_hash" in fields
        sevs = {f["severity"] for f in findings if f["field"] == "template.manifest_hash"}
        assert sevs == {"WARN"}

    def test_missing_fields_strict_raises(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        with pytest.raises(StampValidationError):
            validate_stamp(toml, manifest, strict=True)

    # manifest_hash mismatch ─────────────────────────────────────────────────

    def test_hash_mismatch_always_error(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\nmanifest_hash = "deadbeef"\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        mismatch = [f for f in findings if f["field"] == "template.manifest_hash"]
        assert mismatch
        assert mismatch[0]["severity"] == "ERROR"

    def test_hash_mismatch_error_contains_both_hashes(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\nmanifest_hash = "deadbeef"\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest)
        msg = findings[0]["message"]
        assert "deadbeef" in msg
        actual = compute_manifest_sha256(manifest)
        assert actual in msg

    def test_hash_mismatch_strict_raises(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\nmanifest_hash = "wrong"\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        with pytest.raises(StampValidationError, match="mismatch"):
            validate_stamp(toml, manifest, strict=True)

    # stamp_source ───────────────────────────────────────────────────────────

    def test_invalid_stamp_source_always_warn(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nmanifest_hash = "{h}"\nstamp_source = "robot"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=True)  # strict doesn't escalate WARN
        ss_findings = [f for f in findings if f["field"] == "template.stamp_source"]
        assert ss_findings
        assert ss_findings[0]["severity"] == "WARN"

    def test_valid_stamp_sources_produce_no_finding(self, tmp_path: Path) -> None:
        for src in sorted(VALID_STAMP_SOURCES):
            t = tmp_path / src
            t.mkdir()
            manifest = _write_manifest(t)
            h = compute_manifest_sha256(manifest)
            content = (
                MINIMAL_TOOL_TOML
                + f'\n[template]\nmanifest_hash = "{h}"\nstamp_source = "{src}"\ntemplate_version = "2.0.0"\n'
            )
            toml = _write_tool_toml(t, content)
            findings = validate_stamp(toml, manifest)
            ss_findings = [f for f in findings if f["field"] == "template.stamp_source"]
            assert ss_findings == [], f"Unexpected finding for stamp_source={src!r}"

    # strict mode gate ────────────────────────────────────────────────────────

    def test_strict_does_not_raise_on_warn_only(self, tmp_path: Path) -> None:
        """stamp_source WARN does not cause StampValidationError in strict mode."""
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nmanifest_hash = "{h}"\nstamp_source = "robot"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=True)  # must not raise
        assert any(f["severity"] == "WARN" for f in findings)

    def test_findings_list_not_empty_on_error(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\nmanifest_hash = "bad"\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest)
        assert any(f["severity"] == "ERROR" for f in findings)

    # Parsing failure ─────────────────────────────────────────────────────────

    def test_bad_toml_raises_value_error(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path)
        bad = tmp_path / "tool.toml"
        bad.write_text("not = valid = toml !!!\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot parse"):
            validate_stamp(bad, manifest)
