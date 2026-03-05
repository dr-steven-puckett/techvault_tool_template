TechVault Deterministic Tool Creation Runbook

This document explains how to create a new TechVault tool using the
deterministic tool generation ecosystem.

It is written as a step‑by‑step operational procedure for developers
working inside the TechVault workspace.

------------------------------------------------------------------------

Overview

Each tool in the ecosystem:

-   lives in its own repository
-   resides under tools/<tool_name> in the TechVault workspace
-   is added to TechVault via git submodule
-   must obey deterministic build rules

Determinism rules:

-   explicit sorting everywhere
-   identical inputs produce byte‑identical outputs
-   JSON must use canonical serialization
-   stable pagination
-   no timestamps unless explicitly required
-   no reliance on dict/set iteration order

Tool lifecycle tools:

  Tool                           Purpose
  ------------------------------ ----------------------------------
  techvault-tool-create          generate new tool from template
  techvault-tool-validate        validate tool.toml and structure
  techvault-tool-security-scan   scan for unsafe patterns
  techvault-tool-register        register tool router
  techvault-tool-sync            ecosystem synchronization
  techvault-tool-fleet           run checks across all tools

------------------------------------------------------------------------

Step 0 — Verify the workspace is healthy

From the TechVault repository root run:

    pytest

Expected result:

    259 tests passing
    0 failures

This confirms:

-   test collection is working
-   template ecosystem tools are valid
-   catalog validation is operational

If this fails, fix the ecosystem before creating new tools.

------------------------------------------------------------------------

Step 1 — Choose the new tool identity

Decide the following values:

Tool directory name

    tools/<tool_name>

Example

    tools/library_search

Tool ID (used in tool.toml and catalog)

    library_search

CLI command name

    techvault-tool-library-search

Router prefix

    /v1/tools/library_search

Once these identifiers are chosen they should not change.

------------------------------------------------------------------------

Step 2 — Generate the new tool from the template

Use the deterministic creator tool.

From repository root:

    TOOL_NAME="library_search"

    techvault-tool-create   --name "$TOOL_NAME"   --output-dir "tools/$TOOL_NAME"

This command:

-   copies files from tool_template
-   generates a valid tool.toml
-   stamps files from TEMPLATE_MANIFEST.json
-   ensures deterministic file ordering

Do not manually copy files from the template unless debugging the
creator tool.

------------------------------------------------------------------------

Step 3 — Initialize the standalone repository

Each tool is a standalone Git repository.

    cd tools/$TOOL_NAME

    git init
    git add -A
    git commit -m "Initial scaffold from tool_template"

Create a remote repository and connect it:

    git remote add origin <REMOTE_URL>
    git push -u origin main

------------------------------------------------------------------------

Step 4 — Create the tool Source of Truth documents

Inside the tool repo create:

    docs/

Required documents:

    docs/SOURCE_OF_TRUTH.md
    docs/EXECUTION_PLAN.md

Ask Copilot to generate the SoT

Example Copilot prompt:

    Create docs/SOURCE_OF_TRUTH.md for this tool.

    Follow TOOL_TOML_SPEC.md and TEMPLATE_MANIFEST.json rules.
    Define:

    - scope and responsibilities
    - deterministic output rules
    - CLI interface
    - API router prefix
    - service layer exception boundaries
    - test requirements

Then generate the execution plan.

Copilot prompt:

    Create docs/EXECUTION_PLAN.md with deterministic checkpoints:

    Phase 0 – schema scaffolding
    Phase 1 – service implementation
    Phase 2 – router endpoints
    Phase 3 – CLI integration
    Phase 4 – pytest suite
    Phase 5 – TechVault registration

------------------------------------------------------------------------

Step 5 — Implement the tool

Typical deterministic layout:

    schemas.py
    service.py
    router.py
    cli.py
    tests/

Implementation order:

1.  schemas
2.  service logic
3.  router endpoints
4.  CLI entrypoint
5.  tests

Example Copilot prompt:

    Implement schemas.py exactly matching the SOURCE_OF_TRUTH.
    Do not add extra fields.
    Ensure deterministic serialization.

Next prompt:

    Implement service.py with a strict exception boundary.
    Return deterministic structures only.

------------------------------------------------------------------------

Step 6 — Run tool tests locally

Inside the tool repository:

    pytest

The suite must pass before integration.

------------------------------------------------------------------------

Step 7 — Add the tool to TechVault via submodule

Return to the TechVault root.

    git submodule add <REMOTE_URL> tools/$TOOL_NAME

    git add .gitmodules tools/$TOOL_NAME
    git commit -m "Add tool submodule: $TOOL_NAME"

------------------------------------------------------------------------

Step 8 — Register the tool

Register the router with TechVault.

    techvault-tool-register --tool tools/$TOOL_NAME

This updates the router registrar deterministically.

------------------------------------------------------------------------

Step 9 — Validate and security scan

    techvault-tool-validate --tool tools/$TOOL_NAME

    techvault-tool-security-scan --tool tools/$TOOL_NAME

These commands enforce:

-   tool.toml compliance
-   structure validation
-   security checks

------------------------------------------------------------------------

Step 10 — Update the deterministic catalog

Write the canonical catalog:

    techvault-tool-sync --write-catalog

Verify the catalog:

    techvault-tool-validate --check-catalog

If the catalog changes:

    git add tools/tools.catalog.json
    git commit -m "Update tool catalog"

------------------------------------------------------------------------

Step 11 — Run the fleet checks

Execute ecosystem checks across all tools.

    techvault-tool-fleet   --catalog tools/tools.catalog.json   --steps validate,security_scan

The fleet runner produces a canonical JSON report.

------------------------------------------------------------------------

Step 12 — Final verification

Run the full workspace test suite again.

    pytest

Expected result:

    All tests passing

------------------------------------------------------------------------

Common Mistakes

Editing the template directly
Template changes should be validated using template-check tools.

Manually editing the catalog
Always regenerate using --write-catalog.

Using unordered structures
Always explicitly sort collections.

Using timestamps
Never include timestamps unless required by schema.

------------------------------------------------------------------------

Summary

To create a new tool:

1.  Verify workspace tests
2.  Generate tool with techvault-tool-create
3.  Initialize standalone repo
4.  Write Source-of-Truth docs
5.  Implement code
6.  Run tests
7.  Add submodule
8.  Register tool
9.  Validate and security scan
10. Regenerate catalog
11. Run fleet checks

Following this process guarantees:

-   deterministic outputs
-   reproducible tool builds
-   stable ecosystem integration
