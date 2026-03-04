# Prompt 00 — Scaffold Repository

## Goal
Scaffold a deterministic TechVault tool repository that matches the template baseline.

## Inputs
- `docs/STANDARD_REPO_SKELETON.md`
- `docs/TOOL_TEMPLATE_SOT.md`

## Requirements
- Create the required root files: `tool.toml`, `README.md`, `openapi.snapshot.json` (placeholder).
- Create required package folders: `api/`, `core/`, `cli/` under the tool package.
- Create `docs/prompts/README.md` explaining that the directory contains Copilot execution prompts mapped to phases of `TOOL_TEMPLATE_EXECUTION_PLAN.md`.
- Ensure the prompts directory structure matches the template skeleton.
- Create required docs and tests placeholders per the standard skeleton.
- Match `STANDARD_REPO_SKELETON.md` exactly unless explicitly instructed otherwise.
- Use package-relative imports only.
- Do not add plugin discovery.
- Keep implementation minimal and deterministic-first.

## Checkpoint
- `python -c "import <tool_package>"` succeeds.
- `pytest -q` collects tests.
