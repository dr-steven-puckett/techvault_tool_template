# Prompt 07 — Final Gate

## Goal
Run the final quality gate for template compliance.

## Inputs
- `docs/TOOL_TEMPLATE_SOT.md`
- Full test suite

## Requirements
- Execute the full test suite.
- Confirm standalone CLI mode works using `--catalog-file`.
- Confirm API and CLI outputs remain contract-aligned.
- Confirm OpenAPI snapshot is stable.
- Confirm determinism checks pass.
- Confirm `response_hash` checks pass when hash is enabled.

## Checkpoint
- `pytest -q` is fully green.
