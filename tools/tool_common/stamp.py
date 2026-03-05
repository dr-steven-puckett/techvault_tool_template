"""
tool_common.stamp
~~~~~~~~~~~~~~~~~
Helpers for reading, computing, writing, and validating template stamps
in tool.toml files.

Public API
----------
normalize_manifest_bytes(data)                -- Canonical UTF-8 JSON bytes from bytes or str JSON.
compute_manifest_sha256(manifest_path)        -- SHA-256 hex of canonical manifest bytes.
read_tool_toml(toml_path)                     -- Parse tool.toml -> dict.
write_stamp(toml_path, *, template_version,   -- Write/overwrite [template] section in tool.toml.
            template_manifest_hash, stamp_source)
validate_stamp(toml_path, manifest_path, *)   -- Validate stamp fields; return list of findings.
StampValidationError                          -- Raised by validate_stamp in strict mode.

Hash algorithm (CANONICAL — must not change without a version bump)
---------------------------------------------------------------------
  input  : raw bytes or str containing TEMPLATE_MANIFEST.json content
  decode : bytes -> UTF-8 text (errors="strict")
  parse  : json.loads(text) -> dict
  bytes  : json.dumps(data, sort_keys=True, separators=(',',':'), ensure_ascii=False) + '\\n'
           encoded as UTF-8
  digest : sha256 lowercase hex
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Valid values for the stamp_source field (ordered for deterministic messaging).
VALID_STAMP_SOURCES: frozenset[str] = frozenset({"create", "manual", "patch"})

#: Keys written to the [template] section, in alphabetical order.
_TEMPLATE_KEYS_ORDERED = ("stamp_source", "template_manifest_hash", "template_version")

#: Regex for valid manifest hash strings (lowercase hex, exactly 64 chars).
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

#: Sort keys for finding levels (lower = higher severity, sorts first).
_LEVEL_SEV: dict[str, int] = {"ERROR": 0, "WARN": 1}


# ---------------------------------------------------------------------------
# Canonical bytes / hash
# ---------------------------------------------------------------------------


def normalize_manifest_bytes(data: bytes | str) -> bytes:
    """
    Return the canonical UTF-8 byte representation of a JSON manifest.

    Parameters
    ----------
    data : bytes or str
        Raw bytes (decoded as UTF-8 strict) or a JSON string.

    Returns
    -------
    bytes
        Canonical UTF-8 bytes: json.dumps(sort_keys=True, compact) + '\\n'

    Raises
    ------
    UnicodeDecodeError   if *data* is bytes and not valid UTF-8.
    json.JSONDecodeError if *data* is not valid JSON.

    Rules (authoritative — see docs/TOOL_TOML_SPEC.md §4):
    - decode bytes as UTF-8 (errors="strict")
    - json.dumps with sort_keys=True, separators=(',', ':'), ensure_ascii=False
    - one trailing newline ('\\n') appended
    - encoded as UTF-8
    """
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="strict")
    else:
        text = data
    obj = json.loads(text)
    canonical = (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    )
    return canonical.encode("utf-8")


def compute_manifest_sha256(manifest_path: Path) -> str:
    """
    Return the lowercase hex SHA-256 of the canonical JSON serialization of
    TEMPLATE_MANIFEST.json at *manifest_path*.

    Algorithm (from docs/TOOL_TOML_SPEC.md §4.1):
    1. Read file as bytes.
    2. Canonicalize with normalize_manifest_bytes().
    3. sha256 of the resulting bytes.

    This is stable across platforms and editor whitespace changes.
    """
    raw = Path(manifest_path).read_bytes()
    canonical = normalize_manifest_bytes(raw)
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
    template_manifest_hash: str,
    stamp_source: str,
) -> str:
    """
    Return a deterministic [template] TOML section string.

    Keys are written in alphabetical order:
      stamp_source, template_manifest_hash, template_version

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
        f'stamp_source = "{stamp_source}"\n'
        f'template_manifest_hash = "{template_manifest_hash}"\n'
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
    *,
    template_version: str,
    template_manifest_hash: str,
    stamp_source: str,
) -> None:
    """
    Write (or overwrite) the [template] section in *toml_path*.

    Contract (from docs/TOOL_TOML_SPEC.md §5):
    - [template] is always the last section in the file.
    - Keys within [template] are in alphabetical order:
      stamp_source, template_manifest_hash, template_version.
    - String values use double quotes only.
    - All other sections and fields are preserved exactly.
    - File ends with a single trailing newline.

    Parameters (all keyword-only except toml_path)
    -----------------------------------------------
    toml_path              : Path to the tool.toml file to update.
    template_version       : Value for the template_version key.
    template_manifest_hash : SHA-256 hex string for the template_manifest_hash key.
    stamp_source           : One of "create", "patch", "manual".

    Raises
    ------
    ValueError  if stamp_source is not a member of VALID_STAMP_SOURCES.
    """
    existing = Path(toml_path).read_text(encoding="utf-8")
    stripped = _strip_template_section(existing)
    block = _build_template_block(template_version, template_manifest_hash, stamp_source)
    # Exactly one blank line between the last existing section and [template]
    Path(toml_path).write_text(stripped + "\n\n" + block, encoding="utf-8")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


