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

See `docs/TOOL_TOML_SPEC.md §7.4` for the full finding code table. This tool
additionally emits `LOCAL_MANIFEST_MISSING` (WARN) when the tool repo does not
contain a local `TEMPLATE_MANIFEST.json` audit-record copy.

## Run Directly

```bash
python tools/tool_template_check/checker.py <tool_path>
```
