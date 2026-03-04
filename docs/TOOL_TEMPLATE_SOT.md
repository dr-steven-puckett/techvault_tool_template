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