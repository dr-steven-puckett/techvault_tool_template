# Prompt Pack Index

This index maps prompt files to execution phases in `TOOL_TEMPLATE_EXECUTION_PLAN.md`.

## Phase Mapping

- Preflight (run first) — SOT invariant check: `10_sot_invariant_check.md`

- Phase 0 — Scaffold: `00_scaffold_repo.md`
- Phase 1 — Contracts + determinism helpers: `01_contracts_and_determinism.md`
- Phase 2 — Service layer + ordering rules: `02_catalog_loader.md`, `03_service_layer_ordering.md`
- Phase 3 — API adapter + CLI adapter: `04_api_interface.md`, `08_cli_interface.md`
- Phase 4 — OpenAPI snapshot: `05_openapi_snapshot.md`
- Phase 5 — Determinism + CLI tests: `06_determinism_and_hash_tests.md`, `07_final_gate.md`

## Extended Coverage

- Release/readiness checklist: `09_release_readiness.md`

## Notes

- Keep prompt requirements aligned with `TOOL_TEMPLATE_SOT.md`.
- CLI prompts must enforce standalone mode (`--catalog-file`) and deterministic output.
- If `response_hash` is enabled, prompts should require validation using `sha256(canonical_json_without_hash)`.