class StampValidationError(Exception):
    """Raised by validate_stamp when strict=True and ERROR-severity findings exist."""

    def __init__(self, findings: list[dict]) -> None:
        self.findings = findings
        errors = [f["message"] for f in findings if f.get("level") == "ERROR"]
        super().__init__("; ".join(errors))


def _finding(
    level: str,
    code: str,
    message: str,
    path: str,
    details: dict | None = None,
) -> dict:
    """Build a finding dict with required keys."""
    f: dict = {"level": level, "code": code, "message": message, "path": path}
    if details is not None:
        f["details"] = details
    return f


def validate_stamp(
    toml_path: Path,
    manifest_path: Path,
    *,
    strict: bool = False,
) -> list[dict]:
    """
    Validate the [template] stamp in *toml_path* against *manifest_path*.

    Returns a list of finding dicts, each with keys:
      "level"   : str   — "ERROR" or "WARN"
      "code"    : str   — stable finding code (e.g. "STAMP_MISSING")
      "message" : str   — human-readable description
      "path"    : str   — path to the field, e.g. "tool.toml:[template].template_manifest_hash"
      "details" : dict  — optional; extra context (only present when relevant)

    Findings are sorted by (ERROR before WARN, then code, then path).

    Validation rules (from docs/TOOL_TOML_SPEC.md §7):
    - Missing tool.toml              → ERROR always
    - Missing [template] section     → WARN (non-strict) or ERROR (strict)
    - Missing required key           → WARN (non-strict) or ERROR (strict)
    - Invalid template_manifest_hash → ERROR always
    - Hash mismatch                  → ERROR always
    - Invalid stamp_source           → ERROR always

    Parameters
    ----------
    strict : When True, any ERROR-severity finding causes StampValidationError
             to be raised after all checks complete.
    """
    findings: list[dict] = []
    toml_path = Path(toml_path)
    manifest_path = Path(manifest_path)

    # ── tool.toml present and parseable? ─────────────────────────────────────
    if not toml_path.exists():
        findings.append(_finding(
            "ERROR", "TOML_MISSING",
            f"tool.toml not found: {toml_path}",
            str(toml_path),
        ))
        if strict:
            raise StampValidationError(findings)
        return findings

    try:
        data = read_tool_toml(toml_path)
    except Exception as exc:
        findings.append(_finding(
            "ERROR", "TOML_INVALID",
            f"Cannot parse {toml_path}: {exc}",
            str(toml_path),
        ))
        if strict:
            raise StampValidationError(findings)
        return findings

    # ── Manifest data (hash + version field) ─────────────────────────────────
    try:
        manifest_raw = Path(manifest_path).read_bytes()
        computed_hash = hashlib.sha256(normalize_manifest_bytes(manifest_raw)).hexdigest()
        manifest_data: dict = json.loads(manifest_raw.decode("utf-8", errors="strict"))
        manifest_template_version: str | None = manifest_data.get("template_version")
    except Exception as exc:
        findings.append(_finding(
            "ERROR", "MANIFEST_MISSING",
            f"Cannot read manifest: {exc}",
            str(manifest_path),
        ))
        if strict:
            raise StampValidationError(findings)
        return findings

    template_section = data.get("template")

    # ── Missing entire [template] section ────────────────────────────────────
    if template_section is None:
        level = "ERROR" if strict else "WARN"
        findings.append(_finding(
            level, "STAMP_MISSING",
            "Missing [template] section in tool.toml",
            "tool.toml:[template]",
        ))
        findings.sort(key=lambda f: (_LEVEL_SEV.get(f["level"], 99), f["code"], f.get("path", "")))
        if strict and any(f["level"] == "ERROR" for f in findings):
            raise StampValidationError(findings)
        return findings

    # ── template_version ─────────────────────────────────────────────────────
    tv = template_section.get("template_version")
    if not isinstance(tv, str) or not tv:
        level = "ERROR" if strict else "WARN"
        findings.append(_finding(
            level, "STAMP_KEY_MISSING",
            "Missing field: template_version",
            "tool.toml:[template].template_version",
        ))
    elif manifest_template_version is not None and tv != manifest_template_version:
        findings.append(_finding(
            "ERROR", "VERSION_MISMATCH",
            (
                f"template_version mismatch: "
                f"tool.toml has {tv!r}, "
                f"manifest has {manifest_template_version!r}"
            ),
            "tool.toml:[template].template_version",
            {"recorded": tv, "expected": manifest_template_version},
        ))

    # ── stamp_source ─────────────────────────────────────────────────────────
    if "stamp_source" not in template_section:
        level = "ERROR" if strict else "WARN"
        findings.append(_finding(
            level, "STAMP_KEY_MISSING",
            "Missing field: stamp_source",
            "tool.toml:[template].stamp_source",
        ))
    else:
        src = template_section["stamp_source"]
        if src not in VALID_STAMP_SOURCES:
            findings.append(_finding(
                "ERROR", "STAMP_SOURCE_INVALID",
                (
                    f"stamp_source has unrecognized value {src!r}; "
                    f"expected one of {sorted(VALID_STAMP_SOURCES)}"
                ),
                "tool.toml:[template].stamp_source",
            ))

    # ── template_manifest_hash ────────────────────────────────────────────────
    if "template_manifest_hash" not in template_section:
        level = "ERROR" if strict else "WARN"
        findings.append(_finding(
            level, "STAMP_KEY_MISSING",
            "Missing field: template_manifest_hash",
            "tool.toml:[template].template_manifest_hash",
        ))
    else:
        recorded = template_section["template_manifest_hash"]
        if not _HASH_RE.match(recorded):
            findings.append(_finding(
                "ERROR", "HASH_INVALID",
                f"template_manifest_hash has invalid format: {recorded!r}",
                "tool.toml:[template].template_manifest_hash",
                {"expected_pattern": "^[0-9a-f]{64}$", "got": recorded},
            ))
        elif recorded != computed_hash:
            findings.append(_finding(
                "ERROR", "HASH_MISMATCH",
                (
                    f"template_manifest_hash mismatch: "
                    f"tool.toml has {recorded!r}, "
                    f"computed from {manifest_path.name} is {computed_hash!r}"
                ),
                "tool.toml:[template].template_manifest_hash",
                {"recorded": recorded, "computed": computed_hash},
            ))

    # ── Sort and raise if needed ──────────────────────────────────────────────
    findings.sort(
        key=lambda f: (_LEVEL_SEV.get(f["level"], 99), f["code"], f.get("path", ""))
    )
    if strict and any(f["level"] == "ERROR" for f in findings):
        raise StampValidationError(findings)

    return findings
