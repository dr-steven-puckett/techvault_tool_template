# TOOL TEMPLATE — ROADMAP

## Completed

### tool_sync_manager — `techvault-tool-sync` ✓
Deterministic lifecycle orchestrator. Runs validate → tests → security → register in fixed order for a single tool or an entire tools directory. All steps monitorable via `--json-report`. Dry-run by default for registration; `--apply` to write. `--skip-*` flags for selective runs; `--fail-fast` to abort a tool on first failure. Delegates to sibling foundation tools via subprocess (no internal imports). Exit 0 = all pass, exit 1 = any fail, exit 2 = config error.

### tool_template_validator — `techvault-tool-validate` ✓
Standalone CLI that validates a generated tool repository against the template SOT. Checks structure, prompt pack, determinism module, CLI contract, service exception boundary, test coverage, and OpenAPI snapshot presence. Exit 0 = compliant, exit 1 = non-compliant.

### tool_security_harness — `techvault-tool-security-scan` ✓
Deterministic, offline security scanner for generated tool repositories. Four check sections in fixed output order: static policy (AST), path safety, CLI error leaks, API surface sanity. Exit 0 = PASS, exit 1 = FAIL, exit 2 = ERROR. Includes pytest suite with `good_tool` and `bad_tool` fixture repos.

### tool_registration_manager — `techvault-tool-register` ✓
Deterministic, idempotent CLI that registers a tool repo into `backend/techvault/app/api/__init__.py`. Manages two auto-generated blocks: a router import line and an `api_router.include_router()` call. Supports single-tool and `--all` (scan-directory) modes; single-tool mode preserves other registered tools. Dry-run by default; `--apply` to write. Atomic writes with `py_compile` verification. Exit 0 = success/dry-run, exit 1 = validation error, exit 2 = apply failure.

### tool_template_generator — `techvault-tool-create` ✓
Scaffolds a new tool repository from the template, substituting `tool_id` throughout all files and prompt packs.

### library_catalog_search ✓
First concrete tool built from the template. Demonstrates full Phase 0–6 compliance including determinism, standalone catalog mode, OpenAPI snapshot, and all test categories.

---

## Planned / Future (non-binding)

- **Continuous integration hook** — wire `techvault-tool-sync --all <tools_dir> --techvault-root <root> --json-report ci_report.json` into CI on every pull request (foundation tooling is now complete; this is a CI configuration task only)
- **Security harness: dependency audit check** — static scan of `requirements.txt`/`pyproject.toml` for known-vulnerable package versions (offline, pinned advisory list)
- **Security harness: secrets detection** — flag hardcoded API keys, tokens, or passwords in source files (regex patterns, no network)
- **Validator: openapi snapshot drift check** — surface diff when snapshot is stale rather than just noting its presence
- **Richer domain-specific filters** in concrete tool implementations
- **Ranking improvements** that preserve deterministic tie-breakers
- **Bulk endpoints** with deterministic ordering guarantees
- **Optional caching layer** (must remain deterministic; cache keyed on canonical input hash)
- **Benchmark suite** for large-catalog standalone CLI runs
- **Optional synthesis/agent wrapper** as a separate repo — wraps a tool's service layer without modifying the tool itself