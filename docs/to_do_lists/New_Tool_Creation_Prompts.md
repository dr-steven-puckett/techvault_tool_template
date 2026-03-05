TechVault Tool Development Prompts

This document contains standardized Copilot prompts used when developing
new tools in the TechVault deterministic tool ecosystem.

Using the same prompts across all tools ensures:

-   consistent architecture
-   deterministic outputs
-   consistent API contracts
-   reproducible implementations

These prompts assume the tool repository has already been created using:

    techvault-tool-create

and that the following documents already exist:

    docs/SOURCE_OF_TRUTH.md
    docs/EXECUTION_PLAN.md

------------------------------------------------------------------------

Prompt 1 — Generate Schemas

Use this prompt first.

    Create schemas.py for this tool.

    Follow the SOURCE_OF_TRUTH.md exactly.

    Requirements:

    - Use Pydantic models
    - Define request and response schemas
    - Do not invent additional fields
    - Preserve field ordering
    - Include docstrings explaining each model
    - Ensure deterministic serialization
    - Avoid dynamic defaults such as timestamps
    - All models must be explicitly typed

Expected output:

    schemas.py

------------------------------------------------------------------------

Prompt 2 — Generate Service Layer

After schemas are implemented.

    Create service.py implementing the core logic defined in SOURCE_OF_TRUTH.md.

    Requirements:

    - Implement pure deterministic logic
    - No external orchestration frameworks
    - Explicit sorting for all collections
    - No reliance on dictionary iteration order
    - Implement a strict exception boundary
    - Return deterministic JSON-compatible structures
    - No timestamps or random identifiers
    - Add clear docstrings explaining each function

Expected output:

    service.py

------------------------------------------------------------------------

Prompt 3 — Generate API Router

After service layer exists.

    Create router.py exposing the API endpoints defined in SOURCE_OF_TRUTH.md.

    Requirements:

    - Use FastAPI APIRouter
    - Router prefix must match the Source of Truth
    - Operation IDs must be stable
    - Tags must be deterministic
    - Use request and response models from schemas.py
    - Delegate business logic to service.py only
    - Do not implement logic inside the router
    - Ensure endpoint ordering is deterministic

Expected output:

    router.py

------------------------------------------------------------------------

Prompt 4 — Generate CLI Interface

After router implementation.

    Create cli.py implementing a command-line interface for this tool.

    Requirements:

    - Use argparse
    - Commands must be deterministic
    - No timestamps or random output
    - Output JSON must be canonicalizable
    - CLI must call service functions directly
    - Include --help documentation
    - Follow the CLI naming convention defined in the Source of Truth

Expected output:

    cli.py

------------------------------------------------------------------------

Prompt 5 — Generate Test Suite

After core implementation is complete.

    Create pytest tests for this tool.

    Requirements:

    - Cover schemas, service logic, and router endpoints
    - Use deterministic inputs and outputs
    - Explicitly sort any collections in assertions
    - Avoid reliance on environment state
    - Avoid timestamps or random identifiers
    - Use fixtures where appropriate
    - Ensure tests run independently of other tools

Expected output:

    tests/

------------------------------------------------------------------------

Prompt 6 — Determinism Audit

Before integrating the tool into TechVault.

    Audit the entire tool repository for determinism.

    Verify:

    - all collections are explicitly sorted
    - JSON output is canonicalizable
    - no timestamps appear in output structures
    - no reliance on dictionary iteration order
    - no random identifiers
    - tests are deterministic

------------------------------------------------------------------------

Prompt 7 — Integration Check

Before registering the tool.

    Verify that the tool satisfies the following:

    - tool.toml matches TOOL_TOML_SPEC.md
    - API routes match SOURCE_OF_TRUTH.md
    - CLI commands match execution plan
    - pytest suite passes
    - deterministic rules are satisfied

------------------------------------------------------------------------

Prompt 8 — Documentation Generation

Optional final step.

    Generate README.md for this tool.

    Include:

    - tool purpose
    - CLI usage examples
    - API endpoint documentation
    - development instructions
    - testing instructions

------------------------------------------------------------------------

Summary

Typical development order using these prompts:

1.  schemas.py
2.  service.py
3.  router.py
4.  cli.py
5.  pytest tests
6.  determinism audit
7.  integration verification
8.  README generation

Following this prompt sequence ensures all TechVault tools are built
consistently and deterministically.
