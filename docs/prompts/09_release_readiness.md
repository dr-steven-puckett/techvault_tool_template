# Prompt 09 — Release Readiness

## Goal
Perform release-readiness checks for a tool generated from this template.

## Inputs
- Tool-specific docs and README
- OpenAPI snapshot
- Test results

## Requirements
- Confirm tool-specific SoT, execution plan, and roadmap files are renamed and populated.
- Confirm `README` includes API and CLI usage examples with `--catalog-file`.
- Confirm determinism guarantees are documented (sorting, pagination, canonical JSON).
- Confirm `response_hash` behavior is documented when enabled.
- Confirm `openapi.snapshot.json` is generated and committed.
- Confirm required tests are present and passing.

## Checkpoint
- Produce a short pass/fail matrix including missing items and blockers.
