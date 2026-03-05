# techvault-tool-sync

Deterministic orchestrator that runs the standard TechVault tool lifecycle for a single tool or all tools in a directory.

## Steps (in fixed order)

| # | Step | Delegates to |
|---|------|-------------|
| 1 | **validate** | `techvault-tool-validate` |
| 2 | **tests** | `pytest -q` (in tool repo directory) |
| 3 | **security** | `techvault-tool-security-scan` |
| 4 | **register** | `techvault-tool-register` (dry-run unless `--apply`) |

## Usage

```bash
# Sync a single tool (dry-run registration)
python tools/tool_sync_manager/techvault-tool-sync \
  tools/<tool_id> \
  --techvault-root /path/to/TechVault

# Sync all tool repos under a directory
python tools/tool_sync_manager/techvault-tool-sync \
  --all tools/ \
  --techvault-root /path/to/TechVault

# Apply registration changes
python tools/tool_sync_manager/techvault-tool-sync \
  tools/<tool_id> \
  --techvault-root /path/to/TechVault \
  --apply

# Write a JSON report
python tools/tool_sync_manager/techvault-tool-sync \
  --all tools/ \
  --techvault-root /path/to/TechVault \
  --json-report /tmp/sync_report.json

# (Re)generate tools.catalog.json standalone
python tools/tool_sync_manager/techvault-tool-sync --write-catalog

# Sync all tools and update the catalog in one shot
python tools/tool_sync_manager/techvault-tool-sync \
  --all tools/ \
  --techvault-root /path/to/TechVault \
  --write-catalog
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `TOOL_REPO` | — | Path to a single tool repository (mutually exclusive with `--all`) |
| `--all TOOLS_DIR` | — | Scan TOOLS_DIR for tool repos (sorted lexicographically) |
| `--techvault-root PATH` | required | Root of the TechVault project |
| `--tools-dir PATH` | — | Where tool repos live (recorded in JSON report; optional) |
| `--apply` | false | Pass `--apply` to `techvault-tool-register`; default is dry-run |
| `--enabled true\|false` | — | Forwarded to `techvault-tool-register` |
| `--skip-validate` | false | Skip template compliance check |
| `--skip-tests` | false | Skip pytest run |
| `--skip-security` | false | Skip security scan |
| `--skip-register` | false | Skip registration step |
| `--fail-fast` | false | Stop processing a tool after its first failed step |
| `--json-report PATH` | — | Write deterministic JSON report to this file |
| `--write-catalog` | false | Regenerate `tools/tools.catalog.json` from the current workspace. Can be used standalone (no `TOOL_REPO` / `--all` needed) or combined with a sync run. Atomic write via `.tmp` rename. |
| `--verbose` | false | Print captured stdout/stderr for each step |

## Dry-run vs --apply

The registration step calls `techvault-tool-register`, which is **dry-run by default** (shows what would change without writing). Pass `--apply` to `techvault-tool-sync` to write the registration changes.

All other steps (validate, tests, security) are always read-only.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All steps passed (or skipped) for all tools |
| `1` | One or more tools failed a step |
| `2` | Usage / configuration error (missing paths, bad arguments) |

## JSON report format

```json
{
  "apply": false,
  "techvault_root": "/path/to/TechVault",
  "tools_dir": null,
  "catalog_write": {"catalog_path": "tools/tools.catalog.json", "status": "ok", "tools_count": 8},
  "tools": [
    {
      "path": "tools/my_tool",
      "steps": {
        "validate":  {"exit_code": 0, "mode": null,      "status": "pass", "stderr": "", "stdout": "..."},
        "tests":     {"exit_code": 0, "mode": null,      "status": "pass", "stderr": "", "stdout": "..."},
        "security":  {"exit_code": 0, "mode": null,      "status": "pass", "stderr": "", "stdout": "..."},
        "register":  {"exit_code": 0, "mode": "dry-run", "status": "pass", "stderr": "", "stdout": "..."}
      },
      "tool_id": "my_tool"
    }
  ]
}
```

Rules:
- `tools` array is sorted by `tool_id`
- Step keys always in order: `validate`, `tests`, `security`, `register`
- File written with `json.dumps(..., sort_keys=True, indent=2)` (fully canonical)
- `stdout`/`stderr` truncated to 20 000 chars (first N chars kept)

## Required sibling tools

This tool delegates to — but does **not** import — these foundation tools:

| Script | Repository |
|--------|-----------|
| `tools/tool_template_validator/techvault-tool-validate` | `tool_template_validator/` |
| `tools/tool_security_harness/techvault-tool-security-scan` | `tool_security_harness/` |
| `tools/tool_registration_manager/techvault-tool-register` | `tool_registration_manager/` |

They are called via `subprocess` using `sys.executable <script_path>`. No internal module imports.

## Tests

```bash
.venv/bin/python -m pytest tools/tool_sync_manager/tests/ -v
```

Tests monkeypatch `sync._run_subprocess` to simulate pass/fail responses from sibling tools without requiring them to be present or functional.
