# TechVault — `tool.toml` Canonical Schema Specification

**Version:** 2.0 (aligned with `TEMPLATE_MANIFEST.json` template_version `"2.0.0"`)
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
tool_id             = "<snake_case_identifier>"    # required — Python package name
name                = "<display name>"             # required — human-readable label
version             = "0.1.0"                      # required — SemVer string
entrypoint          = "<tool_id>.api.router:router" # required — Python import path
enabled_by_default  = false                        # required — bool

# ─── API ──────────────────────────────────────────────────────────────────────
[api]
mount_prefix = ""                    # string — additional URL prefix (empty = none)
tags         = ["tools:<tool_id>"]   # list[str] — FastAPI router tags

# ─── Capabilities ─────────────────────────────────────────────────────────────
[capabilities]
actions = ["search"]                 # list[str] — supported CLI/API actions

# ─── Template Stamp ───────────────────────────────────────────────────────────
# Written automatically by techvault-tool-create and techvault-tool-patch.
# Used by techvault-tool-template-check and techvault-tool-template-version
# to detect drift against the canonical TEMPLATE_MANIFEST.json.
[template]
template_version = "2.0.0"          # string  — required
manifest_hash    = "<sha256 hex>"   # string  — required
stamp_source     = "create"         # string  — optional; enum: "create" | "patch" | "manual"
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
| `mount_prefix` | string | Yes | Additional URL prefix. Empty string means no prefix — tool is mounted at `/v1/tools/<tool_id>`. |
| `tags` | list[string] | Yes | FastAPI router tags. Must include `"tools:<tool_id>"`. |

### 3.3 `[capabilities]` Section

| Field | Type | Required | Description |
|---|---|---|---|
| `actions` | list[string] | Yes | List of supported actions (e.g., `["search", "health"]`). |

### 3.4 `[template]` Section — Template Stamp

| Field | Type | Required | Description |
|---|---|---|---|
| `template_version` | string | Yes (stamp required) | Template version at stamp time. Derived from `template_version` field in `TEMPLATE_MANIFEST.json`. |
| `manifest_hash` | string | Yes (stamp required) | SHA-256 of the **canonical JSON serialization** of `TEMPLATE_MANIFEST.json` at stamp time. See §4. |
| `stamp_source` | string | No | How the stamp was written. Enum: `"create"`, `"patch"`, `"manual"`. Default assumed `"manual"` when absent. |

**Why `stamped_at` (timestamp) is intentionally omitted:**
A timestamp field would make `tool.toml` non-deterministic across identical scaffold runs and would need to be explicitly excluded from every comparison. It adds no information for drift detection (which only cares about template version and manifest content, not when the stamp was written). Omitted entirely to preserve determinism.

---

## 4. Manifest Hash Computation

### 4.1 Algorithm

The `manifest_hash` is computed as:

```
sha256( canonical_json_serialization( parse_json( TEMPLATE_MANIFEST.json ) ) )
```

**Step by step:**

1. Read `TEMPLATE_MANIFEST.json` as a UTF-8 string.
2. Parse it as JSON (standard `json.loads`).
3. Re-serialize to a canonical string using:
   - `json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`
   - Append exactly one newline character (`'\n'`).
4. Encode the canonical string as UTF-8 bytes.
5. Compute `sha256` of those bytes.
6. Record the lowercase hex digest.

**Why canonical serialization instead of raw-bytes hashing:**
Raw-byte hashing is sensitive to editor-introduced whitespace changes (trailing spaces, CRLF vs LF, BOM). Canonical JSON serialization is stable across all platforms and editors. The `sort_keys=True` option ensures key ordering is stable regardless of Python dict insertion order. This is the same approach used for `response_hash` in tool responses.

### 4.2 Reference Python Implementation

```python
import hashlib
import json
from pathlib import Path

def compute_manifest_sha256(manifest_path: Path) -> str:
    raw = manifest_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    canonical = (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
```

This function is the **canonical implementation**. All tools must use this exact algorithm.
The reference implementation lives in `tools/tool_common/stamp.py`.

### 4.3 Canonical Manifest Location

