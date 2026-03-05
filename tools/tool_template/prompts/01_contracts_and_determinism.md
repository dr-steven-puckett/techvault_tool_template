# Prompt 01 — Contracts and Determinism Helpers

## Goal
Define schema contracts and canonical determinism primitives before implementing service logic.

## Inputs
- `docs/TOOL_TEMPLATE_SOT.md`
- `docs/TOOL_TEMPLATE_EXECUTION_PLAN.md`

## Requirements
- Define request and response schemas in `api/schemas.py`.
- Implement canonical JSON helper(s) in `core/determinism.py`.
- Enforce UTF-8 and sorted JSON keys.
- Reject or sanitize NaN/Infinity in output payloads.
- If hash is enabled, add `response_hash = sha256(canonical_json_without_hash)` helper.
- Ensure hash input excludes the `response_hash` field itself.
- Add or complete `tests/test_contract_schemas.py`.
- Add schema-level checks for deterministic response shape.

## Checkpoint
- `pytest tests/test_contract_schemas.py -q` passes.
