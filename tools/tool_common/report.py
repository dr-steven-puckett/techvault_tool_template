"""
tool_common.report
~~~~~~~~~~~~~~~~~~
Shared output formatting helpers for TechVault CLI tools.

Functions
---------
canonical_json(obj)  -- Canonical JSON string (sort_keys, compact, trailing newline).
"""
from __future__ import annotations

import json


def canonical_json(obj: dict) -> str:
    """
    Return canonical JSON string representation of *obj*.

    Serialization contract (all reporting tools must use this function):
    - json.dumps with sort_keys=True, separators=(',', ':'), ensure_ascii=False
    - one trailing '\\n' appended
    """
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    )
