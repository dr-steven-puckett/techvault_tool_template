# TOOL TEMPLATE — EXECUTION PLAN (Phase 0–6)

Run each phase in order. Do not proceed until the checkpoint passes.

## Phase 0 — Scaffold
- Create repo tree, package skeleton, tool.toml, README, openapi.snapshot.json placeholder, docs/.
- Include `cli/` package and `core/catalog_loader.py`.
- Create `docs/prompts/README.md`.

Checkpoint 0:
- `python -c "import <tool_package>"` succeeds
- `pytest -q` collects (even if some tests are xfailed initially)

## Phase 1 — Contracts first (schemas + determinism helpers)
- Define Pydantic request/response schemas
- Add canonical JSON dump helper (core/determinism.py)
- If `response_hash_enabled=true` for this tool, add deterministic hash helper for `response_hash` (`sha256(canonical_json_without_hash)`)
- Add contract tests for schema validation

Checkpoint 1:
- `pytest tests/test_contract_schemas.py -q` passes

## Phase 2 — Service layer (no API logic)
- Implement service functions with strict exception boundary
- Implement deterministic catalog loader + normalization (`core/catalog_loader.py`)
- Add ordering + pagination invariants at service layer
- Validate input-order independence (shuffle test)

Checkpoint 2:
- `pytest tests/test_ordering_pagination.py -q` passes

## Phase 3 — API adapter + CLI adapter
- Implement FastAPI router, deps, error handlers
- Implement CLI commands (`search`, `health`) backed by service layer
- Add standalone catalog mode support: `--catalog-file`

Checkpoint 3:
- `python -m <tool_package>.cli health` returns valid JSON
- `python -m <tool_package>.cli search --query "x" --catalog-file <path>` returns valid JSON

## Phase 4 — OpenAPI snapshot
- Implement openapi_snapshot generator + snapshot test

Checkpoint 4:
- `UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/test_openapi_snapshot.py -q`
- `pytest tests/test_openapi_snapshot.py -q` (no env var) passes

## Phase 5 — Determinism + CLI tests + full suite
- Add byte-identical JSON determinism tests (service/API/CLI)
- Add CLI smoke test (`tests/test_cli_smoke.py`) with `subprocess.run()` and `returncode == 0`
- Assert repeated CLI stdout is byte-identical
- Assert standalone mode works with `--catalog-file`
- If `response_hash_enabled=true`, add `response_hash` tests: recompute from canonical payload without hash and assert equality
- Add API smoke tests

Checkpoint 5:
- `pytest -q` all green

## Phase 6 — Tooling Gates (Compliance, Security + Registration)

Run the companion validators and register the tool. Do not ship until all gates pass.

### 6.1 Template Compliance Validator
```bash
python tools/tool_template_validator/techvault-tool-validate <repo_path>
```
Must exit 0. Validates:
- Repository structure (files, dirs, subpackages)
- Prompt pack integrity
- Determinism enforcement module + test present
- CLI `--catalog-file` requirement
- Service exception boundary (`ValueError`/`PermissionError`)
- Required test files present
- `openapi.snapshot.json` present

### 6.2 Security Harness
```bash
python tools/tool_security_harness/techvault-tool-security-scan <repo_path>
```
Must exit 0 (no FAIL-severity findings). Checks:
1. Static policy — no forbidden imports or calls (`pickle`, `socket`, `requests`, `httpx`, `eval`, `exec`, `os.system`, `subprocess(shell=True)`, `yaml.load`)
2. Path safety — `catalog_loader.py` rejects absolute paths, traversal, and non-UTF-8 inputs
3. CLI error leaks — no Python tracebacks in stderr; stdout is JSON-only
4. API surface sanity — routes under `/v1/tools/<tool_id>`, correct tags

WARN-only findings (e.g., DEBUG logging, missing fastapi) do not fail the gate.

### 6.3 Registration Manager
```bash
# Dry-run to verify what will be written
python tools/tool_registration_manager/techvault-tool-register <repo_path> --techvault-root <root>

# Apply once block content is confirmed correct
python tools/tool_registration_manager/techvault-tool-register <repo_path> --techvault-root <root> --apply
```
Must exit 0. Idempotent; safe to re-run on every release. Writes auto-managed `# BEGIN`/`# END` blocks into `backend/techvault/app/api/__init__.py`:
- Router import line: `from <tool_id>.api.router import router as <tool_id>_router` (after existing imports)
- `api_router.include_router(<tool_id>_router, tags=["tools:<tool_id>"])` call (before `__all__`)

Checkpoint 6 (Final Gate) — run individually or via the sync orchestrator:

```bash
# Preferred: run all gates in one command (dry-run)
python tools/tool_sync_manager/techvault-tool-sync <repo_path> --techvault-root <root>

# Apply registration once dry-run output is confirmed
python tools/tool_sync_manager/techvault-tool-sync <repo_path> --techvault-root <root> --apply
```

Or run each gate individually:
- `python tools/tool_template_validator/techvault-tool-validate <repo_path>` exits 0
- `python tools/tool_security_harness/techvault-tool-security-scan <repo_path>` exits 0
- `python tools/tool_registration_manager/techvault-tool-register <repo_path> --techvault-root <root> --apply` exits 0