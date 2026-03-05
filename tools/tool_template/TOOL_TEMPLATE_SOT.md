# TechVault Library Tool — TEMPLATE Source of Truth

**Tool ID:** `tool_id_here`
**Type:** Standalone deterministic tool repository (no agents, no synthesis)
**Integration:** added to TechVault via git submodule (or git subprocess) and registered as a callable tool.
**This document is the single source of truth.** Implementations MUST match this spec.

---

## 0) Determinism Contract (Non-Negotiable)

This tool MUST be deterministic:

- Explicit sorting for all collections.
- Stable pagination with stable tie-breakers.
- No reliance on dict/set iteration order.
- Identical inputs → byte-identical JSON outputs (canonical JSON serialization rules).
- Input order independence: shuffled equivalent inputs MUST yield identical outputs.
- No LLM usage. No orchestration frameworks. No background jobs.

### 0.1 Canonical JSON rules
- UTF-8
- `sort_keys=true`
- No NaN/Infinity
- Stable float formatting (avoid floats when possible; prefer ints/strings)
- All output objects must have stable key ordering (enforced via canonical dump)
- CLI output is JSON-only to stdout; errors are emitted to stderr only.

### 0.2 Deterministic hash check (recommended standard)
- `response_hash` is OPTIONAL and controlled by a tool-level setting `response_hash_enabled` (template default: `false`).
- If `response_hash_enabled=true`, API + CLI responses MUST include `response_hash` computed as `sha256(canonical_json_without_hash)`.
- Hash input excludes the `response_hash` field itself.
- If `response_hash_enabled=false`, `response_hash` MUST NOT be emitted.

---

## 1) Core Architecture (Mandatory)

Every TechVault tool MUST implement three interfaces over one canonical logic layer:

- **Service Layer (`core/service.py`)**: canonical deterministic logic.
- **FastAPI Router (`api/router.py`)**: integration adapter.
- **CLI Interface (`cli/main.py`)**: standalone execution and debugging adapter.

Rules:
- No duplicated logic across API and CLI.
- API and CLI MUST call the same service functions.
- Identical logical inputs MUST produce byte-identical JSON outputs.

---

## 2) Purpose and Scope

### 2.1 Purpose
Describe what this tool does in 1–2 sentences.

### 2.2 In scope
Bullets.

### 2.3 Out of scope / non-goals
Bullets (explicitly excludes synthesis, LLM calls, async workers).

---

## 3) Repository Layout (Tool Repo Standard)

Minimum structure:

./
  tool.toml
  README.md
  openapi.snapshot.json
  docs/
    TOOL_<NAME>_SOT.md
    TOOL_<NAME>_EXECUTION_PLAN.md
    TOOL_<NAME>_ROADMAP.md
    TOOL_TEMPLATE.md
    prompts/
      README.md
  <tool_package>/
    __init__.py
    api/
      __init__.py
      router.py
      schemas.py
      deps.py
      openapi_snapshot.py
    core/
      __init__.py
      service.py
      determinism.py
      catalog_loader.py
      security.py   # optional (only if tool enforces auth)
    cli/
      __init__.py
      main.py
  tests/
    test_contract_schemas.py
    test_determinism_json.py
    test_ordering_pagination.py
    test_cli_smoke.py
    test_openapi_snapshot.py
    test_api_smoke.py

Notes:
- No dynamic discovery; TechVault mounts router explicitly.
- Package-relative imports only.

---

## 4) Host Integration Contract (TechVault)

- TechVault imports router explicitly; no plugin discovery.
- Host provides request context (`ctx`) and db session dependency overrides where applicable.
- Tool must remain runnable standalone for tests by using tool-local deps (overrideable).

---

## 5) Standalone Catalog Mode (Mandatory)

CLI MUST support standalone invocation with catalog input:

- `--catalog-file <path_to_catalog.json>`

Example:
- `python -m <tool_package>.cli search --query "python agents" --catalog-file catalog.json`
- Canonical invocation form is `python -m <tool_package>.cli <command> ...`.

### 5.1 Catalog JSON format
- UTF-8 JSON array of catalog items.
- Each item must include deterministic identity and retrieval fields (for example `item_id`, `title`, `authors`, `year`, `file_ref`, `tags`).
- Service behavior MUST be independent of input item order.

### 5.2 Loader and normalization requirements
- `core/catalog_loader.py` loads and validates catalog JSON.
- Catalog items are normalized to a deterministic order before search logic runs.
- Minimum normalization: sort by `item_id` ascending.

---

## 6) Security Contract (if applicable)

### 6.1 Context fields
Define the minimal ctx contract (user_id, group_ids, security_level, etc.) if the tool enforces access control.

