# Prompt 05 — OpenAPI Snapshot

## Goal
Implement deterministic OpenAPI snapshot generation and drift detection.

## Inputs
- `api/openapi_snapshot.py`
- `openapi.snapshot.json`

## Requirements
- Generate schema snapshot via `api/openapi_snapshot.py`.
- Persist canonical snapshot at repo root as `openapi.snapshot.json`.
- Allow snapshot updates only when `UPDATE_OPENAPI_SNAPSHOT=1` is set.
- Ensure snapshot verification fails on schema drift without update flag.
- Keep OpenAPI generation deterministic.
- Ensure `tests/test_openapi_snapshot.py` supports update and verify modes.

## Checkpoint
- `UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/test_openapi_snapshot.py -q` passes.
- `pytest tests/test_openapi_snapshot.py -q` passes without update flag.
