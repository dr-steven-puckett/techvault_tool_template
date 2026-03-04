# TOOL TEMPLATE — EXECUTION PLAN (Phase 0–5)

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

Checkpoint 5 (Final Gate):
- `pytest -q` all green