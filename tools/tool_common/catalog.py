"""
tool_common.catalog
~~~~~~~~~~~~~~~~~~~
Deterministic catalog generator and loader for TechVault foundation tools.

Functions
---------
generate_catalog(tools_root)  -- Scan tools_root for tool dirs; return catalog dict.
load_catalog(catalog_path)    -- Load catalog dict from JSON file.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path


def _is_tool_dir(d: Path) -> bool:
    """Return True if *d* is a catalogued tool directory.

    Criterion: directory contains at least one ``techvault-tool-*`` launcher
    file.  This matches the existing ``tools.catalog.json`` exactly:
    - Includes all 8 CLI tool dirs (each has a launcher).
    - Excludes ``tool_common`` (shared library; no launcher).
    - Excludes ``tool_template`` (template mirror; no launcher).
    """
    if not d.is_dir():
        return False
    return any(
        f.is_file() and f.name.startswith("techvault-tool-")
        for f in d.iterdir()
    )


def _read_tool_id(tool_dir: Path) -> str:
    """Read ``tool_id`` from ``tool.toml``; fall back to directory name."""
    toml_path = tool_dir / "tool.toml"
    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
        tid = data.get("tool_id")
        return str(tid) if tid else tool_dir.name
    except Exception:  # noqa: BLE001
        return tool_dir.name


def generate_catalog(tools_root: Path) -> dict:
    """Scan *tools_root* for tool directories and return a catalog dict.

    Catalog schema::

        {"version": 1, "tools": [{"id": "<id>", "path": "tools/<dir>"}, ...]}

    Entries are sorted by ``id`` (lexicographic).  The ``path`` value always
    uses the directory name (not the ``tool_id`` from ``tool.toml``) relative
    to the workspace root, formatted as ``tools/<dirname>``.

    Parameters
    ----------
    tools_root:
        Absolute path to the ``tools/`` directory.
    """
    tools_root = Path(tools_root)
    entries: list[dict] = []
    for child in sorted(tools_root.iterdir()):
        if _is_tool_dir(child):
            tid = _read_tool_id(child)
            entries.append({"id": tid, "path": f"tools/{child.name}"})
    # Explicit sort on id for determinism (belt-and-suspenders over sorted iterdir).
    entries.sort(key=lambda e: e["id"])
    return {"tools": entries, "version": 1}


def load_catalog(catalog_path: Path) -> dict:
    """Load and parse a catalog JSON file.

    Parameters
    ----------
    catalog_path:
        Path to the ``tools.catalog.json`` file.

    Raises
    ------
    FileNotFoundError  if the file does not exist.
    json.JSONDecodeError  if the file is not valid JSON.
    """
    raw = Path(catalog_path).read_text(encoding="utf-8")
    return json.loads(raw)
