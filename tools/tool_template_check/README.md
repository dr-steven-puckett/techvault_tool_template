# tool_template_check

Validates the `[template]` stamp in a TechVault tool's `tool.toml` against a
`TEMPLATE_MANIFEST.json`.

## CLI Usage

```
techvault-tool-template-check <tool_path> [--manifest <path>] [--strict]
```

| Argument | Default | Description |
|---|---|---|
| `tool_path` | required | Path to the tool repo directory (must contain `tool.toml`) |
| `--manifest` | `tools/tool_template/TEMPLATE_MANIFEST.json` | Manifest to validate against |
| `--strict` | off | Exit 2 if any finding exists |

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | No findings |
| `1` | WARN findings only (non-strict) |
| `2` | ERROR findings present, or any finding when `--strict` |

## JSON Report

Output is a single canonical JSON object (keys sorted, compact):

```json
{
  "computed_manifest_hash": "<64-char hex or null>",
  "expected_manifest_hash": "<64-char hex or null>",
  "findings": [...],
  "manifest_path": "...",
  "strict": false,
  "template": {...},
  "tool_path": "..."
}
```

## Finding Codes

See `docs/TOOL_TOML_SPEC.md §7.4` for the base code table. This tool emits all spec codes
plus the tool-level extensions below.

| Code | Level | Description |
|---|---|---|
| `STAMP_MISSING` | WARN / ERROR (strict) | `[template]` section absent from `tool.toml` |
| `STAMP_KEY_MISSING` | WARN / ERROR (strict) | A required key is absent from `[template]` |
| `HASH_INVALID` | ERROR | `template_manifest_hash` does not match `^[0-9a-f]{64}$` |
| `HASH_MISMATCH` | ERROR | Recorded hash does not equal computed hash |
| `STAMP_SOURCE_INVALID` | ERROR | `stamp_source` value not in `{"create","patch","manual"}` |
| `VERSION_MISMATCH` | ERROR | `template_version` differs from manifest's `template_version` field |
| `TOML_MISSING` | ERROR | `tool.toml` not found |
| `TOML_INVALID` | ERROR | `tool.toml` cannot be parsed as TOML |
| `MANIFEST_MISSING` | ERROR | `TEMPLATE_MANIFEST.json` cannot be read |
| `LOCAL_MANIFEST_MISSING` | **WARN always** | Tool repo root does not contain a `TEMPLATE_MANIFEST.json` audit-record copy. This level never escalates to ERROR — only the exit code changes in `--strict` mode. |
| `UNHANDLED_EXCEPTION` | ERROR | Unexpected internal error (I/O failure or code bug) |

`LOCAL_MANIFEST_MISSING` and `UNHANDLED_EXCEPTION` are tool-level extension codes not in `docs/TOOL_TOML_SPEC.md §7.4`. They are stable string codes and will not be renamed.

## Run Directly

```bash
python tools/tool_template_check/checker.py <tool_path>
```