| Context | Manifest Path |
|---|---|
| Stamping at creation (`techvault-tool-create`) | `tools/tool_template/TEMPLATE_MANIFEST.json` in the `tv_tool_template` workspace |
| Stamping at upgrade (`techvault-tool-patch`) | Same — always the workspace canonical copy |
| Checking for drift (`techvault-tool-template-check`) | Same — the workspace canonical copy is the authority |

**The tool repo does NOT contain a local copy of `TEMPLATE_MANIFEST.json`.** The stamp in `tool.toml` is compared against the workspace manifest at check time.

---

## 5. TOML Formatting Rules

When writing or updating the `[template]` section programmatically:

1. **Section position:** `[template]` is always the **last section** in the file.
2. **Key order within `[template]`:** alphabetical — `manifest_hash`, `stamp_source`, `template_version`.
3. **String quoting:** double quotes only (no single quotes).
4. **No trailing whitespace** on any line.
5. **Single trailing newline** at end of file.
6. **Preserve all other sections** exactly as they were — the writer only touches the `[template]` section.
7. **Preserve comments** in non-`[template]` sections. Comments inside the old `[template]` section are discarded on overwrite.

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
manifest_hash    = "a3f1c2d4e5b6a7f8e9c0d1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2"
stamp_source     = "create"
template_version = "2.0.0"
```

---

## 7. Validation Rules for `techvault-tool-template-check`

### 7.1 Missing `[template]` section

| Mode | Behavior |
|---|---|
| Default (non-strict) | `WARN` — "Missing [template] section in tool.toml" |
| `--strict` | `ERROR` → exit 1 |

### 7.2 Missing `template_version` or `manifest_hash`

| Mode | Behavior |
|---|---|
| Default (non-strict) | `WARN` — "Missing field: `template_version`" / "Missing field: `manifest_hash`" |
| `--strict` | `ERROR` → exit 1 |

### 7.3 `manifest_hash` mismatch

Always `ERROR` regardless of strict mode. A mismatch means the tool repo was generated from a different manifest than the current one — this is drift.

```
manifest_hash mismatch: tool.toml has '<recorded>', computed from TEMPLATE_MANIFEST.json is '<current>'
```

### 7.4 Invalid `stamp_source`

Always `WARN` (not ERROR). The field is optional and informational.

### 7.5 JSON Report Keys

When `techvault-tool-template-check` emits a JSON report, each finding must include:

```json
{
  "field": "template.manifest_hash",
  "severity": "ERROR",
  "message": "manifest_hash mismatch: ..."
}
```

Report-level keys:

```json
{
  "tool_id": "document_text_search",
  "toml_path": "path/to/tool.toml",
  "manifest_path": "path/to/TEMPLATE_MANIFEST.json",
  "compliant": false,
  "findings": [ ... ]
}
```

### 7.6 Exit Codes

| Exit code | Meaning |
|---|---|
| 0 | No ERROR-severity findings (WARNs are acceptable) |
| 1 | One or more ERROR findings |
| 2 | Fatal error (cannot parse tool.toml, manifest not found) |

---

## 8. `techvault-tool-template-version` Behavior

`techvault-tool-template-version` reads `tool.toml` from one or more tool repos and reports:

- `tool_id`
- `template_version` (from `[template]` section, or `"<no stamp>"` if missing)
- `manifest_hash` (from `[template]`, or `"<no stamp>"`)
- `hash_status`: `"match"` | `"mismatch"` | `"no_stamp"`
- `stamp_source` (if present)

Output is deterministic JSON with `tools[]` sorted by `tool_id`.

---

## 9. Integration with Foundation Tools

| Tool | Stamp interaction |
|---|---|
| `techvault-tool-create` | Writes `[template]` section with `stamp_source = "create"` after scaffolding |
| `techvault-tool-patch` *(planned)* | Overwrites `[template]` section with `stamp_source = "patch"` after applying template changes |
| `techvault-tool-validate` | Does **not** check the stamp (structural compliance only) |
| `techvault-tool-security-scan` | Does **not** read `tool.toml` stamp |
| `techvault-tool-register` | Reads `tool_id` and `entrypoint` only; ignores `[template]` |
| `techvault-tool-sync` | Delegates to each tool; stamp checking is a separate gate |
| `techvault-tool-template-check` *(planned)* | Primary consumer — compares stamp against workspace manifest |
| `techvault-tool-template-version` *(planned)* | Reads and reports stamp across tool repos |
