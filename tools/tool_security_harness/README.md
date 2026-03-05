# techvault-tool-security-scan

Deterministic, offline security harness for TechVault tool repositories.

## Usage

```bash
techvault-tool-security-scan <repo_path>
```

Or run directly:

```bash
python tools/tool_security_harness/scanner.py <repo_path>
python tools/tool_security_harness/scanner.py <repo_path> --verbose
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | **PASS** — no FAIL-severity findings |
| `1` | **FAIL** — one or more FAIL-severity findings |
| `2` | **ERROR** — could not complete the scan (invalid path, unexpected exception) |

## Checks Performed

Checks run in this fixed order. Output sections and findings are always sorted deterministically.

### 1. Static Policy Checks

Recursively scans all `.py` files under the tool package directory using Python's `ast` module. **FAIL** findings for:

| Pattern | Why |
|---------|-----|
| `subprocess.*(shell=True)` | Arbitrary shell injection |
| `eval(...)` or `exec(...)` | Arbitrary code execution |
| `import pickle` / `from pickle import ...` | Unsafe deserialization |
| `yaml.load(...)` (any usage) | Unsafe YAML deserialization — use `yaml.safe_load` |
| `import requests` / `import httpx` | Unexpected outbound HTTP |
| `import socket` | Raw network access |
| `os.system(...)` | Shell command injection |

**WARN** findings for:

| Pattern | Why |
|---------|-----|
| `logging.basicConfig(level=logging.DEBUG)` | Debug logging enabled by default |
| `logger.setLevel(logging.DEBUG)` | Same |

### 2. Path Safety Checks

If `core/catalog_loader.py` exists, verifies it guards against:

- **Absolute paths** (UNIX `/...` or Windows drive letters)
- **Path traversal segments** (`..`)
- **Non-UTF-8 input**

The check first uses static pattern matching. If patterns cannot be confirmed statically, a minimal dynamic test imports the loader and calls its first public function with bad inputs, asserting `ValueError` is raised.

### 3. CLI Error Leak Checks

If `cli/main.py` exists, runs the CLI twice via `python -m <package>.cli.main`:

1. `health` — verifies stdout is valid JSON and stderr contains no Python traceback
2. *(no args)* — verifies stderr contains no Python traceback and stdout (if any) is valid JSON

### 4. API Surface Sanity

If `api/router.py` exists and `fastapi` is available, imports the router and mounts it into an in-process FastAPI app:

- All routes must be under `/v1/tools/<tool_id>`
- Router tags must include `tools:<tool_id>`
- OpenAPI schema tags must include `tools:<tool_id>`
- No unexpected extra endpoints outside the tool prefix

## Sample Output

```
TechVault Tool Security Scan: /path/to/my_tool
========================================================================

[Static Policy Checks] PASS

[Path Safety Checks] PASS

[CLI Error Leak Checks] PASS

[API Surface Sanity] PASS

------------------------------------------------------------------------
RESULT: PASS
```

Failing example:

```
TechVault Tool Security Scan: /path/to/bad_tool
========================================================================

[Static Policy Checks] FAIL
  [FAIL] bad_tool/core/evil.py:8 — Forbidden import: pickle
  [FAIL] bad_tool/core/evil.py:9 — Forbidden import: socket
  [FAIL] bad_tool/core/evil.py:26 — Forbidden call: subprocess.run(shell=True)
  [FAIL] bad_tool/core/evil.py:32 — Forbidden call: os.system()
  [FAIL] bad_tool/core/evil.py:38 — Forbidden call: eval()
  [FAIL] bad_tool/core/evil.py:43 — Forbidden call: exec()
  [FAIL] bad_tool/core/evil.py:48 — Forbidden call: yaml.load() — use yaml.safe_load() instead
  [WARN] bad_tool/core/evil.py:52 — logging configured at DEBUG level by default

[Path Safety Checks] FAIL
  [FAIL] bad_tool/core/catalog_loader.py:0 — catalog_loader.load_catalog('../traversal') did not raise ValueError

[CLI Error Leak Checks] FAIL
  [FAIL] bad_tool/cli/main.py:0 — no-args invocation: Python traceback detected in stderr

[API Surface Sanity] FAIL
  [FAIL] bad_tool/api/router.py:0 — Router prefix '/tools/bad' does not start with '/v1/tools/bad_tool'

------------------------------------------------------------------------
RESULT: FAIL
```

## Running Tests

From the workspace root:

```bash
cd tools/tool_security_harness
python -m pytest tests/ -v
```

The test suite uses fixture repositories under `tests/fixtures/`:

| Fixture | Purpose |
|---------|---------|
| `tests/fixtures/good_tool/` | Clean tool — scanner must exit 0 |
| `tests/fixtures/bad_tool/` | Intentionally insecure — scanner must exit 1 |

## Constraints

- **Offline** — no network calls are made
- **No fuzzing** — all bad inputs are deterministic constants
- **Read-only** — the scanned repository is never modified
- **Deterministic output** — findings are sorted by `(file_path, line_number, severity, message)` on every run
