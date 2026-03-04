# Prompt 06 — Determinism and Hash Tests

## Goal
Implement strict determinism tests across service, API, and CLI surfaces.

## Inputs
- `core/determinism.py`
- `tests/test_determinism_json.py`
- `tests/test_cli_smoke.py`

## Requirements
- Repeat identical requests N times and assert byte-identical canonical JSON output.
- Shuffle catalog input and assert identical output.
- Verify pagination stability across adjacent pages.
- If enabled, validate `response_hash` by recomputing `sha256(canonical_json_without_hash)`.
- Use byte-level comparisons rather than semantic-only comparisons.
- Ensure determinism coverage exists for service and/or API in `tests/test_determinism_json.py`.
- Ensure CLI deterministic stdout assertions exist in `tests/test_cli_smoke.py`.

## Checkpoint
- Determinism and optional hash tests pass in local test suite.
