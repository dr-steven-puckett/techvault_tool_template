# Prompt 10 — SOT Invariant Check

## Goal

Validate that the Source-of-Truth (SOT), execution plan, repository skeleton, and prompt pack are internally consistent before beginning tool implementation.

This step prevents Copilot from generating code that violates the SOT or introduces nondeterministic behavior.

## Inputs

- `docs/TOOL_TEMPLATE_SOT.md`
- `docs/TOOL_TEMPLATE_EXECUTION_PLAN.md`
- `docs/STANDARD_REPO_SKELETON.md`
- `docs/prompts/README.md`
- All prompt files in `docs/prompts/`

## Verification Requirements

Perform the following checks:

### 1 — Phase Mapping Consistency

Verify that prompts referenced in `docs/prompts/README.md` map correctly to the phases defined in `TOOL_TEMPLATE_EXECUTION_PLAN.md`.

Confirm:

- Phase 0 → `00_scaffold_repo.md`
- Phase 1 → `01_contracts_and_determinism.md`
- Phase 2 → `02_catalog_loader.md`, `03_service_layer_ordering.md`
- Phase 3 → `04_api_interface.md`, `08_cli_interface.md`
- Phase 4 → `05_openapi_snapshot.md`
- Phase 5 → `06_determinism_and_hash_tests.md`, `07_final_gate.md`
- Extended coverage → `09_release_readiness.md`
- Invariant check → `10_sot_invariant_check.md`

Report any mismatch.

### 2 — Repository Skeleton Alignment

Verify that:

`STANDARD_REPO_SKELETON.md` matches the repository structure described in `TOOL_TEMPLATE_SOT.md`.

Confirm presence of:

- `tool.toml`
- `README.md`
- `openapi.snapshot.json`

`docs/`

- `TOOL_<NAME>_SOT.md`
- `TOOL_<NAME>_EXECUTION_PLAN.md`
- `TOOL_<NAME>_ROADMAP.md`
- `prompts/`

`docs/prompts/`

- `README.md`
- all numbered prompt files

tool package directories:

- `api/`
- `core/`
- `cli/`

tests:

- contract tests
- determinism tests
- CLI tests
- OpenAPI snapshot tests

Report missing or conflicting paths.

### 3 — Determinism Rules Alignment

Verify that all prompts and SOT definitions consistently enforce:

- explicit sorting
- stable pagination
- canonical JSON serialization
- byte-identical deterministic outputs
- independence from input ordering

Check that no prompt introduces:

- nondeterministic iteration
- random ordering
- background jobs
- asynchronous workers
- external LLM calls

Report violations.

### 4 — CLI Behavior Consistency

Verify that all CLI references enforce canonical invocation:

`python -m <tool_package>.cli <command>`

Confirm that:

- CLI uses service-layer logic only
- CLI emits JSON to stdout only
- CLI errors go to stderr
- CLI supports `--catalog-file`

Report inconsistencies.

### 5 — Exception Boundary

Verify prompts enforce the service-layer exception boundary:

Only these exceptions may escape:

- `ValueError`
- `PermissionError`

Unexpected exceptions must be wrapped as deterministic `ValueError`.

Report violations.

### 6 — response_hash Behavior

Verify that documentation and prompts treat `response_hash` consistently:

- Optional feature
- Enabled only when tool configuration allows
- Computed as `sha256(canonical_json_without_hash)`

Ensure prompts do not require hash tests unless enabled.

Report inconsistencies.

## Output

Produce a short report with:

PASS / FAIL for each invariant category.

Example format:

- Phase Mapping: PASS
- Repository Skeleton Alignment: PASS
- Determinism Rules: PASS
- CLI Behavior: PASS
- Exception Boundary: PASS
- Response Hash Behavior: PASS

If any invariant fails, list:

- the conflicting files
- the section where the conflict occurs
- recommended correction

## Constraint

This prompt must NEVER generate code.

It only analyzes documentation and prompts to ensure template integrity before tool generation begins.
