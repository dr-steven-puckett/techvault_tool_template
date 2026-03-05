# TechVault — `tool.toml` Canonical Schema Specification

**Version:** 2.1 (aligned with `TEMPLATE_MANIFEST.json` template_version `"2.0.0"`)
**Authoritative location:** `docs/TOOL_TOML_SPEC.md`
**Machine-readable inventory:** `tools/tool_template/TEMPLATE_MANIFEST.json`

This document is the normative reference for the `tool.toml` file present in every TechVault tool repository.

---

## 1. Purpose

`tool.toml` is the configuration file that:

1. Identifies a tool repository and its integration contract with TechVault.
2. Declares the capabilities and API surface of the tool.
3. Records the **template stamp** — a record of which template version and manifest content baseline the repo was generated from or last upgraded to.

---

## 2. Full Schema

```toml
# ─── Identity ─────────────────────────────────────────────────────────────────
tool_id             = "<snake_case_identifier>"     # required — Python package name
name                = "<display name>"              # required — human-readable label
version             = "0.1.0"                       # required — SemVer string
entrypoint          = "<tool_id>.api.router:router" # required — Python import path
enabled_by_default  = false                         # required — bool

# ─── API ──────────────────────────────────────────────────────────────────────
[api]
mount_prefix = ""                    # string — additional URL prefix (empty = none)
tags         = ["tools:<tool_id>"]   # list[str] — FastAPI router tags

# ─── Capabilities ─────────────────────────────────────────────────────────────
[capabilities]
actions = ["search"]                 # list[str] — supported CLI/API actions

# ─── Template Stamp ───────────────────────────────────────────────────────────
# Written automatically by techvault-tool-create and techvault-tool-patch.
# Used by techvault-tool-template-check to detect drift against TEMPLATE_MANIFEST.json.
[template]
stamp_source           = "create"         # string  — required; enum: "create"|"patch"|"manual"
template_manifest_hash = "<sha256 hex>"   # string  — required; 64-char lowercase hex
template_version       = "2.0.0"          # string  — required
```

---

## 3. Field Descriptions

### 3.1 Root Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_id` | string | Yes | Python package name (`snake_case`). Must be a valid Python identifier. |
| `name` | string | Yes | Human-readable display name. |
| `version` | string | Yes | SemVer string for the tool's own version (independent of template version). |
| `entrypoint` | string | Yes | FastAPI router import path, format: `<package>.api.router:router`. |
| `enabled_by_default` | bool | Yes | Whether TechVault mounts the router without explicit opt-in. |

### 3.2 `[api]` Section

| Field | Type | Required | Description |
|---|---|---|---|
| `mount_prefix` | string | Yes | Additional URL prefix. Empty string means no prefix. |
| `tags` | list[string] | Yes | FastAPI router tags. Must include `"tools:<tool_id>"`. |

### 3.3 `[capabilities]` Section

| Field | Type | Required | Description |
|---|---|---|---|
| `actions` | list[string] | Yes | List of supported actions (e.g., `["search", "health"]`). |

### 3.4 `[template]` Section — Template Stamp

The `[template]` section MUST have exactly these keys (in alphabetical order):

| Field | Type | Required | Description |
|---|---|---|---|
| `stamp_source` | string | Yes | How the stamp was written. Enum: `"create"`, `"patch"`, `"manual"`. |
| `template_manifest_hash` | string | Yes | SHA-256 of the **canonical JSON serialization** of `TEMPLATE_MANIFEST.json` at stamp time. See §4. Must be 64-char lowercase hex. |
| `template_version` | string | Yes | Template version at stamp time. Derived from `template_version` field in `TEMPLATE_MANIFEST.json`. |

**Why `stamped_at` (timestamp) is intentionally omitted:**

A timestamp field would make `tool.toml` non-deterministic across identical scaffold runs and would need to be explicitly excluded from every comparison. It provides no value for drift detection — drift is detected by comparing `template_manifest_hash` to the current canonical hash, not by when stamping occurred. Timestamps are omitted entirely to preserve determinism.

---

## 4. Manifest Hash Computation

### 4.1 Algorithm

The `template_manifest_hash` is computed as:

