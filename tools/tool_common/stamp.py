"""
tool_common.stamp
~~~~~~~~~~~~~~~~~
Helpers for reading, computing, writing, and validating template stamps
in tool.toml files.

Public API
----------
normalize_manifest_bytes(data)              -- Canonical UTF-8 JSON bytes of a manifest dict.
compute_manifest_sha256(manifest_path)      -- SHA-256 hex of canonical manifest bytes.
read_tool_toml(toml_path)                   -- Parse tool.toml -> dict.
write_stamp(toml_path, template_version,    -- Write/overwrite [template] section in tool.toml.
            manifest_hash, stamp_source)
validate_stamp(toml_path, manifest_path, *) -- Validate stamp fields; return list of findings.
StampValidationError                        -- Raised by validate_stamp in strict mode.

Hash algorithm (CANONICAL — must not change without a version bump)
---------------------------------------------------------------------
  input  : parsed TEMPLATE_MANIFEST.json dict
  bytes  : json.dumps(data, sort_keys=True, separators=(',',':'), ensure_ascii=False) + '\\n'
           encoded as UTF-8
  digest : sha256 lowercase hex
"""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Valid values for the stamp_source field (ordered for deterministic messaging).
VALID_STAMP_SOURCES: frozenset[str] = frozenset({"create", "manual", "patch"})

#: Keys written to the [template] section, in alphabetical order.
_TEMPLATE_KEYS_ORDERED = ("manifest_hash", "stamp_source", "template_version")


# ---------------------------------------------------------------------------
# Canonical bytes / hash
# ---------------------------------------------------------------------------


def normalize_manifest_bytes(data: dict) -> bytes:
    """
    Return the canonical UTF-8 byte representation of a parsed manifest dict.

    Rules (authoritative — see docs/TOOL_TOML_SPEC.md §4):
    - json.dumps with sort_keys=True, separators=(',', ':'), ensure_ascii=False
    - one trailing newline ('\\n') appended
    - encoded as UTF-8

    These rules are identical to tool_common.manifest.canonical_manifest_bytes.
    Both functions must stay in sync.
    """
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def compute_manifest_sha256(manifest_path: Path) -> str:
    """
    Return the lowercase hex SHA-256 of the canonical JSON serialization of
    TEMPLATE_MANIFEST.json at *manifest_path*.

    Algorithm (from docs/TOOL_TOML_SPEC.md §4.1):
    1. Read file as UTF-8 text.
    2. Parse as JSON.
    3. Re-serialize via normalize_manifest_bytes().
    4. sha256 of the resulting bytes.

    This is stable across platforms and editor whitespace changes.
    """
    raw = manifest_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    canonical = normalize_manifest_bytes(data)
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_tool_toml(toml_path: Path) -> dict:
    """
    Parse *toml_path* using tomllib and return the resulting dict.

    Raises
    ------
    FileNotFoundError  if the path does not exist.
    tomllib.TOMLDecodeError  if the file is not valid TOML.
    """
    with open(toml_path, "rb") as fh:
        return tomllib.load(fh)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def _build_template_block(
    template_version: str,
    manifest_hash: str,
    stamp_source: str,
) -> str:
    """
    Return a deterministic [template] TOML section string.

    Keys are written in alphabetical order:
      manifest_hash, stamp_source, template_version

    Raises
    ------
    ValueError  if stamp_source is not a member of VALID_STAMP_SOURCES.
    """
    if stamp_source not in VALID_STAMP_SOURCES:
        raise ValueError(
            f"stamp_source must be one of {sorted(VALID_STAMP_SOURCES)!r}; "
            f"got {stamp_source!r}"
        )
    return (
        "[template]\n"
        f'manifest_hash    = "{manifest_hash}"\n'
        f'stamp_source     = "{stamp_source}"\n'
        f'template_version = "{template_version}"\n'
    )


def _strip_template_section(text: str) -> str:
    """
    Remove any existing [template] section from TOML source *text*.

    The function processes line by line so it handles both mid-file and
    end-of-file positions correctly.  All other sections and lines are
    preserved verbatim.
    """
    lines = text.split("\n")
    result: list[str] = []
    inside_template = False

    for line in lines:
        stripped = line.strip()
        # Entering the [template] section
        if stripped == "[template]":
            inside_template = True
            continue
        # Leaving the [template] section (any other top-level section header)
        if inside_template and stripped.startswith("[") and not stripped.startswith("[template]"):
            inside_template = False
        if not inside_template:
            result.append(line)

    # Remove trailing blank lines so we can append cleanly
    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result)


