PYTHON := .venv/bin/python
SYNC   := tools/tool_sync_manager/techvault-tool-sync
VALID  := tools/tool_template_validator/techvault-tool-validate
FLEET  := tools/tool_fleet_manager/techvault-tool-fleet

.PHONY: catalog-sync catalog-check catalog-ci fleet-ci test ci

## Regenerate tools/tools.catalog.json from the current workspace.
## Run after adding or removing a tool; commit the result.
catalog-sync:
	$(PYTHON) $(SYNC) --write-catalog

## Assert that tools/tools.catalog.json is up to date.
## Exits non-zero if the on-disk catalog does not match the generated one.
catalog-check:
	$(PYTHON) $(VALID) --check-catalog

## Regenerate catalog then verify it matches (CI-hard gate).
## If the catalog changed, re-run catalog-sync and commit the file.
catalog-ci: catalog-sync catalog-check

## Run fleet steps validate + security-scan + template-check across all tools.
fleet-ci:
	$(PYTHON) $(FLEET) \
	  --catalog tools/tools.catalog.json \
	  --steps validate,security_scan,template-check

## Run the full test suite.
test:
	$(PYTHON) -m pytest -q

## Full CI pass: catalog gate + fleet checks + test suite.
ci: catalog-ci fleet-ci test
