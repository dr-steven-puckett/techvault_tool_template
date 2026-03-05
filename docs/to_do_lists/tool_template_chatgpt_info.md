# TechVault Tool Template — Complete Context for ChatGPT

**Repository:** `dr-steven-puckett/techvault_tool_template` (branch: `main`)
**Local path:** `/home/spuckett1/projects/tools/tv_tool_template`
**Template version:** `2.0.0`
**Last updated:** March 5, 2026

---

## 1. Purpose of This Repository

This repo is the **master template and foundation tooling workspace** for all TechVault library tools. It contains:

1. **The template standard** — normative docs (SOT, execution plan, roadmap, skeleton, TEMPLATE_MANIFEST) that every generated tool repo must comply with.
2. **Foundation CLI tools** — standalone Python utilities (`tools/`) that validate, secure, register, and orchestrate generated tool repos.
3. **A prompt pack** — 11 ordered Copilot prompt files that drive phased construction of a new tool through Copilot.
4. **A generator** — scaffolding CLI (`techvault-tool-create`) that clones the template into a new named tool repo.

This repo is **not** a TechVault tool itself — it governs how tools are built, validated, and deployed.

---

## 2. Repository Layout

```
tv_tool_template/
├── docs/
│   ├── TOOL_TEMPLATE.md                  # Entrypoint doc for all tool repos
│   ├── TOOL_TEMPLATE_SOT.md              # Normative source of truth
│   ├── TOOL_TEMPLATE_EXECUTION_PLAN.md   # Phased build sequence (Phase 0–6)
│   ├── TOOL_TEMPLATE_ROADMAP.md          # Completed + future work
│   ├── STANDARD_REPO_SKELETON.md         # Required directory/file tree
│   └── prompts/                          # Copilot prompt pack (11 files + README)
│       ├── README.md                     # Phase-to-prompt mapping index
│       ├── 00_scaffold_repo.md
│       ├── 01_contracts_and_determinism.md
│       ├── 02_catalog_loader.md
│       ├── 03_service_layer_ordering.md
│       ├── 04_api_interface.md
│       ├── 05_openapi_snapshot.md
│       ├── 06_determinism_and_hash_tests.md
│       ├── 07_final_gate.md
│       ├── 08_cli_interface.md
│       ├── 09_release_readiness.md
│       └── 10_sot_invariant_check.md     # Preflight — run before any phase
├── tools/
│   ├── tool_template/                    # Mirror of docs/ (canonical template copy)
│   │   ├── TEMPLATE_MANIFEST.json        # Machine-readable inventory of requirements
│   │   ├── TOOL_TEMPLATE_SOT.md
│   │   ├── TOOL_TEMPLATE_EXECUTION_PLAN.md
│   │   ├── TOOL_TEMPLATE_ROADMAP.md
│   │   ├── STANDARD_REPO_SKELETON.md
│   │   └── prompts/                      # Mirror of docs/prompts/
│   ├── tool_template_generator/
│   │   ├── generator.py
│   │   └── techvault-tool-create         # Launcher (chmod +x, runpy)
│   ├── tool_template_validator/
│   │   ├── validator.py
│   │   └── techvault-tool-validate       # Launcher
│   ├── tool_security_harness/
│   │   ├── scanner.py
│   │   ├── techvault-tool-security-scan  # Launcher
│   │   └── tests/
│   ├── tool_registration_manager/
│   │   ├── registrar.py
│   │   ├── techvault-tool-register       # Launcher
│   │   └── tests/
│   └── tool_sync_manager/
│       ├── sync.py
│       ├── techvault-tool-sync           # Launcher (orchestrator)
│       └── tests/
```

---

## 3. Core Architecture Contract

Every TechVault tool repo must implement **three interfaces over one shared logic layer**:

```
core/service.py        ← canonical deterministic logic (no FastAPI, no CLI)
    ↑                         ↑
api/router.py          cli/main.py
(FastAPI adapter)      (CLI adapter)
```

