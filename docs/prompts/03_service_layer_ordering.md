# Prompt 03 — Service Layer Ordering and Pagination

## Goal
Implement canonical deterministic service functions in `core/service.py`.

## Inputs
- `docs/TOOL_TEMPLATE_SOT.md`
- `core/catalog_loader.py`

## Requirements
- Keep all business logic in service layer.
- Apply explicit sorting and stable tie-breakers.
- Implement stable pagination with `limit` and `offset`.
- Enforce strict exception boundary with only `ValueError` and `PermissionError` escaping.
- Wrap unexpected exceptions as deterministic `ValueError` messages.
- Keep API and CLI specific logic out of service functions.
- Ensure `tests/test_ordering_pagination.py` covers tie collisions and page stability.
- Add shuffle/input-order-independence assertions.

## Checkpoint
- `pytest tests/test_ordering_pagination.py -q` passes.