### 6.2 Enforcement rules
- Centralized enforcement only: `core/security.py`
- Fail-closed on missing/unknown values.

---

## 7) Service Exception Boundary (Strict)

**Only these exceptions may escape service functions:**
- `ValueError` (invalid input, not found, determinism violations)
- `PermissionError` (authz failure)

All unexpected exceptions MUST be wrapped deterministically as `ValueError("Unexpected error: <ClassName>: <stable_message>")`.

---

## 8) Data Contracts

### 8.1 Primary entities
Define entity models (even if no DB): e.g., `CatalogItem`, `SearchResult`, etc.

### 8.2 Sorting and pagination (MUST be explicit)
Define:
- Default sort keys
- Tie-breaker key
- Pagination model (`limit`, `offset` OR cursor—prefer limit/offset for simplicity)
- Stability guarantees

### 8.3 CLI output contract
- Command output is canonical JSON to stdout only.
- Output shape must match corresponding API response semantics.
- Errors are deterministic and emitted to stderr only.
- If `response_hash` is emitted, it MUST match canonical response payload bytes excluding the hash field.
- Canonical CLI invocation form is `python -m <tool_package>.cli <command> ...`.

---

## 9) API Contract (FastAPI)

### 9.1 Router
- Prefix: `/v1/tools/<tool_id>`
- Tags: `["tools:<tool_id>"]`

### 9.2 Endpoints
List endpoints with request/response schemas.

### 9.3 Error mapping
- `PermissionError` → HTTP 403
- `ValueError` containing “not found” → HTTP 404
- other `ValueError` → HTTP 400

---

## 10) Determinism Tests (Required)

- Byte-identical JSON for same request repeated N times.
- Ordering/pagination stability for:
  - equal-score ties
  - same title, different id
  - case-folding collisions
- “No hidden nondeterminism” test: randomize input iteration order and assert output unchanged.
- Catalog shuffle test: shuffled catalog input produces identical results.
- CLI determinism test: repeated CLI invocation with same args yields identical stdout bytes.
- Response hash test (ONLY when `response_hash_enabled=true`): recompute `sha256(canonical_json_without_hash)` and assert equality with emitted `response_hash`.

---

## 11) OpenAPI Snapshot (Tool-local)

- Repo root contains `openapi.snapshot.json`.
- Test compares generated schema to snapshot.
- Regeneration requires explicit env var `UPDATE_OPENAPI_SNAPSHOT=1`.

---

## 12) Done Definition (Acceptance Criteria)

- All tests pass: `pytest -q`
- OpenAPI snapshot stable (no drift)
- Determinism tests pass (byte-identical JSON)
- CLI smoke + standalone mode tests pass (`--catalog-file` path)
- If hash is enabled, `response_hash` validation tests pass
- Service exception boundary enforced
- Pagination/order invariants verified
- `techvault-tool-validate <repo_path>` exits 0 (all compliance checks pass)
- `techvault-tool-security-scan <repo_path>` exits 0 (no FAIL-severity security findings)

---

## 13) Companion Tooling Gates (Required)

Two standalone CLI utilities MUST be run against every generated tool repository before it is considered complete. Both live in `tools/` inside this template workspace.

### 13.1 Template Compliance Validator — `techvault-tool-validate`

Location: `tools/tool_template_validator/`

Verifies the structural and contractual completeness of a generated tool repo:
- Repository structure (required files, dirs, subpackages)
- Prompt pack integrity (`docs/prompts/` completeness)
- Determinism enforcement (`core/determinism.py` + `tests/test_determinism_json.py`)
- CLI requirements (`cli/main.py` with `--catalog-file`)
- Service layer contract (`ValueError`/`PermissionError` boundaries)
- Test coverage (all required test files present)
- OpenAPI snapshot presence

**Usage:**
```bash
python tools/tool_template_validator/techvault-tool-validate <repo_path>
# Exit 0 = compliant; Exit 1 = non-compliant
```

### 13.2 Security Harness — `techvault-tool-security-scan`

Location: `tools/tool_security_harness/`

Deterministically scans a generated tool repository for cybersecurity hazards and policy violations. Offline; no network access; no fuzzing; does NOT modify the scanned repository.

**Checks performed (in fixed output order):**

1. **Static Policy Checks** — AST scan of all `.py` files under the tool package:
   - FAIL: `subprocess.*(shell=True)`, `eval()`, `exec()`, `import pickle`, `yaml.load()` (any), `import requests`/`httpx`, `import socket`, `os.system()`
   - WARN: `logging` configured at `DEBUG` level by default