**Rules:**
- API and CLI both call the same service functions — zero logic duplication.
- Service layer is the only layer with business logic.
- `core/catalog_loader.py` loads and normalizes catalog input.
- `core/determinism.py` provides canonical JSON serialization helpers.
- No agents, no LLM calls, no async workers, no orchestration frameworks.

---

## 4. Determinism Contract (Non-Negotiable)

All tools are **pure deterministic functions**:

- Explicit `sort()` on all collections with stable tie-breakers.
- Stable pagination (limit/offset, not cursor).
- No reliance on dict/set iteration order.
- Identical inputs → byte-identical JSON outputs.
- Input-order independence: shuffled equivalent inputs produce identical outputs.
- **Canonical JSON rules:** UTF-8, `sort_keys=True`, no NaN/Infinity.

### Optional: `response_hash`
- Controlled by per-tool setting `response_hash_enabled` (template default: `false`).
- When enabled: `response_hash = sha256(canonical_json_without_hash)`.
- When disabled: field must NOT be emitted.

---

## 5. Service Exception Boundary (Strict)

Only two exception types may escape service functions:

| Exception | Meaning |
|---|---|
| `ValueError` | Invalid input, not found, determinism violation |
| `PermissionError` | Authorization failure |

All unexpected exceptions must be wrapped: `ValueError("Unexpected error: <ClassName>: <stable_message>")`.

**HTTP mapping:**
- `PermissionError` → 403
- `ValueError` containing "not found" → 404
- Other `ValueError` → 400

---

## 6. Standard Tool Repository Structure

Every generated tool repo must match this skeleton:

```
<repo_root>/
├── tool.toml
├── README.md
├── openapi.snapshot.json
├── docs/
│   ├── TOOL_<NAME>_SOT.md
│   ├── TOOL_<NAME>_EXECUTION_PLAN.md
│   ├── TOOL_<NAME>_ROADMAP.md
│   ├── TOOL_TEMPLATE.md
│   └── prompts/
│       └── README.md
├── <tool_package>/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── deps.py
│   │   └── openapi_snapshot.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   ├── determinism.py
│   │   └── catalog_loader.py
│   └── cli/
│       ├── __init__.py
│       └── main.py
└── tests/
    ├── test_contract_schemas.py
    ├── test_ordering_pagination.py
    ├── test_determinism_json.py
    ├── test_cli_smoke.py
    ├── test_openapi_snapshot.py
    └── test_api_smoke.py
```

**Key conventions:**
- API prefix: `/v1/tools/<tool_id>`
- Router tags: `["tools:<tool_id>"]`
- Canonical CLI invocation: `python -m <tool_package>.cli <command>`
- Standalone mode required: `--catalog-file <path>` on all search commands

---

## 7. TEMPLATE_MANIFEST.json

Machine-readable inventory of requirements. Located at `tools/tool_template/TEMPLATE_MANIFEST.json`. Used by foundation tooling (validator, sync orchestrator) to check compliance.

```json
{
  "policies": {
    "cli_invocation": "python -m <tool_id>.cli <command>",
    "response_hash_enabled_default": false
  },
  "required_dirs": [
    "docs", "docs/prompts", "tests",
    "<tool_id>/api", "<tool_id>/cli", "<tool_id>/core"
  ],
  "required_docs": [
    "TOOL_*_EXECUTION_PLAN.md",
    "TOOL_*_ROADMAP.md",
    "TOOL_*_SOT.md"
  ],
  "required_prompts": [
    "docs/prompts/00_scaffold_repo.md",
    "docs/prompts/01_contracts_and_determinism.md",
    "docs/prompts/02_catalog_loader.md",
    "docs/prompts/03_service_layer_ordering.md",
    "docs/prompts/04_api_interface.md",
    "docs/prompts/05_openapi_snapshot.md",
    "docs/prompts/06_determinism_and_hash_tests.md",
    "docs/prompts/07_final_gate.md",
    "docs/prompts/08_cli_interface.md",
    "docs/prompts/09_release_readiness.md",
    "docs/prompts/10_sot_invariant_check.md",
    "docs/prompts/README.md"
  ],
  "required_root_files": ["README.md", "openapi.snapshot.json", "tool.toml"],
  "template_version": "2.0.0"
}
```

