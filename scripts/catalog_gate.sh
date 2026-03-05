#!/usr/bin/env bash
# scripts/catalog_gate.sh
#
# CI catalog gate — run from repo root (or any subdirectory):
#
#   bash scripts/catalog_gate.sh          # check-only (fails if catalog is stale)
#   bash scripts/catalog_gate.sh --apply  # regenerate + auto-commit if changed
#
# Exit codes:
#   0  catalog is up to date
#   1  catalog was stale (check-only mode) or check-catalog failed after regen
#   2  script usage / environment error

set -euo pipefail

APPLY=0
for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

# Resolve repo root regardless of working directory.
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PYTHON=".venv/bin/python"
SYNC="tools/tool_sync_manager/techvault-tool-sync"
VALID="tools/tool_template_validator/techvault-tool-validate"

echo "=== catalog-sync ==="
$PYTHON "$SYNC" --write-catalog

if ! git diff --exit-code tools/tools.catalog.json > /dev/null 2>&1; then
    if [[ $APPLY -eq 1 ]]; then
        echo "catalog changed — committing updated tools.catalog.json"
        git add tools/tools.catalog.json
        git commit -m "chore: regenerate tools.catalog.json [ci-auto]"
    else
        echo "ERROR: tools/tools.catalog.json is stale." >&2
        echo "Run 'make catalog-sync' (or 'bash scripts/catalog_gate.sh --apply'), commit the result, and push." >&2
        exit 1
    fi
fi

echo "=== catalog-check ==="
$PYTHON "$VALID" --check-catalog
echo "catalog check passed"
