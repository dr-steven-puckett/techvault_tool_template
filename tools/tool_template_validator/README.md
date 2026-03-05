# techvault-tool-validate

Validates a TechVault tool repository against the template SOT requirements, and optionally checks whether `tools/tools.catalog.json` is up to date.

## Usage

```bash
# Validate a single tool repository
python tools/tool_template_validator/techvault-tool-validate tools/<tool_id>

# Validate and check catalog in the same invocation
python tools/tool_template_validator/techvault-tool-validate tools/<tool_id> --check-catalog

# Check catalog only (no repo validation needed)
python tools/tool_template_validator/techvault-tool-validate --check-catalog
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `repo_path` | — | Path to the tool repository to validate (optional when only `--check-catalog` is used) |
| `--check-catalog` | false | Generate the expected `tools/tools.catalog.json` in-memory and compare it byte-for-byte with the file on disk. Outputs a deterministic JSON result. |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Validation passed (and catalog matches, if `--check-catalog` was given) |
| `1` | Validation failed or catalog mismatch / file missing |
| `2` | Usage / configuration error |

## Catalog check output

When `--check-catalog` is passed, the validator writes a deterministic JSON object to stdout:

```json
{
  "catalog_mismatch": false,
  "catalog_path": "tools/tools.catalog.json",
  "expected_path": "<in-memory>",
  "status": "match"
}
```

On mismatch the `status` field is `"mismatch"` and a `"first_diff_index"` byte offset is included.  
On a missing catalog file the `status` is `"file_missing"`.

The catalog inclusion criterion mirrors `tool_common.catalog.generate_catalog`: any subdirectory of `tools/` that contains a `techvault-tool-*` launcher file is treated as a tool entry.

## Tests

```bash
.venv/bin/python -m pytest tools/tool_template_validator/tests/ -v
```