---

## 8. Phased Build Process (Execution Plan)

Tools are built phase-by-phase with a checkpoint at each phase before proceeding.

| Phase | Description | Copilot Prompt | Checkpoint |
|---|---|---|---|
| Preflight | SOT invariant check | `10_sot_invariant_check.md` | SOT matches implementation |
| 0 | Scaffold repo, skeleton, docs | `00_scaffold_repo.md` | `import <tool>` succeeds; pytest collects |
| 1 | Contracts — schemas + determinism helpers | `01_contracts_and_determinism.md` | `test_contract_schemas.py` passes |
| 2 | Service layer — catalog loader, ordering, pagination | `02_catalog_loader.md` + `03_service_layer_ordering.md` | `test_ordering_pagination.py` passes |
| 3 | API adapter + CLI adapter | `04_api_interface.md` + `08_cli_interface.md` | `cli health` returns JSON; standalone search works |
| 4 | OpenAPI snapshot | `05_openapi_snapshot.md` | Snapshot stable; `test_openapi_snapshot.py` passes |
| 5 | Determinism tests + CLI smoke + hash tests | `06_determinism_and_hash_tests.md` + `07_final_gate.md` | All `pytest -q` green |
| 6 | Tooling gates: validate → security → register | `09_release_readiness.md` | All three gates exit 0 |

### Phase 6 — Tooling Gates (Detail)

**Preferred: run all gates at once via sync orchestrator:**
```bash
# Dry-run (no writes)
python tools/tool_sync_manager/techvault-tool-sync <repo_path> --techvault-root <root>

# Apply registration when confirmed
python tools/tool_sync_manager/techvault-tool-sync <repo_path> --techvault-root <root> --apply
```

**Or run individually:**
```bash
python tools/tool_template_validator/techvault-tool-validate <repo_path>          # exit 0
python tools/tool_security_harness/techvault-tool-security-scan <repo_path>       # exit 0
python tools/tool_registration_manager/techvault-tool-register <repo_path> \
    --techvault-root <root> --apply                                               # exit 0
```

---

## 9. Foundation Tools Inventory

All five foundation tools live in `tools/` and are complete. Each follows the same pattern:
- Single `.py` implementation file
- `runpy`-based launcher (`techvault-<name>`, chmod +x)
- `tests/` directory with monkeypatched subprocess isolation

### 9.1 `techvault-tool-create` — Template Generator

**Location:** `tools/tool_template_generator/`

Scaffolds a new tool repository from the template, substituting `tool_id` throughout all files, docs, and prompt packs.

```bash
python tools/tool_template_generator/techvault-tool-create <tool_id> <output_dir>
```

### 9.2 `techvault-tool-validate` — Compliance Validator

**Location:** `tools/tool_template_validator/`
**Tests:** present
**Exit codes:** 0 = compliant, 1 = non-compliant

Validates a generated tool repo against `TEMPLATE_MANIFEST.json` and `TOOL_TEMPLATE_SOT.md`:
- Required files, dirs, subpackages
- Prompt pack completeness (all 11 prompt files + README)
- `core/determinism.py` present + `test_determinism_json.py` present
- `cli/main.py` has `--catalog-file` support
- Service exception boundary (`ValueError`/`PermissionError` only)
- All 6 required test files present
- `openapi.snapshot.json` present

```bash
python tools/tool_template_validator/techvault-tool-validate <repo_path>
```

### 9.3 `techvault-tool-security-scan` — Security Harness

