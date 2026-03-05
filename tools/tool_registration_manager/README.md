# techvault-tool-register

Deterministic, idempotent CLI that registers a TechVault tool into the API router.

## Target file

```
backend/techvault/app/api/__init__.py
```

The registrar inserts and maintains two auto-managed blocks:

| Block | Purpose | Insertion point |
|-------|---------|-----------------|
| `TECHVAULT TOOL ROUTER IMPORTS` | `from <tool_id>.api.router import router as <tool_id>_router` | After existing imports |
| `TECHVAULT TOOL ROUTER MOUNTS` | `api_router.include_router(...)` calls | Before `__all__` |

All entries are sorted lexicographically by `tool_id`. Running the tool a second time with identical inputs makes no change.

## Usage

```bash
# Dry-run (default) — show what would change
python tools/tool_registration_manager/techvault-tool-register \
  tools/<tool_id> \
  --techvault-root /path/to/TechVault

# Register all tool repos found under a directory
python tools/tool_registration_manager/techvault-tool-register \
  --all tools/ \
  --techvault-root /path/to/TechVault

# Write changes
python tools/tool_registration_manager/techvault-tool-register \
  tools/<tool_id> \
  --techvault-root /path/to/TechVault \
  --apply
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `TOOL_REPO` | — | Path to tool repository (positional) |
| `--all TOOLS_DIR` | — | Scan directory for all tool repos (mutually exclusive with positional) |
| `--techvault-root PATH` | required | Root of the TechVault project |
| `--apply` | false | Write changes; dry-run if omitted |
| `--allow-mismatch` | false | Allow `tool_id` to differ from folder name |
| `--verbose` | false | Show full unified diff in dry-run output |
| `--api-init PATH` | auto | Override path to `api/__init__.py` |

## tool.toml requirements

```toml
tool_id   = "my_tool"          # required; must match folder name
entrypoint = "my_tool.api.router:router"  # required; must contain ":"
```

## Block markers (contractual)

```
# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
from sample_tool.api.router import router as sample_tool_router
# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)

# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
api_router.include_router(
    sample_tool_router,
    tags=["tools:sample_tool"]
)
# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (dry-run complete, or changes applied) |
| `1` | Validation / configuration error |
| `2` | Apply failure (compile error — changes reverted) |

## Constraints

- Modifies **only** content inside the auto-generated blocks.
- Does **not** touch `create_app`, `main.py`, or any existing routers outside the blocks.
- No external dependencies — Python stdlib only (`tomllib`, `difflib`, `py_compile`).
- Atomic writes via `tempfile.mkstemp` → `py_compile` verify → `shutil.move`.

## Tests

```bash
.venv/bin/python -m pytest tools/tool_registration_manager/tests/ -v
```

37 tests across 7 classes: dry-run, apply, idempotency, sorting, validation errors, block markers, `--all`, single-tool preservation.
