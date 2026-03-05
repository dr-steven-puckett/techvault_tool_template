"""
Tests for tool_common.stamp
============================
59 tests covering the full public API against the spec in docs/TOOL_TOML_SPEC.md.

Sections
--------
A) normalize_manifest_bytes   (tests  1– 8)
B) compute_manifest_sha256    (tests  9–14)
C) read_tool_toml             (tests 15–19)
D) write_stamp                (tests 20–31)
E) validate_stamp             (tests 32–59)
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
    compute_manifest_sha256,
    normalize_manifest_bytes,
    read_tool_toml,
    validate_stamp,
    write_stamp,
)


# ---------------------------------------------------------------------------
# Shared test data
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


def _valid_stamp_hash(manifest: Path) -> str:
    return compute_manifest_sha256(manifest)


# ---------------------------------------------------------------------------
# A) normalize_manifest_bytes  (8 tests)
# ---------------------------------------------------------------------------


class TestNormalizeManifestBytes:
    """Tests 1-8."""

    def test_accepts_str_input(self) -> None:  # 1
        text = json.dumps(SAMPLE_MANIFEST)
        result = normalize_manifest_bytes(text)
        assert isinstance(result, bytes)

    def test_accepts_bytes_input(self) -> None:  # 2
        raw = json.dumps(SAMPLE_MANIFEST).encode("utf-8")
        result = normalize_manifest_bytes(raw)
        assert isinstance(result, bytes)

    def test_str_and_bytes_same_output(self) -> None:  # 3
        text = json.dumps(SAMPLE_MANIFEST)
        assert normalize_manifest_bytes(text) == normalize_manifest_bytes(text.encode("utf-8"))

    def test_different_str_whitespace_identical_output(self) -> None:  # 4
        compact = json.dumps(SAMPLE_MANIFEST, separators=(",", ":"))
        pretty = json.dumps(SAMPLE_MANIFEST, indent=4)
        assert normalize_manifest_bytes(compact) == normalize_manifest_bytes(pretty)

    def test_non_utf8_bytes_raises_unicode_decode_error(self) -> None:  # 5
        bad = b"\xff\xfe invalid utf-8"
        with pytest.raises(UnicodeDecodeError):
            normalize_manifest_bytes(bad)

    def test_invalid_json_raises_json_decode_error(self) -> None:  # 6
        with pytest.raises(json.JSONDecodeError):
            normalize_manifest_bytes("not valid json {{")

    def test_output_ends_with_exactly_one_newline(self) -> None:  # 7
        result = normalize_manifest_bytes(json.dumps(SAMPLE_MANIFEST))
        assert result.endswith(b"\n")
        assert not result.endswith(b"\n\n")

    def test_sort_keys_deterministic(self) -> None:  # 8
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"a": 2, "m": 3, "z": 1}
        assert normalize_manifest_bytes(json.dumps(d1)) == normalize_manifest_bytes(json.dumps(d2))


# ---------------------------------------------------------------------------
# B) compute_manifest_sha256  (6 tests)
# ---------------------------------------------------------------------------


class TestComputeManifestSha256:
    """Tests 9-14."""

    def test_returns_64_char_hex(self, tmp_path: Path) -> None:  # 9
        manifest = _write_manifest(tmp_path)
        result = compute_manifest_sha256(manifest)
        assert isinstance(result, str)
        assert len(result) == 64
        int(result, 16)  # must be valid hex

    def test_stable_across_calls(self, tmp_path: Path) -> None:  # 10
        manifest = _write_manifest(tmp_path)
        assert compute_manifest_sha256(manifest) == compute_manifest_sha256(manifest)

    def test_whitespace_insensitive(self, tmp_path: Path) -> None:  # 11
        m1 = tmp_path / "m1.json"
        m2 = tmp_path / "m2.json"
        m1.write_text(json.dumps(SAMPLE_MANIFEST, indent=2) + "\n", encoding="utf-8")
        m2.write_text(json.dumps(SAMPLE_MANIFEST, indent=4) + "\n\n", encoding="utf-8")
        assert compute_manifest_sha256(m1) == compute_manifest_sha256(m2)

    def test_different_data_different_hash(self, tmp_path: Path) -> None:  # 12
        m1 = tmp_path / "m1.json"
        m2 = tmp_path / "m2.json"
        m1.write_text(json.dumps({"a": 1}), encoding="utf-8")
        m2.write_text(json.dumps({"a": 2}), encoding="utf-8")
        assert compute_manifest_sha256(m1) != compute_manifest_sha256(m2)

    def test_matches_manual_computation(self, tmp_path: Path) -> None:  # 13
        manifest = _write_manifest(tmp_path)
        raw = manifest.read_bytes()
        obj = json.loads(raw.decode("utf-8"))
        canonical = (
            json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode("utf-8")
        expected = hashlib.sha256(canonical).hexdigest()
        assert compute_manifest_sha256(manifest) == expected

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:  # 14
        with pytest.raises(FileNotFoundError):
            compute_manifest_sha256(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# C) read_tool_toml  (5 tests)
# ---------------------------------------------------------------------------


class TestReadToolToml:
    """Tests 15-19."""

    def test_reads_root_fields(self, tmp_path: Path) -> None:  # 15
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["tool_id"] == "sample_tool"
        assert data["version"] == "0.1.0"
        assert data["enabled_by_default"] is False

    def test_reads_api_section(self, tmp_path: Path) -> None:  # 16
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["api"]["mount_prefix"] == ""
        assert data["api"]["tags"] == ["tools:sample_tool"]

    def test_reads_capabilities_section(self, tmp_path: Path) -> None:  # 17
        toml = _write_tool_toml(tmp_path)
        data = read_tool_toml(toml)
        assert data["capabilities"]["actions"] == ["search"]

    def test_raises_file_not_found(self, tmp_path: Path) -> None:  # 18
        with pytest.raises(FileNotFoundError):
            read_tool_toml(tmp_path / "missing.toml")

    def test_raises_on_invalid_toml(self, tmp_path: Path) -> None:  # 19
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not = valid = toml !!!\n", encoding="utf-8")
        with pytest.raises(tomllib.TOMLDecodeError):
            read_tool_toml(bad)


# ---------------------------------------------------------------------------
# D) write_stamp  (12 tests)
# ---------------------------------------------------------------------------


class TestWriteStamp:
    """Tests 20-31."""

    def test_creates_template_section(self, tmp_path: Path) -> None:  # 20
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        data = read_tool_toml(toml)
        assert data["template"]["template_version"] == "2.0.0"
        assert data["template"]["template_manifest_hash"] == h
        assert data["template"]["stamp_source"] == "create"

    def test_template_manifest_hash_key_name(self, tmp_path: Path) -> None:  # 21
        """The written key is template_manifest_hash, not manifest_hash."""
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        content = toml.read_text(encoding="utf-8")
        assert "template_manifest_hash" in content
        # Ensure 'manifest_hash' only appears as part of 'template_manifest_hash'
        rest = content.replace("template_manifest_hash", "")
        assert "manifest_hash" not in rest

    def test_overwrites_existing_template_section(self, tmp_path: Path) -> None:  # 22
        manifest = _write_manifest(tmp_path)
        old = (
            MINIMAL_TOOL_TOML
            + '\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "old"\ntemplate_version = "1.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, old)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="patch")
        data = read_tool_toml(toml)
        assert data["template"]["template_manifest_hash"] == h
        assert data["template"]["template_version"] == "2.0.0"
        assert data["template"]["stamp_source"] == "patch"

    def test_preserves_other_sections(self, tmp_path: Path) -> None:  # 23
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        data = read_tool_toml(toml)
        assert data["tool_id"] == "sample_tool"
        assert data["api"]["mount_prefix"] == ""
        assert data["capabilities"]["actions"] == ["search"]

    def test_template_section_is_last(self, tmp_path: Path) -> None:  # 24
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        content = toml.read_text(encoding="utf-8")
        template_pos = content.rindex("[template]")
        api_pos = content.rindex("[api]")
        cap_pos = content.rindex("[capabilities]")
        assert template_pos > api_pos
        assert template_pos > cap_pos

    def test_keys_alphabetical_in_template(self, tmp_path: Path) -> None:  # 25
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        content = toml.read_text(encoding="utf-8")
        segment = content[content.rindex("[template]"):]
        # Alphabetical: stamp_source < template_manifest_hash < template_version
        ss = segment.index("stamp_source")
        tmh = segment.index("template_manifest_hash")
        tv = segment.index("template_version")
        assert ss < tmh < tv

    def test_string_values_use_double_quotes(self, tmp_path: Path) -> None:  # 26
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        content = toml.read_text(encoding="utf-8")
        segment = content[content.rindex("[template]"):]
        assert '"create"' in segment
        assert f'"{h}"' in segment
        assert '"2.0.0"' in segment

    def test_single_trailing_newline(self, tmp_path: Path) -> None:  # 27
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        content = toml.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert not content.endswith("\n\n")

    def test_deterministic_double_write(self, tmp_path: Path) -> None:  # 28
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = _valid_stamp_hash(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        bytes1 = toml.read_bytes()
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        bytes2 = toml.read_bytes()
        assert bytes1 == bytes2

    def test_invalid_stamp_source_raises(self, tmp_path: Path) -> None:  # 29
        toml = _write_tool_toml(tmp_path)
        with pytest.raises(ValueError, match="stamp_source must be one of"):
            write_stamp(toml, template_version="2.0.0", template_manifest_hash="abc", stamp_source="automated")

    def test_all_valid_stamp_sources_accepted(self, tmp_path: Path) -> None:  # 30
        for src in sorted(VALID_STAMP_SOURCES):
            t = tmp_path / src
            t.mkdir()
            toml = _write_tool_toml(t)
            write_stamp(toml, template_version="2.0.0", template_manifest_hash="abc", stamp_source=src)
            data = read_tool_toml(toml)
            assert data["template"]["stamp_source"] == src

    def test_keyword_only_params_required(self, tmp_path: Path) -> None:  # 31
        """write_stamp must reject positional arguments after toml_path."""
        toml = _write_tool_toml(tmp_path)
        with pytest.raises(TypeError):
            write_stamp(toml, "2.0.0", "abc", "create")  # type: ignore


# ---------------------------------------------------------------------------
# E) validate_stamp  (23 tests)
# ---------------------------------------------------------------------------


class TestValidateStamp:
    """Tests 32-54."""

    def _make_stamped_toml(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (tool.toml, manifest.json) with a fully valid stamp."""
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        h = compute_manifest_sha256(manifest)
        write_stamp(toml, template_version="2.0.0", template_manifest_hash=h, stamp_source="create")
        return toml, manifest

    # -- Valid stamp -----------------------------------------------------------

    def test_valid_stamp_no_findings(self, tmp_path: Path) -> None:  # 32
        toml, manifest = self._make_stamped_toml(tmp_path)
        findings = validate_stamp(toml, manifest)
        assert findings == []

    # -- Missing [template] section -------------------------------------------

    def test_missing_template_section_warn_non_strict(self, tmp_path: Path) -> None:  # 33
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)  # no [template]
        findings = validate_stamp(toml, manifest, strict=False)
        assert len(findings) == 1
        assert findings[0]["level"] == "WARN"
        assert findings[0]["code"] == "STAMP_MISSING"

    def test_missing_template_section_error_strict(self, tmp_path: Path) -> None:  # 34
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        try:
            validate_stamp(toml, manifest, strict=True)
            pytest.fail("Expected StampValidationError")
        except StampValidationError as exc:
            stamp_findings = [f for f in exc.findings if f["code"] == "STAMP_MISSING"]
            assert stamp_findings
            assert stamp_findings[0]["level"] == "ERROR"

    def test_missing_template_section_raises_stamp_validation_error(self, tmp_path: Path) -> None:  # 35
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        with pytest.raises(StampValidationError, match="Missing \\[template\\] section"):
            validate_stamp(toml, manifest, strict=True)

    def test_missing_template_section_returns_one_finding(self, tmp_path: Path) -> None:  # 36
        """Early-return: only one finding when entire [template] section is absent."""
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        findings = validate_stamp(toml, manifest, strict=False)
        assert len(findings) == 1

    # -- Missing required keys ------------------------------------------------

    def test_missing_template_version_warn_non_strict(self, tmp_path: Path) -> None:  # 37
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        tv_findings = [f for f in findings if "template_version" in f.get("path", "")]
        assert tv_findings
        assert tv_findings[0]["level"] == "WARN"

    def test_missing_template_version_error_strict(self, tmp_path: Path) -> None:  # 38
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        try:
            validate_stamp(toml, manifest, strict=True)
            pytest.fail("Expected StampValidationError")
        except StampValidationError as exc:
            tv_findings = [f for f in exc.findings if "template_version" in f.get("path", "")]
            assert tv_findings
            assert tv_findings[0]["level"] == "ERROR"

    def test_missing_template_manifest_hash_warn_non_strict(self, tmp_path: Path) -> None:  # 39
        manifest = _write_manifest(tmp_path)
        content = (
            MINIMAL_TOOL_TOML
            + '\n[template]\nstamp_source = "create"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        hash_findings = [f for f in findings if "template_manifest_hash" in f.get("path", "")]
        assert hash_findings
        assert hash_findings[0]["level"] == "WARN"

    def test_missing_template_manifest_hash_error_strict(self, tmp_path: Path) -> None:  # 40
        manifest = _write_manifest(tmp_path)
        content = (
            MINIMAL_TOOL_TOML
            + '\n[template]\nstamp_source = "create"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        try:
            validate_stamp(toml, manifest, strict=True)
            pytest.fail("Expected StampValidationError")
        except StampValidationError as exc:
            hash_findings = [f for f in exc.findings if "template_manifest_hash" in f.get("path", "")]
            assert hash_findings
            assert hash_findings[0]["level"] == "ERROR"

    def test_missing_fields_strict_raises(self, tmp_path: Path) -> None:  # 41
        manifest = _write_manifest(tmp_path)
        content = MINIMAL_TOOL_TOML + '\n[template]\ntemplate_version = "2.0.0"\n'
        toml = _write_tool_toml(tmp_path, content)
        with pytest.raises(StampValidationError):
            validate_stamp(toml, manifest, strict=True)

    # -- Hash format validation ------------------------------------------------

    def test_invalid_hash_format_error_always(self, tmp_path: Path) -> None:  # 42
        manifest = _write_manifest(tmp_path)
        # "deadbeef" is only 8 chars -- invalid format
        content = (
            MINIMAL_TOOL_TOML
            + '\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "deadbeef"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        hash_findings = [f for f in findings if f["code"] == "HASH_INVALID"]
        assert hash_findings
        assert hash_findings[0]["level"] == "ERROR"

    def test_invalid_hash_format_non_strict_still_error(self, tmp_path: Path) -> None:  # 43
        manifest = _write_manifest(tmp_path)
        # A non-hex 64-char string -- invalid format
        bad_hash = "X" * 64
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{bad_hash}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        hash_findings = [f for f in findings if f["code"] == "HASH_INVALID"]
        assert hash_findings
        assert hash_findings[0]["level"] == "ERROR"

    # -- Hash mismatch ---------------------------------------------------------

    def test_hash_mismatch_error_always(self, tmp_path: Path) -> None:  # 44
        manifest = _write_manifest(tmp_path)
        wrong_hash = "a" * 64  # valid format but wrong value
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{wrong_hash}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        mismatch = [f for f in findings if f["code"] == "HASH_MISMATCH"]
        assert mismatch
        assert mismatch[0]["level"] == "ERROR"

    def test_hash_mismatch_message_contains_both_hashes(self, tmp_path: Path) -> None:  # 45
        manifest = _write_manifest(tmp_path)
        wrong_hash = "b" * 64
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{wrong_hash}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        mismatch = [f for f in findings if f["code"] == "HASH_MISMATCH"]
        assert mismatch
        msg = mismatch[0]["message"]
        assert wrong_hash in msg
        actual = compute_manifest_sha256(manifest)
        assert actual in msg

    def test_hash_mismatch_strict_raises(self, tmp_path: Path) -> None:  # 46
        manifest = _write_manifest(tmp_path)
        wrong_hash = "c" * 64
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{wrong_hash}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        with pytest.raises(StampValidationError, match="mismatch"):
            validate_stamp(toml, manifest, strict=True)

    # -- stamp_source ----------------------------------------------------------

    def test_stamp_source_invalid_is_error(self, tmp_path: Path) -> None:  # 47
        """Spec change: invalid stamp_source is ERROR (not WARN)."""
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "robot"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        ss_findings = [f for f in findings if f["code"] == "STAMP_SOURCE_INVALID"]
        assert ss_findings
        assert ss_findings[0]["level"] == "ERROR"

    def test_stamp_source_valid_no_finding(self, tmp_path: Path) -> None:  # 48
        for src in sorted(VALID_STAMP_SOURCES):
            t = tmp_path / src
            t.mkdir()
            manifest = _write_manifest(t)
            h = compute_manifest_sha256(manifest)
            content = (
                MINIMAL_TOOL_TOML
                + f'\n[template]\nstamp_source = "{src}"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "2.0.0"\n'
            )
            toml = _write_tool_toml(t, content)
            findings = validate_stamp(toml, manifest, strict=False)
            assert findings == [], f"Unexpected findings for stamp_source={src!r}: {findings}"

    # -- Finding structure -----------------------------------------------------

    def test_findings_have_required_keys(self, tmp_path: Path) -> None:  # 49
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)  # no [template]
        findings = validate_stamp(toml, manifest, strict=False)
        required = {"level", "code", "message", "path"}
        for f in findings:
            assert required.issubset(f.keys()), f"Finding missing keys: {f}"

    def test_findings_use_level_not_severity(self, tmp_path: Path) -> None:  # 50
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        findings = validate_stamp(toml, manifest, strict=False)
        assert findings
        for f in findings:
            assert "level" in f
            assert "severity" not in f

    def test_findings_have_code_field(self, tmp_path: Path) -> None:  # 51
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)
        findings = validate_stamp(toml, manifest, strict=False)
        assert findings
        for f in findings:
            assert "code" in f
            assert isinstance(f["code"], str)
            assert f["code"]

    # -- Sorting ---------------------------------------------------------------

    def test_findings_sorted_deterministically(self, tmp_path: Path) -> None:  # 52
        """ERROR findings sort before WARN; same order on repeated calls."""
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        # stamp_source invalid -> ERROR; template_version missing -> WARN
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "bad"\ntemplate_manifest_hash = "{h}"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        assert len(findings) == 2
        assert findings[0]["level"] == "ERROR"
        assert findings[1]["level"] == "WARN"
        # Stable: second call returns same order
        findings2 = validate_stamp(toml, manifest, strict=False)
        assert [f["code"] for f in findings] == [f["code"] for f in findings2]

    # -- StampValidationError --------------------------------------------------

    def test_stamp_validation_error_carries_findings_attribute(self, tmp_path: Path) -> None:  # 53
        manifest = _write_manifest(tmp_path)
        toml = _write_tool_toml(tmp_path)  # no [template] -> ERROR in strict
        try:
            validate_stamp(toml, manifest, strict=True)
            pytest.fail("Expected StampValidationError")
        except StampValidationError as exc:
            assert hasattr(exc, "findings")
            assert isinstance(exc.findings, list)
            assert len(exc.findings) > 0
            assert all("level" in f for f in exc.findings)

    def test_strict_true_does_not_raise_when_no_errors(self, tmp_path: Path) -> None:  # 54
        """strict=True must not raise when the stamp is completely valid."""
        toml, manifest = self._make_stamped_toml(tmp_path)
        findings = validate_stamp(toml, manifest, strict=True)
        assert findings == []

    # -- VERSION_MISMATCH ------------------------------------------------------

    def test_version_mismatch_is_always_error_non_strict(self, tmp_path: Path) -> None:  # 55
        """template_version != manifest template_version is always ERROR."""
        manifest = _write_manifest(tmp_path)  # has template_version=2.0.0
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "1.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        vm = [f for f in findings if f["code"] == "VERSION_MISMATCH"]
        assert vm, f"Expected VERSION_MISMATCH; got {findings}"
        assert vm[0]["level"] == "ERROR"

    def test_version_mismatch_strict_raises(self, tmp_path: Path) -> None:  # 56
        manifest = _write_manifest(tmp_path)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "0.9.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        with pytest.raises(StampValidationError) as exc_info:
            validate_stamp(toml, manifest, strict=True)
        vm = [f for f in exc_info.value.findings if f["code"] == "VERSION_MISMATCH"]
        assert vm

    def test_version_mismatch_message_contains_both_versions(self, tmp_path: Path) -> None:  # 57
        manifest = _write_manifest(tmp_path)  # template_version=2.0.0
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "1.2.3"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        vm = [f for f in findings if f["code"] == "VERSION_MISMATCH"]
        assert vm
        assert "1.2.3" in vm[0]["message"]
        assert "2.0.0" in vm[0]["message"]

    def test_version_mismatch_not_fired_when_manifest_has_no_version_field(self, tmp_path: Path) -> None:  # 58
        """If TEMPLATE_MANIFEST.json has no template_version key, no VERSION_MISMATCH is raised."""
        manifest_data = {k: v for k, v in SAMPLE_MANIFEST.items() if k != "template_version"}
        manifest = _write_manifest(tmp_path, manifest_data)
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "9.9.9"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        assert not any(f["code"] == "VERSION_MISMATCH" for f in findings)

    def test_version_match_produces_no_finding(self, tmp_path: Path) -> None:  # 59
        """When template_version in tool.toml equals manifest template_version, no VERSION_MISMATCH."""
        manifest = _write_manifest(tmp_path)  # template_version=2.0.0
        h = compute_manifest_sha256(manifest)
        content = (
            MINIMAL_TOOL_TOML
            + f'\n[template]\nstamp_source = "create"\ntemplate_manifest_hash = "{h}"\ntemplate_version = "2.0.0"\n'
        )
        toml = _write_tool_toml(tmp_path, content)
        findings = validate_stamp(toml, manifest, strict=False)
        assert not any(f["code"] == "VERSION_MISMATCH" for f in findings)