**Location:** `tools/tool_security_harness/`
**Tests:** 28 tests (good_tool + bad_tool fixture repos)
**Exit codes:** 0 = PASS, 1 = FAIL (findings), 2 = ERROR (scan failed)

Deterministic, **offline** AST security scanner. Four check sections in fixed output order:

1. **Static Policy (AST scan)** — FAIL on: `subprocess(shell=True)`, `eval`, `exec`, `import pickle`, `yaml.load`, `import requests`/`httpx`, `import socket`, `os.system`; WARN on DEBUG logging
2. **Path Safety** — `catalog_loader.py` must reject absolute paths, path traversal (`..`), non-UTF-8 input
3. **CLI Error Leaks** — no Python tracebacks in stderr on `health` or no-args invocation; stdout must be valid JSON
4. **API Surface Sanity** — all routes under `/v1/tools/<tool_id>`; correct tags

Output format: deterministic `PASS`/`FAIL` per section; findings sorted by `(file_path, line, severity, message)`; concludes with `RESULT: PASS` or `RESULT: FAIL`.

```bash
python tools/tool_security_harness/techvault-tool-security-scan <repo_path>
```

### 9.4 `techvault-tool-register` — Registration Manager

**Location:** `tools/tool_registration_manager/`
**Tests:** 37 tests
**Exit codes:** 0 = success/dry-run, 1 = validation error, 2 = apply/compile failure

Idempotent CLI that writes two auto-managed blocks into `backend/techvault/app/api/__init__.py`. Dry-run by default; `--apply` required to write. Atomic writes: `tempfile.mkstemp` → `py_compile` verify → `shutil.move`.

**Target file** (first existing candidate):
- `backend/techvault/app/api/__init__.py`
- `techvault/app/api/__init__.py`
- `app/api/__init__.py`

**Block markers (contractual — do not change):**
```python
# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
from sample_tool.api.router import router as sample_tool_router
# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)

# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
api_router.include_router(sample_tool_router, tags=["tools:sample_tool"])
# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
```

**Key behaviors:**
- Import block inserted after existing `from`/`import` lines
- Mount block inserted before `__all__ = ["api_router"]`
- All entries sorted lexicographically by `tool_id`
- Single-tool mode preserves other already-registered tools
- `--all` mode replaces both blocks with the full scanned set

```bash
# Single tool dry-run
python tools/tool_registration_manager/techvault-tool-register <tool_repo> --techvault-root <root>

# Register all tools in a directory
python tools/tool_registration_manager/techvault-tool-register --all <tools_dir> --techvault-root <root>

# Apply
python tools/tool_registration_manager/techvault-tool-register <tool_repo> --techvault-root <root> --apply
```

### 9.5 `techvault-tool-sync` — Sync Orchestrator

**Location:** `tools/tool_sync_manager/`
**Tests:** 47 tests
**Exit codes:** 0 = all pass/skip, 1 = any fail, 2 = usage/config error

Runs all four gates in **fixed order**: validate → tests (`pytest -q`) → security → register. Single tool or entire `tools/` directory. This is the **preferred Phase 6 command**.

**Key behaviors:**
- Tools processed lexicographically by directory name
- Each step captures stdout + stderr; non-zero exit = fail
- Failures propagate to exit 1; processing continues unless `--fail-fast`
- `--apply` only affects the register step; all other steps are read-only
- `--json-report PATH` writes canonical JSON report (`sort_keys=True`); tools sorted by `tool_id`; stdout/stderr truncated to 20,000 chars

**Flags:**
```bash
--apply                 # Write registration (dry-run without this)
--skip-validate         # Skip validate gate
--skip-tests            # Skip pytest gate
--skip-security         # Skip security scan gate
--skip-register         # Skip registration gate
--fail-fast             # Abort tool on first step failure
--json-report PATH      # Write JSON report to PATH
--all <tools_dir>       # Scan directory for tool repos (contain tool.toml)
```

