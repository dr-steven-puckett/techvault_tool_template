"""API router for bad_tool — routes NOT under /v1/tools/bad_tool (intentional violation)."""
from __future__ import annotations

try:
    from fastapi import APIRouter

    # Intentional violation: wrong prefix and wrong tag
    router = APIRouter(
        prefix="/tools/bad",  # missing /v1 and wrong tool id
        tags=["bad_tool"],    # wrong tag format — missing "tools:" prefix
    )

    @router.get("/search")
    def search(q: str = "") -> dict:
        return {"results": []}

    @router.get("/internal/debug")  # unexpected extra endpoint
    def debug_internal() -> dict:
        return {"debug": True}

except ImportError:
    class _StubRouter:  # type: ignore[no-reuse-as-module]
        prefix = "/tools/bad"
        tags = ["bad_tool"]
        routes: list = []

    router = _StubRouter()  # type: ignore[assignment]
