# tool_fleet_manager

Fleet runner for the TechVault deterministic tool ecosystem.

Executes stamp-checking steps across all tools listed in `tools/tools.catalog.json` and returns an aggregated canonical JSON report.

---

## Purpose

When the workspace grows to 200+ tools, running `techvault-tool-template-check` or `techvault-tool-template-version --check` per-tool by hand is impractical. `techvault-tool-fleet` reads the catalog, iterates every tool (in deterministic id order), dispatches the requested steps, and aggregates results into a single JSON report.

---

## CLI Usage

```bash
# Check all tools against the workspace canonical manifest (default step: template-check)
techvault-tool-fleet

# Run both stamp steps across all catalog tools
techvault-tool-fleet --steps template-check,template-version-check

# Specify a custom catalog or manifest
techvault-tool-fleet --catalog path/to/tools.catalog.json \
                     --manifest path/to/TEMPLATE_MANIFEST.json

# Strict mode: exit 2 on any finding (WARN or ERROR)
techvault-tool-fleet --strict --steps template-check
```

**Exit codes**

| Code | Meaning |
|------|---------|
| `0` | All steps OK across all tools |
| `1` | At least one WARN, no errors |
| `2` | At least one ERROR, catalog failure, or step dispatch error |

---

## Catalog Schema

The catalog file (`tools/tools.catalog.json`) is the single authority for fleet enumeration. The fleet runner **never scans directories by default**.

```json
{
  "version": 1,
  "tools": [
    { "id": "<tool_id>", "path": "tools/<repo_dir_name>" }
  ]
}
```

**Rules enforced at load time:**

| Rule | Error code |
|------|------------|
| `version` must equal `1` | `CATALOG_VERSION_UNKNOWN` |
| `tools` must be a JSON array | `CATALOG_INVALID` |
| Each entry must have exactly `"id"` and `"path"` keys | `CATALOG_INVALID` |
| `"path"` must start with `"tools/"` | `CATALOG_INVALID` |
| No duplicate `"id"` values | `CATALOG_DUPLICATE_ID` |
| `tools` list must be sorted ascending by `"id"` | `CATALOG_UNSORTED` |

---

## Supported Steps (v1)

| Step name | Delegates to |
|-----------|-------------|
| `template-check` | `tool_template_check/checker.py run_check()` |
| `template-version-check` | `tool_template_version/versioner.py run_check()` |

---

## Report Structure

```json
{
  "catalog_path": "<string>",
  "manifest_path": "<string>",
  "steps": ["template-check"],
  "strict": false,
  "results": [
    {
      "tool_id": "...",
      "tool_path": "...",
      "step": "...",
      "exit_code": 0,
      "report": { ... },
      "error": null
    }
  ],
  "summary": {
    "total_tools": 8,
    "total_steps": 1,
    "ok": 2,
    "warn": 3,
    "error": 3
  }
}
```

`results` is sorted by `(tool_id, step)` ascending.
On catalog failure, a top-level `"catalog_error"` key is added and `results` is empty.

---

## Determinism Guarantees

- Tools processed in catalog order (sorted by `id`; validated at load).
- Steps dispatched in sorted order within each tool.
- `results` explicitly re-sorted by `(tool_id, step)` before output.
- Report serialized via `canonical_json`: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"`.
- No timestamps, random seeds, or unordered collection iteration in the fleet runner itself.
- Identical inputs always produce byte-identical JSON output.

---

## Importable API

```python
from fleet import run_fleet, read_catalog, canonical_json, CatalogError

catalog = read_catalog("tools/tools.catalog.json")

report, exit_code = run_fleet(
    catalog_path="tools/tools.catalog.json",
    manifest_path=None,          # None → workspace canonical default
    strict=False,
    steps=["template-check", "template-version-check"],
)

print(canonical_json(report))
```