```bash
# Full run, dry-run registration
python tools/tool_sync_manager/techvault-tool-sync <tool_repo> --techvault-root <root>

# All tools, apply registration, with report
python tools/tool_sync_manager/techvault-tool-sync --all <tools_dir> \
    --techvault-root <root> --apply --json-report /tmp/report.json
```

---

## 10. Prompt Pack (Copilot Construction Workflow)

Each prompt file drives one phase of tool construction, submitted to Copilot in order.

| File | Phase | Purpose |
|---|---|---|
| `10_sot_invariant_check.md` | Preflight | Verify SOT and implementation are aligned before any work |
| `00_scaffold_repo.md` | Phase 0 | Generate repo skeleton, all required files/dirs |
| `01_contracts_and_determinism.md` | Phase 1 | Pydantic schemas + canonical JSON helper + hash helper |
| `02_catalog_loader.md` | Phase 2a | `catalog_loader.py` with normalization, validation, path safety |
| `03_service_layer_ordering.md` | Phase 2b | Service functions, ordering, pagination invariants, shuffle safety |
| `04_api_interface.md` | Phase 3a | FastAPI router, deps, error mapping |
| `08_cli_interface.md` | Phase 3b | CLI commands, `--catalog-file`, deterministic stdout |
| `05_openapi_snapshot.md` | Phase 4 | OpenAPI snapshot generator + snapshot test |
| `06_determinism_and_hash_tests.md` | Phase 5a | Byte-identical JSON tests, shuffle tests, hash validation |
| `07_final_gate.md` | Phase 5b | CLI smoke tests, API smoke, full suite green |
| `09_release_readiness.md` | Phase 6 | Tooling gates, registration, release checklist |

**Usage pattern:** Paste the prompt file (with tool-specific substitutions) into Copilot Chat before starting each phase.

---

## 11. Host Integration — TechVault Backend

Tools are registered into the TechVault FastAPI backend via the registration manager. The target file is:

```
backend/techvault/app/api/__init__.py
```

Template of the target file (minimal):
```python
from fastapi import APIRouter

api_router = APIRouter()

# BEGIN TECHVAULT TOOL ROUTER IMPORTS (auto-generated)
# END TECHVAULT TOOL ROUTER IMPORTS (auto-generated)

# BEGIN TECHVAULT TOOL ROUTER MOUNTS (auto-generated)
# END TECHVAULT TOOL ROUTER MOUNTS (auto-generated)

__all__ = ["api_router"]
```

**Important rules:**
- TechVault imports routers explicitly — no plugin discovery.
- Tool must remain runnable standalone for tests (tool-local deps).
- Host provides request context via dependency injection overrides.

---

## 12. Reference Tool: `library_catalog_search`

The first concrete tool built from this template. Not in this repo — lives in its own repo. Demonstrates full Phase 0–6 compliance:

- Full service → API → CLI stack
- Standalone `--catalog-file` mode
- All 6 required test file categories
- OpenAPI snapshot
- Passed all three tooling gates (validate / security / register)

Used as the proof-of-concept and example for the template standard.

---

## 13. Current Status

### Completed ✓

| Item | Notes |
|---|---|
| `TEMPLATE_MANIFEST.json` | `tools/tool_template/TEMPLATE_MANIFEST.json` — canonical machine-readable inventory |
| `techvault-tool-create` | Scaffolding generator |
| `techvault-tool-validate` | Compliance validator |
| `techvault-tool-security-scan` | Offline AST security scanner, 28 tests |
| `techvault-tool-register` | Idempotent router-block registrar, 37 tests |
| `techvault-tool-sync` | Lifecycle orchestrator (all four gates), 47 tests |
| `library_catalog_search` | Reference tool (in separate repo) |
| Docs/SOT mirrored to `tools/tool_template/` | Template mirror kept in sync |
| `.gitignore` | Standard Python excludes |
| Phase 0–6 execution plan | Complete with gate commands |

