# Prompt 08 — CLI Interface

## Goal
Implement a standalone CLI adapter in `cli/main.py` that reuses service-layer logic.

## Inputs
- `core/service.py`
- `core/catalog_loader.py`
- `docs/TOOL_TEMPLATE_SOT.md`

## Requirements
- Implement commands: `search` and `health`.
- Accept `--catalog-file` for standalone operation.
- Load catalog via `core/catalog_loader.py`.
- Call service-layer functions only; do not duplicate logic in CLI.
- Emit canonical JSON to stdout.
- Emit errors to stderr only.
- Do not log to stdout.
- If enabled, include `response_hash = sha256(canonical_json_without_hash)`.
- Ensure hash computation excludes the `response_hash` field itself.

## Checkpoint
- `pytest -q` passes schema contract tests.
- `pytest -q` passes ordering invariant tests.
- `pytest -q` passes deterministic JSON tests.
- `pytest -q` passes `response_hash` validation tests when enabled.
- `pytest -q` passes CLI smoke tests.
- `pytest -q` passes API smoke tests.
- `pytest -q` passes OpenAPI snapshot tests.