```
sha256( canonical_json_bytes( parse_json( raw_bytes( TEMPLATE_MANIFEST.json ) ) ) )
```

**Step by step:**

1. Read `TEMPLATE_MANIFEST.json` as raw bytes.
2. Decode as UTF-8 (`errors="strict"`).
3. Parse as JSON (standard `json.loads`).
4. Re-serialize to a canonical string using:
   - `json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`
   - Append exactly one newline character (`'\n'`).
5. Encode the canonical string as UTF-8 bytes.
6. Compute `sha256` of those bytes.
7. Record the lowercase hex digest (64 characters).

**Why canonical serialization instead of raw-bytes hashing:**
Raw-byte hashing is sensitive to editor-introduced whitespace changes (trailing spaces, CRLF vs LF, BOM). Canonical JSON serialization is stable across all platforms and editors. The `sort_keys=True` option ensures key ordering is stable regardless of Python dict insertion order.

**Why `normalize_manifest_bytes` accepts bytes or str (not dict):**
The public API of `normalize_manifest_bytes` accepts raw file content (bytes or JSON string) rather than a pre-parsed dict. This allows the function to serve as both an input-validation point and a canonical serializer without requiring the caller to pre-parse the file.

### 4.2 Reference Python Implementation

```python
import hashlib
import json
from pathlib import Path

def normalize_manifest_bytes(data: bytes | str) -> bytes:
    """Canonical UTF-8 bytes from raw bytes or JSON string."""
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
    raw = Path(manifest_path).read_bytes()
    canonical = normalize_manifest_bytes(raw)
    return hashlib.sha256(canonical).hexdigest()
```

This implementation is authoritative. All tools must use `tools/tool_common/stamp.py` which contains these exact algorithms.

### 4.3 Hash Format Validation

A valid `template_manifest_hash` must match the regex `^[0-9a-f]{64}$` — exactly 64 lowercase hexadecimal characters.

Any recorded value that does not match this regex is **always an ERROR** (regardless of strict mode).

### 4.4 Canonical Manifest Location

**Decision: Option A — tool repos carry their own `TEMPLATE_MANIFEST.json`.**

When `techvault-tool-create` scaffolds a new tool repo it copies the current `TEMPLATE_MANIFEST.json` from the template source into the **tool repo root** alongside `tool.toml`. This local copy records the exact manifest baseline the tool was created from.

| Context | Manifest Path |
|---|---|
| Stamping at creation (`techvault-tool-create`) | `tools/tool_template/TEMPLATE_MANIFEST.json` in the workspace (source of truth used to write the stamp and copy into the tool repo) |
| Stamping at upgrade (`techvault-tool-patch`) *(planned)* | The workspace canonical copy — overwrites both the stamp and the tool repo's local `TEMPLATE_MANIFEST.json` |
| Checking for drift (`techvault-tool-template-check`) *(planned)* | **Default:** `tools/tool_template/TEMPLATE_MANIFEST.json` — the workspace canonical copy. Pass `--manifest <path>` to test against older template versions, forks, or a pinned CI copy (see §10.1). |

**Rationale:**

- The workspace canonical `TEMPLATE_MANIFEST.json` is the live authority — routine drift detection compares any tool against it by default.
- The local `TEMPLATE_MANIFEST.json` copied into each tool repo root at scaffold time is an **audit record** of the baseline used; it is not the default check target.
- The `template_manifest_hash` in `tool.toml` is the integrity check over the checked manifest — pointing `--manifest` at the local tool copy lets you verify the local copy has not been tampered with.
- When `--manifest` points at the workspace canonical, `VERSION_MISMATCH` fires if the tool's `template_version` no longer matches the current template, cleanly distinguishing ordinary drift from hash corruption.

---

## 5. TOML Formatting Rules

When `write_stamp()` in `tools/tool_common/stamp.py` writes or updates the `[template]` section:

1. **Section position:** `[template]` is always the **last section** in the file — even if it would sort earlier alphabetically than other sections.
2. **Key order within `[template]`:** strictly alphabetical — `stamp_source`, `template_manifest_hash`, `template_version`.
3. **String quoting:** double quotes only (no single quotes).
4. **No trailing whitespace** on any line.
5. **Single trailing newline** at end of file.
6. **Preserve all other sections** exactly as they were. The writer strips the old `[template]` section and appends a fresh deterministic one.
7. **Comments:** Comments inside the old `[template]` section are discarded on overwrite (not feasible to preserve with the current line-based strip/rewrite approach). Comments in all other sections are preserved verbatim.