### Planned / Future (non-binding)

| Item | Notes |
|---|---|
| **CI hook** | `techvault-tool-sync --all <tools_dir> --techvault-root <root> --json-report ci_report.json` on every PR — config task only, tooling is complete |
| **Security: dependency audit** | Static scan of `requirements.txt`/`pyproject.toml` for vulnerable packages (offline, pinned advisory list) |
| **Security: secrets detection** | Flag hardcoded API keys/tokens (regex, no network) |
| **Validator: snapshot drift diff** | Surface diff when OpenAPI snapshot is stale instead of just noting presence |
| **Domain-specific bulk endpoints** | With deterministic ordering guarantees |
| **Optional caching layer** | Cache keyed on canonical input hash |
| **Benchmark suite** | Large-catalog CLI performance runs |

---

## 14. Backlog / Action Items (`tool_template_to_do_list.md`)

These are the next automation tools proposed for this workspace, in recommended build order:

### Priority Queue

| # | Tool Name | Purpose |
|---|---|---|
| 1 | `techvault-tool-template-check` | Detect drift from template standard in an existing tool repo (structure, prompt pack, tool.toml schema, SOT docs) |
| 2 | `techvault-tool-template-patch` | Auto-update existing tool repos when template changes — add new prompt files, update SOT sections, add missing dirs |
| 3 | `techvault-tool-prompts-check` | Verify every tool repo has the complete prompt pack (all 11 files), flag missing or modified prompts |
| 4 | `techvault-tool-prompts-update` | Push template prompt updates into existing tool repos (`--all tools/`) |
| 5 | `techvault-tool-schema-gen` | Auto-generate `schemas.py`, `router.py`, `service.py` stubs from `tool.toml` — drastically speeds up Phase 0–1 |
| 6 | `techvault-tool-determinism-check` | Standalone determinism verification: stable JSON ordering, deterministic pagination, repeat-run identity |
| 7 | `techvault-tool-docs-build` | Auto-generate `TechVault/docs/TOOLS.md` catalog table (tool, actions, endpoint) from all registered tools |
| 8 | `techvault-tool-integration-test` | Spin up temporary FastAPI env, load router, verify endpoints respond, OpenAPI valid |
| 9 | `techvault-tool-benchmark` | Measure avg latency, memory usage, catalog-size scaling — critical for search/text tools |
| 10 | `techvault-tool-template-version` | Track which template version each tool uses; upgrade command `techvault-tool-template-upgrade` |

### Notes on Priority Reasoning
- **Items 1–2** are the most urgent: as tools proliferate, drift goes silent without a detector+patcher.
- **Items 3–4** are closely related to 1–2 and could be merged into a single `template-check` + `template-patch` system.
- **Item 5** (`schema-gen`) has the highest ROI for new tool construction — eliminates manual boilerplate for Phases 0–1.
- **Items 6–7** are quality/observability tools with moderate priority.
- **Items 8–9** are integration/performance tools — lower priority until more tools exist.
- **Item 10** (version manager) becomes critical when template versioning diverges across tools.

---

## 15. Key Technical Conventions

### Naming
- Tool IDs: `snake_case` (e.g., `library_catalog_search`)
- Launcher scripts: `techvault-tool-<name>` (kebab-case, no `.py` extension, chmod +x)
- Python package: same as tool ID (e.g., `library_catalog_search/`)
- Docs: `TOOL_<NAME>_SOT.md` where `<NAME>` is uppercase with underscores

### Implementation Pattern (Foundation Tools)
```python
# launcher (techvault-tool-<name>)
#!/usr/bin/env python3
import runpy, sys, pathlib
sys.argv[0] = str(pathlib.Path(__file__).resolve())
runpy.run_path(str(pathlib.Path(__file__).parent / "<name>.py"), run_name="__main__")
```

