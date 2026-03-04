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
- No LLM usage. No orchestration frameworks. No background jobs.

### 0.1 Canonical JSON rules
- UTF-8
- `sort_keys=true`
- No NaN/Infinity
- Stable float formatting (avoid floats when possible; prefer ints/strings)
- All output objects must have stable key ordering (enforced via canonical dump)

---

## 1) Purpose and Scope

### 1.1 Purpose
Describe what this tool does in 1–2 sentences.

### 1.2 In scope
Bullets.

### 1.3 Out of scope / non-goals
Bullets (explicitly excludes synthesis, LLM calls, async workers).

---

## 2) Repository Layout (Tool Repo Standard)

Minimum structure:

./
  tool.toml
  README.md
  openapi.snapshot.json
  docs/
    TOOL_<NAME>_SOT.md
    TOOL_<NAME>_EXECUTION_PLAN.md
    TOOL_<NAME>_ROADMAP.md   # optional
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
      security.py   # optional (only if tool enforces auth)
    db/             # only if tool persists data
      __init__.py
      models.py
      migrations/
        env.py
        versions/
  tests/
    __init__.py
    test_contract_schemas.py
    test_determinism_json.py
    test_ordering_pagination.py
    test_openapi_snapshot.py
    test_api_smoke.py

Notes:
- No dynamic discovery; TechVault mounts router explicitly.
- Package-relative imports only.

---

## 3) Host Integration Contract (TechVault)

- TechVault imports router explicitly; no plugin discovery.
- Host provides request context (`ctx`) and db session dependency overrides where applicable.
- Tool must remain runnable standalone for tests by using tool-local deps (overrideable).

---

## 4) Security Contract (if applicable)

### 4.1 Context fields
Define the minimal ctx contract (user_id, group_ids, security_level, etc.) if the tool enforces access control.

### 4.2 Enforcement rules
- Centralized enforcement only: `core/security.py`
- Fail-closed on missing/unknown values.

---

## 5) Service Exception Boundary (Strict)

**Only these exceptions may escape service functions:**
- `ValueError` (invalid input, not found, determinism violations)
- `PermissionError` (authz failure)

All unexpected exceptions MUST be wrapped deterministically as `ValueError("Unexpected error: <ClassName>: <stable_message>")`.

---

## 6) Data Contracts

### 6.1 Primary entities
Define entity models (even if no DB): e.g., `CatalogItem`, `SearchResult`, etc.

### 6.2 Sorting and pagination (MUST be explicit)
Define:
- Default sort keys
- Tie-breaker key
- Pagination model (`limit`, `offset` OR cursor—prefer limit/offset for simplicity)
- Stability guarantees

---

## 7) API Contract (FastAPI)

### 7.1 Router
- Prefix: `/v1/tools/<tool_id>`
- Tags: `["tools:<tool_id>"]`

### 7.2 Endpoints
List endpoints with request/response schemas.

### 7.3 Error mapping
- `PermissionError` → HTTP 403
- `ValueError` containing “not found” → HTTP 404
- other `ValueError` → HTTP 400

---

## 8) Determinism Tests (Required)

- Byte-identical JSON for same request repeated N times.
- Ordering/pagination stability for:
  - equal-score ties
  - same title, different id
  - case-folding collisions
- “No hidden nondeterminism” test: randomize input iteration order and assert output unchanged.

---

## 9) OpenAPI Snapshot (Tool-local)

- Repo root contains `openapi.snapshot.json`.
- Test compares generated schema to snapshot.
- Regeneration requires explicit env var `UPDATE_OPENAPI_SNAPSHOT=1`.

---

## 10) Done Definition (Acceptance Criteria)

- All tests pass: `pytest -q`
- OpenAPI snapshot stable (no drift)
- Determinism tests pass (byte-identical JSON)
- Service exception boundary enforced
- Pagination/order invariants verified