# Prompt 02 — Catalog Loader

## Goal
Implement deterministic standalone catalog loading in `core/catalog_loader.py`.

## Inputs
- `docs/TOOL_TEMPLATE_SOT.md`
- CLI requirements for `--catalog-file`

## Requirements
- Load catalog JSON from `--catalog-file` path.
- Validate UTF-8 and expected item schema.
- Normalize ordering before service logic runs.
- Minimum normalization is sort by `item_id` ascending.
- Return deterministic `list[CatalogItem]` output.
- Ensure input file item order does not affect downstream results.
- Add loader-focused validation and normalization tests.
- Include malformed JSON and schema error cases.

## Checkpoint
- Loader tests pass for valid, invalid, and shuffled catalog inputs.