### Test Isolation Pattern (Foundation Tools)
```python
# All subprocess calls to sibling tools are monkeypatched in tests
monkeypatch.setattr(sync, "_run_subprocess", FakeRunner(...))
# FakeRunner.commands_containing checks cmd[:3] only to avoid false matches
# from tmp_path directories containing tool name substrings
```

### Atomic Write Pattern (Used in `techvault-tool-register`)
```python
fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=target.parent)
os.close(fd)
target.write_text(new_content)
py_compile.compile(str(tmp_path), doraise=True)
shutil.move(tmp_path, target)
```

### Exit Code Convention (All Foundation Tools)
| Exit code | Meaning |
|---|---|
| 0 | Success / dry-run complete / all pass |
| 1 | Failure (non-compliant, findings, one or more steps failed) |
| 2 | Usage/config error or fatal scan error |

### JSON Report Format (`techvault-tool-sync`)
```json
{
  "apply": false,
  "techvault_root": "<path>",
  "tools_dir": "<path>",
  "tools": [
    {
      "tool_id": "sample_tool",
      "overall": "pass",
      "steps": {
        "validate": {"status": "pass", "exit_code": 0, "stdout": "...", "stderr": "..."},
        "tests":    {"status": "pass", "exit_code": 0, "stdout": "...", "stderr": "..."},
        "security": {"status": "pass", "exit_code": 0, "stdout": "...", "stderr": "..."},
        "register": {"status": "pass", "exit_code": 0, "stdout": "...", "stderr": "..."}
      }
    }
  ]
}
```
Tools sorted by `tool_id`; stdout/stderr truncated to 20,000 chars; `sort_keys=True`.

---

## 16. Architecture Design Questions / Open Items

The following are open design considerations relevant for ChatGPT architecture discussions:

1. **Template versioning strategy** — `TEMPLATE_MANIFEST.json` has `template_version: "2.0.0"`. How should `tool.toml` record which template version a tool was built against? What is the migration path when the template bumps?

2. **`techvault-tool-template-check` vs. `techvault-tool-validate`** — The existing validator checks compliance only at Phase 6 gate time. A drift detector would run continuously against already-shipped tools. Should these be merged (with a `--drift` flag) or remain separate tools?

3. **`techvault-tool-schema-gen` from `tool.toml`** — What fields should `tool.toml` contain to enable stub generation of `schemas.py` / `router.py` / `service.py`? Currently `tool.toml` is minimal. Needs a schema definition section.

4. **`techvault-tool-integration-test`** — Requires FastAPI and uvicorn to be available. Should it be a separate venv or can it reuse the tool's deps? How should it handle tools that don't have FastAPI installed locally?

5. **CI integration** — The sync orchestrator is ready for CI. The remaining decision is what `--techvault-root` should point to in a CI/CD context (presumably the main TechVault backend repo checked out as a sibling).

6. **`techvault-tool-template-patch`scope** — Should auto-patching add only new prompt files (safe) or also update existing SOT sections (risky)? Separate `--safe` and `--full` modes?

7. **Prompt pack evolution** — As new phases or prompt files are added (e.g., a Phase 10), how are existing tool repos migrated? The `prompts-update` tool is the answer but its patch strategy needs defining.

---

## 17. Tech Stack

| Technology | Role |
|---|---|
| Python 3.12 | All foundation tools and generated tools |
| FastAPI | API adapter layer in each tool |
| Pydantic v2 | Request/response schema validation |
| pytest 9.0.2 | All tests |
| stdlib only | All foundation tools (`pathlib`, `ast`, `json`, `hashlib`, `subprocess`, `shutil`, `tempfile`, etc.) |
| No external deps | Foundation tools have zero third-party requirements |

---

*This document is an accurate snapshot of the repository as of March 5, 2026. Upload to ChatGPT to provide full context for architecture design, Copilot prompt development, and next action items.*