**Determinism guarantee:** identical inputs (same existing `tool.toml` content, same stamp parameters) always produce byte-identical output. Two consecutive calls to `write_stamp()` with the same arguments produce a byte-identical file.

These rules are enforced by `tools/tool_common/stamp.py::write_stamp()`.

---

## 6. Canonical `tool.toml` Example

```toml
tool_id             = "document_text_search"
name                = "document_text_search"
version             = "0.1.0"
entrypoint          = "document_text_search.api.router:router"
enabled_by_default  = false

[api]
mount_prefix = ""
tags         = ["tools:document_text_search"]

[capabilities]
actions = ["search"]

[template]
stamp_source           = "create"
template_manifest_hash = "a3f1c2d4e5b6a7f8e9c0d1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2"
template_version       = "2.0.0"
```

---

## 7. Validation Rules for `techvault-tool-template-check`

### 7.1 Severity Levels and Exit Codes

| Exit Code | Meaning |
|---|---|
| `0` | No findings, or INFO-only findings |
| `1` | WARN findings exist, no ERROR findings |
| `2` | ERROR findings exist (regardless of WARN count) |

### 7.2 Finding Object Keys (JSON report contract)

Each finding in the `findings` array must have these keys (in stable order when serialized):

| Key | Type | Description |
|---|---|---|
| `level` | `"WARN"` \| `"ERROR"` | Severity level |
| `code` | string | Stable finding code (see §7.4) |
| `message` | string | Human-readable description |
| `path` | string | Path to the field, e.g. `"tool.toml:[template].template_manifest_hash"` |
| `details` | object | Optional. Extra context (JSON-serializable, keys sorted when serialized). Only present when relevant. |

### 7.3 Top-Level Report Object

```json
{
  "tool_path": "path/to/tool.toml",
  "manifest_path": "path/to/TEMPLATE_MANIFEST.json",
  "strict": false,
  "computed_manifest_hash": "<64-char hex>",
  "expected_manifest_hash": "<64-char hex or null if manifest missing>",
  "template": { "stamp_source": "create", "template_manifest_hash": "...", "template_version": "2.0.0" },
  "findings": [ ... ]
}
```

### 7.4 Stable Finding Codes

| Code | Description | Default Level | Always Override? |
|---|---|---|---|
| `STAMP_MISSING` | `[template]` section is absent | WARN | ERROR in strict |
| `STAMP_KEY_MISSING` | A required key is absent from `[template]` | WARN | ERROR in strict |
| `HASH_INVALID` | `template_manifest_hash` does not match `^[0-9a-f]{64}$` | ERROR | Always ERROR |
| `HASH_MISMATCH` | Recorded hash does not equal computed hash | ERROR | Always ERROR |
| `STAMP_SOURCE_INVALID` | `stamp_source` value is not in the allowed enum | ERROR | Always ERROR |
| `VERSION_MISMATCH` | `template_version` differs from `TEMPLATE_MANIFEST.json` version field | ERROR | Always ERROR |
| `TOML_MISSING` | `tool.toml` file not found | ERROR | Always ERROR |
| `TOML_INVALID` | `tool.toml` cannot be parsed as TOML | ERROR | Always ERROR |
| `MANIFEST_MISSING` | `TEMPLATE_MANIFEST.json` cannot be read | ERROR | Always ERROR |

### 7.5 Validation Rule Table

