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
