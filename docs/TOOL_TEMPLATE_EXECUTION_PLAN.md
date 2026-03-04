# TOOL TEMPLATE — EXECUTION PLAN (Phase 0–4)

Run each phase in order. Do not proceed until the checkpoint passes.

## Phase 0 — Scaffold
- Create repo tree, package skeleton, tool.toml, README, openapi.snapshot.json placeholder, docs/.

Checkpoint 0:
- `python -c "import <tool_package>"` succeeds
- `pytest -q` collects (even if some tests are xfailed initially)

## Phase 1 — Contracts first (schemas + determinism helpers)
- Define Pydantic request/response schemas
- Add canonical JSON dump helper (core/determinism.py)
- Add contract tests for schema validation

Checkpoint 1:
- `pytest tests/test_contract_schemas.py -q` passes

## Phase 2 — Service layer (no API logic)
- Implement service functions with strict exception boundary
- Add ordering + pagination invariants at service layer

Checkpoint 2:
- `pytest tests/test_ordering_pagination.py -q` passes

## Phase 3 — API adapter + OpenAPI snapshot
- Implement FastAPI router, deps, error handlers
- Implement openapi_snapshot generator + snapshot test

Checkpoint 3:
- `UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/test_openapi_snapshot.py -q`
- `pytest tests/test_openapi_snapshot.py -q` (no env var) passes

## Phase 4 — Determinism + full suite
- Add byte-identical JSON determinism tests (API-level and/or service-level)
- Add API smoke tests

Checkpoint 4 (Final Gate):
- `pytest -q` all green