"""
tool_common.manifest
~~~~~~~~~~~~~~~~~~~~
Deterministic loader for TEMPLATE_MANIFEST.json.

Functions
---------
load_manifest(manifest_path)      -- Parse and return the manifest dict.
canonical_manifest_bytes(data)    -- Canonical UTF-8 JSON bytes (sort_keys, compact).
"""
from __future__ import annotations

import json
from pathlib import Path


def load_manifest(manifest_path: Path) -> dict:
    """
    Load TEMPLATE_MANIFEST.json and return the parsed dict.

    Raises
    ------
    FileNotFoundError  if the path does not exist.
    json.JSONDecodeError  if the file is not valid JSON.
    """
    raw = manifest_path.read_text(encoding="utf-8")
    return json.loads(raw)


def canonical_manifest_bytes(data: dict) -> bytes:
    """
    Return the canonical UTF-8 byte representation of a manifest dict.

    Serialization contract (must match stamp.normalize_manifest_bytes exactly):
    - json.dumps with sort_keys=True, separators=(',', ':'), ensure_ascii=False
    - one trailing '\\n' appended
    - encoded as UTF-8
    """
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
