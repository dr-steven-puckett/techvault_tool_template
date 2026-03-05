# TechVault Library Tool Template (V2)

This file is the reusable entrypoint for all TechVault library tool repos.

## Required Documents

- `TOOL_<NAME>_SOT.md` — normative source of truth for behavior and contracts.
- `TOOL_<NAME>_EXECUTION_PLAN.md` — phased build sequence and checkpoints.
- `TOOL_<NAME>_ROADMAP.md` — non-binding future ideas only.

For this template repository, the canonical references are:

- `TOOL_TEMPLATE_SOT.md`
- `TOOL_TEMPLATE_EXECUTION_PLAN.md`
- `TOOL_TEMPLATE_ROADMAP.md`
- `STANDARD_REPO_SKELETON.md`
- `tools/tool_template/TEMPLATE_MANIFEST.json` — **canonical machine-readable inventory** of all required files, directories, prompt entries, and policy defaults. This is the authoritative source used by foundation tooling (validator, sync orchestrator) to check template compliance.

## Architecture Contract (Mandatory)

Every tool implements three interfaces over shared logic:

- Service layer (`core/service.py`) as canonical deterministic logic
- FastAPI adapter (`api/router.py`)
- CLI adapter (`cli/main.py`)

API and CLI must call the same service functions.

## Standalone CLI Requirement

All tools must run outside TechVault using:

- `--catalog-file <path/to/catalog.json>`

CLI output must be deterministic canonical JSON on stdout only; errors go to stderr.

When enabled, responses should include `response_hash = sha256(canonical_json_without_hash)` for determinism verification, cache keys, and auditability.

Template default: `response_hash_enabled = false` unless a tool SOT explicitly enables it.

## Determinism Requirement

Tools must enforce:

- stable sorting with explicit tie-breakers
- stable pagination
- byte-identical JSON for identical inputs
- input-order independence (shuffle-safe)
- optional deterministic response hash validation

## Test Minimums

Required tests include:

- contract/schema validation
- ordering/pagination stability
- JSON determinism
- CLI smoke + deterministic stdout checks
- OpenAPI snapshot stability
- API smoke

## Usage

Start from this document, then copy and specialize the `TOOL_TEMPLATE_*` docs into tool-specific docs named `TOOL_<NAME>_*`.
