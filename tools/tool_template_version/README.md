# tool_template_version

Reads or repairs the `[template]` stamp in a TechVault tool's `tool.toml`.

## CLI Usage

```
techvault-tool-template-version <tool_path> (--check | --write) [--manifest <path>]
```

| Argument | Default | Description |
|---|---|---|
| `tool_path` | required | Path to the tool repo directory (must contain `tool.toml`) |
| `--check` | — | Validate the stamp and report findings (read-only) |
| `--write` | — | Write (or overwrite) the stamp with `stamp_source = "manual"` |
| `--manifest` | `tools/tool_template/TEMPLATE_MANIFEST.json` | Manifest to validate against |

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | No findings |
| `1` | WARN findings only |
| `2` | ERROR findings present |

## JSON Report

Output is a single canonical JSON object (keys sorted, compact):

```json
{
  "computed_manifest_hash": "<64-char hex or null>",
  "expected_manifest_hash": "<64-char hex or null>",
  "findings": [...],
  "manifest_path": "...",
  "mode": "check|write",
  "strict": false,
  "template": {...},
  "tool_path": "...",
  "wrote_stamp": false
}
```

## Finding Codes

See `docs/TOOL_TOML_SPEC.md §7.4` for the base code table. This tool emits all spec codes
plus the tool-level extensions below.

| Code | Level | Description |
|---|---|---|
| `STAMP_MISSING` | WARN | `[template]` section absent from `tool.toml` |
| `STAMP_KEY_MISSING` | WARN | A required key is absent from `[template]` |
| `HASH_INVALID` | ERROR | `template_manifest_hash` does not match `^[0-9a-f]{64}$` |
| `HASH_MISMATCH` | ERROR | Recorded hash does not equal computed hash |
| `STAMP_SOURCE_INVALID` | ERROR | `stamp_source` value not in `{"create","patch","manual"}` |
| `VERSION_MISMATCH` | ERROR | `template_version` differs from manifest's `template_version` field |
| `TOML_MISSING` | ERROR | `tool.toml` not found |
| `MANIFEST_MISSING` | ERROR | `TEMPLATE_MANIFEST.json` cannot be read or parsed |
| `MANIFEST_INVALID` | ERROR | `TEMPLATE_MANIFEST.json` is missing the required `template_version` field |
| `UNHANDLED_EXCEPTION` | ERROR | Unexpected internal error (I/O failure or code bug) |

`MANIFEST_INVALID` and `UNHANDLED_EXCEPTION` are tool-level extension codes not in `docs/TOOL_TOML_SPEC.md §7.4`. They are stable string codes and will not be renamed.

## Responsibility Boundary

| Tool | Responsibility |
|---|---|
| `techvault-tool-template-check` | Detect and report stamp drift (read-only) |
| `techvault-tool-template-version` | Repair or write missing stamps |

## Run Directly

```bash
python tools/tool_template_version/versioner.py <tool_path> --check
python tools/tool_template_version/versioner.py <tool_path> --write
```
