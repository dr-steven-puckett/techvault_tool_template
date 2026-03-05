TechVault Tool Creation Checklist

A quick deterministic checklist for creating a new TechVault tool.
Follow this in order to ensure the tool integrates cleanly into the
ecosystem.

------------------------------------------------------------------------

0 — Verify Workspace Health

Run from the TechVault repo root:

    pytest

Expected:

    All tests passing

If tests fail, fix the ecosystem first.

------------------------------------------------------------------------

1 — Define Tool Identity

Choose stable identifiers:

  Field            Example
  ---------------- -------------------------------
  Tool directory   tools/library_search
  Tool ID          library_search
  CLI command      techvault-tool-library-search
  Router prefix    /v1/tools/library_search

These values must remain stable once chosen.

------------------------------------------------------------------------

2 — Generate Tool Scaffold

From repo root:

    TOOL_NAME="library_search"

    techvault-tool-create   --name "$TOOL_NAME"   --output-dir "tools/$TOOL_NAME"

This command:

-   copies the template
-   generates tool.toml
-   applies TEMPLATE_MANIFEST.json
-   ensures deterministic structure

------------------------------------------------------------------------

3 — Initialize Standalone Repository

    cd tools/$TOOL_NAME

    git init
    git add -A
    git commit -m "Initial scaffold from tool_template"

Add remote:

    git remote add origin <REMOTE_URL>
    git push -u origin main

------------------------------------------------------------------------

4 — Create Source of Truth Docs

Inside tool repo create:

    docs/SOURCE_OF_TRUTH.md
    docs/EXECUTION_PLAN.md

Ask Copilot:

    Create docs/SOURCE_OF_TRUTH.md using TOOL_TOML_SPEC.md rules.
    Define deterministic outputs, API routes, CLI interface,
    service boundaries, and test requirements.

Then:

    Create docs/EXECUTION_PLAN.md with phased implementation steps.

------------------------------------------------------------------------

5 — Implement the Tool

Recommended structure:

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
5.  pytest tests

------------------------------------------------------------------------

6 — Run Tool Tests

Inside tool repo:

    pytest

All tests must pass before integration.

------------------------------------------------------------------------

7 — Add Tool as Submodule

From TechVault root:

    git submodule add <REMOTE_URL> tools/$TOOL_NAME

    git add .gitmodules tools/$TOOL_NAME
    git commit -m "Add tool submodule: $TOOL_NAME"

------------------------------------------------------------------------

8 — Register the Tool

    techvault-tool-register --tool tools/$TOOL_NAME

Ensures router registration stays deterministic.

------------------------------------------------------------------------

9 — Validate Tool

    techvault-tool-validate --tool tools/$TOOL_NAME

Checks:

-   tool.toml schema
-   directory structure
-   manifest alignment

------------------------------------------------------------------------

10 — Security Scan

    techvault-tool-security-scan --tool tools/$TOOL_NAME

Detects unsafe patterns.

------------------------------------------------------------------------

11 — Update Tool Catalog

    techvault-tool-sync --write-catalog

Verify catalog:

    techvault-tool-validate --check-catalog

Commit changes if catalog updated:

    git add tools/tools.catalog.json
    git commit -m "Update tools catalog"

------------------------------------------------------------------------

12 — Run Fleet Validation

    techvault-tool-fleet   --catalog tools/tools.catalog.json   --steps validate,security_scan

Fleet confirms ecosystem-wide invariants.

------------------------------------------------------------------------

13 — Final Workspace Test

    pytest

Expected:

    All tests passing

------------------------------------------------------------------------

Determinism Rules Reminder

Always ensure:

-   collections are sorted
-   JSON uses canonical serialization
-   outputs contain no timestamps
-   file generation order is stable
-   tests do not depend on environment state

------------------------------------------------------------------------

Done

If all steps pass:

-   the tool is deterministic
-   the tool is registered
-   the catalog is correct
-   the ecosystem remains reproducible