2. **Path Safety Checks** — if `core/catalog_loader.py` exists:
   - Must reject absolute paths, path traversal (`..`), and non-UTF-8 input with `ValueError`
   - Falls back to minimal dynamic test if patterns cannot be confirmed statically

3. **CLI Error Leak Checks** — if `cli/main.py` exists:
   - `health` invocation: stdout must be valid JSON; stderr must not contain a Python traceback
   - No-args invocation: stderr must not contain a Python traceback

4. **API Surface Sanity** — if `api/router.py` exists (requires `fastapi`):
   - All routes must be under `/v1/tools/<tool_id>`
   - Router tags must include `tools:<tool_id>`
   - No unexpected extra endpoints

**Usage:**
```bash
python tools/tool_security_harness/techvault-tool-security-scan <repo_path>
# Exit 0 = PASS; Exit 1 = FAIL (findings); Exit 2 = ERROR (scan failed)
```

**Output format:** Deterministic `PASS`/`FAIL` per section, findings sorted by `(file_path, line, severity, message)`, concluding with `RESULT: PASS` or `RESULT: FAIL`.

---

### 13.3 Registration Manager — `techvault-tool-register`

Location: `tools/tool_registration_manager/`

Idempotent, deterministic CLI that registers a generated tool repository into the TechVault API router. Writes two auto-managed blocks into `backend/techvault/app/api/__init__.py`. Dry-run by default; `--apply` required to write.

**Target file (first existing candidate):**
- `backend/techvault/app/api/__init__.py`
- `techvault/app/api/__init__.py`
- `app/api/__init__.py`

**Key contracts:**

- Import block inserted after existing `from`/`import` lines in `api/__init__.py`.
- Mount block inserted before `__all__ = ["api_router"]`.
- All entries sorted lexicographically by `tool_id`.
- Single-tool mode preserves other tools already registered in the blocks.
- `--all` mode replaces both blocks with exactly the discovered set of tools.
- Atomic writes: `tempfile.mkstemp` → `py_compile` verify → `shutil.move`.
- Exit 0 = success / dry-run complete; Exit 1 = validation error; Exit 2 = apply/compile failure.

**Block markers (contractual):**
```
# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
```

**Rendered example (`sample_tool`):**
```python
# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
from sample_tool.api.router import router as sample_tool_router
# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)

# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
api_router.include_router(
    sample_tool_router,
    tags=["tools:sample_tool"]
)
# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
```

**Usage:**
```bash
# Register a single tool (dry-run)
python tools/tool_registration_manager/techvault-tool-register <tool_repo_path> --techvault-root <root>

# Register all tools found under a directory
python tools/tool_registration_manager/techvault-tool-register --all <tools_dir> --techvault-root <root>

# Write changes
python tools/tool_registration_manager/techvault-tool-register <tool_repo_path> --techvault-root <root> --apply
# Exit 0 = applied; Exit 1 = validation error; Exit 2 = compile failure
```

---

### 13.4 Sync Orchestrator — `techvault-tool-sync`

Location: `tools/tool_sync_manager/`

Deterministic lifecycle orchestrator for foundation tooling. Runs all four gates in fixed order for a single tool or a scanned directory of tools. Does **not** modify tool repo contents.

**Steps (fixed order):**
1. `validate` — delegates to `techvault-tool-validate`
2. `tests` — runs `pytest -q` in the tool repo working directory
3. `security` — delegates to `techvault-tool-security-scan`
4. `register` — delegates to `techvault-tool-register` (dry-run unless `--apply`)

**Key contracts:**

- Tools processed in lexicographic order by directory name.
- Each step captured (stdout + stderr); non-zero exit = fail.
- Any step failure propagates to overall exit 1; processing continues unless `--fail-fast`.
- `--apply` only affects the register step; all other steps are read-only.
- Optional `--json-report PATH` writes a canonical JSON report (`sort_keys=True`); `tools[]` sorted by `tool_id`; stdout/stderr truncated to 20 000 chars.
- Exit 0 = all steps passed/skipped; Exit 1 = one or more tools failed; Exit 2 = usage/config error.

**Usage:**
```bash
# Single tool, dry-run registration
python tools/tool_sync_manager/techvault-tool-sync <tool_repo> --techvault-root <root>

# All tools, apply registration
python tools/tool_sync_manager/techvault-tool-sync --all <tools_dir> --techvault-root <root> --apply

# Skip individual steps
python tools/tool_sync_manager/techvault-tool-sync <tool_repo> --techvault-root <root> \
  --skip-validate --skip-tests

# Full run with JSON report
python tools/tool_sync_manager/techvault-tool-sync <tool_repo> --techvault-root <root> \
  --json-report /tmp/report.json
# Exit 0 = pass; Exit 1 = fail; Exit 2 = config error
```