def write_stamp(
    toml_path: Path,
    template_version: str,
    manifest_hash: str,
    stamp_source: str = "create",
) -> None:
    """
    Write (or overwrite) the [template] section in *toml_path*.

    Contract (from docs/TOOL_TOML_SPEC.md §5):
    - [template] is always the last section in the file.
    - Keys within [template] are in alphabetical order.
    - String values use double quotes only.
    - All other sections and fields are preserved exactly.
    - File ends with a single trailing newline.

    Parameters
    ----------
    toml_path        : Path to the tool.toml file to update.
    template_version : Value for the template_version key.
    manifest_hash    : SHA-256 hex string for the manifest_hash key.
    stamp_source     : One of "create", "patch", "manual" (default: "create").

    Raises
    ------
    ValueError  if stamp_source is not a member of VALID_STAMP_SOURCES.
    """
    existing = toml_path.read_text(encoding="utf-8")
    stripped = _strip_template_section(existing)
    block = _build_template_block(template_version, manifest_hash, stamp_source)
    # Exactly one blank line between the last existing section and [template]
    toml_path.write_text(stripped + "\n\n" + block, encoding="utf-8")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


class StampValidationError(ValueError):
    """Raised by validate_stamp when strict=True and ERROR-severity findings exist."""


def validate_stamp(
    toml_path: Path,
    manifest_path: Path,
    *,
    strict: bool = False,
) -> list[dict]:
    """
    Validate the [template] stamp in *toml_path* against *manifest_path*.

    Returns a list of finding dicts, each with keys:
      "field"    : str   — the field or check that failed
      "severity" : str   — "ERROR" or "WARN"
      "message"  : str   — human-readable description

    Validation rules (from docs/TOOL_TOML_SPEC.md §7):
    - Missing [template] section        → WARN (non-strict) or ERROR+raise (strict)
    - Missing template_version field    → WARN (non-strict) or ERROR+raise (strict)
    - Missing manifest_hash field       → WARN (non-strict) or ERROR+raise (strict)
    - manifest_hash value mismatch      → ERROR always (drift is always an error)
    - Invalid stamp_source value        → WARN always (informational field)

    Parameters
    ----------
    strict : When True, any ERROR-severity finding causes StampValidationError
             to be raised after all checks complete.
    """
    findings: list[dict] = []

    try:
        data = read_tool_toml(toml_path)
    except Exception as exc:
        raise ValueError(f"Cannot parse {toml_path}: {exc}") from exc

    template_section = data.get("template")

    # ── Missing entire [template] section ────────────────────────────────────
    if template_section is None:
        sev = "ERROR" if strict else "WARN"
        findings.append({
            "field": "template",
            "severity": sev,
            "message": "Missing [template] section in tool.toml",
        })
        if strict:
            raise StampValidationError(findings[-1]["message"])
        return findings

    # ── template_version ──────────────────────────────────────────────────────
    if "template_version" not in template_section:
        sev = "ERROR" if strict else "WARN"
        findings.append({
            "field": "template.template_version",
            "severity": sev,
            "message": "Missing field: template_version",
        })

    # ── stamp_source (optional; only warn on invalid value when present) ──────
    if "stamp_source" in template_section:
        src = template_section["stamp_source"]
        if src not in VALID_STAMP_SOURCES:
            findings.append({
                "field": "template.stamp_source",
                "severity": "WARN",
                "message": (
                    f"stamp_source has unrecognized value {src!r}; "
                    f"expected one of {sorted(VALID_STAMP_SOURCES)}"
                ),
            })

    # ── manifest_hash ─────────────────────────────────────────────────────────
    if "manifest_hash" not in template_section:
        sev = "ERROR" if strict else "WARN"
        findings.append({
            "field": "template.manifest_hash",
            "severity": sev,
            "message": "Missing field: manifest_hash",
        })
    else:
        recorded_hash = template_section["manifest_hash"]
        actual_hash = compute_manifest_sha256(manifest_path)
        if recorded_hash != actual_hash:
            findings.append({
                "field": "template.manifest_hash",
                "severity": "ERROR",
                "message": (
                    f"manifest_hash mismatch: "
                    f"tool.toml has {recorded_hash!r}, "
                    f"computed from {manifest_path.name} is {actual_hash!r}"
                ),
            })

    # ── Strict-mode gate ──────────────────────────────────────────────────────
    if strict:
        errors = [f for f in findings if f["severity"] == "ERROR"]
        if errors:
            raise StampValidationError("; ".join(e["message"] for e in errors))

    return findings
