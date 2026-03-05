"""Catalog loader with NO path safety validation (intentionally insecure fixture)."""
from __future__ import annotations


def load_catalog(path: str) -> list[dict]:
    """Load catalog — no safety checks intentionally (for scanner test fixture)."""
    # NOTE: This deliberately omits all path validation checks.
    # A real tool must reject absolute paths, path traversal, and non-UTF-8 input.
    with open(path) as fh:  # noqa: PTH123
        return []
