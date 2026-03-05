"""Catalog loader with proper path safety validation."""
from __future__ import annotations


def load_catalog(path: str) -> list[dict]:
    """Load a catalog from a relative path.

    Raises ValueError for:
    - Absolute paths (starting with / or a Windows drive letter)
    - Path traversal segments (..)
    - Non-UTF-8 input
    """
    # Reject non-UTF-8 input
    if isinstance(path, bytes):
        try:
            path = path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Non-UTF-8 path rejected: {exc}") from exc
    else:
        try:
            path.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Non-UTF-8 path rejected: {exc}") from exc

    # Reject absolute paths (Unix and Windows)
    if os.path.isabs(path) or path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        raise ValueError(f"Absolute paths are not allowed: {path!r}")

    # Reject path traversal
    if ".." in path:
        raise ValueError(f"Path traversal segments are not allowed: {path!r}")

    return []


import os  # noqa: E402 — intentionally placed after function for readability