| Condition | non-strict | strict |
|---|---|---|
| `[template]` section absent | WARN (`STAMP_MISSING`) | ERROR (`STAMP_MISSING`) + raise |
| Required key absent (`stamp_source`, `template_manifest_hash`, `template_version`) | WARN (`STAMP_KEY_MISSING`) | ERROR (`STAMP_KEY_MISSING`) + raise |
| `template_manifest_hash` format invalid (not `^[0-9a-f]{64}$`) | ERROR (`HASH_INVALID`) | ERROR (`HASH_INVALID`) + raise |
| Hash mismatch (recorded ≠ computed) | ERROR (`HASH_MISMATCH`) | ERROR (`HASH_MISMATCH`) + raise |
| `stamp_source` value not in `{"create","patch","manual"}` | ERROR (`STAMP_SOURCE_INVALID`) | ERROR + raise |
| `template_version` ≠ manifest's `template_version` field (when field present in manifest) | ERROR (`VERSION_MISMATCH`) | ERROR + raise |
| `tool.toml` not found | ERROR (`TOML_MISSING`) | ERROR + raise |
| `TEMPLATE_MANIFEST.json` not readable | ERROR (`MANIFEST_MISSING`) | ERROR + raise |

**Note:** When `[template]` is absent, `validate_stamp()` returns early (only one finding). It does not continue to check individual keys.

### 7.6 Findings Sort Order

Findings are returned sorted by `(level_severity, code, path)` where `ERROR` sorts before `WARN` (lower sort key = higher priority).

---

## 8. `write_stamp()` API Contract

Signature:

```python
def write_stamp(
    toml_path: str | Path,
    *,
    template_version: str,
    template_manifest_hash: str,
    stamp_source: str,
) -> None: ...
```

All parameters after `toml_path` are **keyword-only** (enforced by `*`).

Behaviour:
- Reads existing `tool.toml` if present; creates if absent.
- Strips any existing `[template]` section.
- Appends a fresh `[template]` section as the last section.
- Raises `ValueError` if `stamp_source` is not in `{"create", "patch", "manual"}`.
- Writes deterministically: byte-identical output for identical inputs.

---

## 9. Integration with Foundation Tools

| Tool | Stamp interaction |
|---|---|
| `techvault-tool-create` | Writes `[template]` section with `stamp_source = "create"` immediately after scaffolding |
| `techvault-tool-patch` *(planned)* | Overwrites `[template]` section with `stamp_source = "patch"` after applying template changes |
| `techvault-tool-validate` | Does **not** check the stamp (structural compliance only) |
| `techvault-tool-security-scan` | Does **not** read `tool.toml` stamp |
| `techvault-tool-register` | Reads `tool_id` and `entrypoint` only; ignores `[template]` |
| `techvault-tool-sync` | Delegates to each tool; stamp checking is a separate gate |
| `techvault-tool-template-check` *(planned)* | Primary consumer — compares stamp against manifest (default: workspace canonical; `--manifest <path>` to override) |
| `techvault-tool-template-version` *(planned)* | Reads or repairs the `[template]` stamp; `--check` reports findings, `--write` writes `stamp_source="manual"` |

---

## 10. CLI Contracts

### 10.1 `techvault-tool-template-check` *(planned)*

```
techvault-tool-template-check <tool_path> [--manifest <path>] [--strict]
```

| Argument | Default | Description |
|---|---|---|
| `tool_path` | required | Path to the tool repo directory (must contain `tool.toml`) |
| `--manifest` | `tools/tool_template/TEMPLATE_MANIFEST.json` | Manifest to validate against. Override to test older template versions, forks, or a pinned CI copy. |
| `--strict` | off | Treat WARN findings as errors; exit code 2 if any finding is present |

The workspace canonical copy is the authority for routine drift detection. Use `--manifest` to point at the tool repo's own local copy (`<tool_repo>/TEMPLATE_MANIFEST.json`) when auditing scaffold-time integrity in isolation from the current workspace state.

### 10.2 `techvault-tool-template-version` *(planned)*

Manages the `[template]` stamp in `tool.toml`.

```
techvault-tool-template-version <tool_path> (--check | --write) [--manifest <path>]
```

| Mode | `[template]` absent | `[template]` present |
|---|---|---|
| `--check` | Report `STAMP_MISSING` (exit 1 non-strict, 2 strict) | Run full `validate_stamp` against manifest; print findings |
| `--write` | Write stamp with `stamp_source = "manual"` | Overwrite stamp with `stamp_source = "manual"` |

**Responsibility boundary:**

| Tool | Responsibility |
|---|---|
| `techvault-tool-template-check` | Detect and report stamp drift (read-only) |
| `techvault-tool-template-version` | Repair or write missing stamps |
