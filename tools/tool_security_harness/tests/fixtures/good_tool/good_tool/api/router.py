"""API router for good_tool — routes strictly under /v1/tools/good_tool."""
from __future__ import annotations

try:
    from fastapi import APIRouter  # type: ignore[import-untyped]

    router = APIRouter(
        prefix="/v1/tools/good_tool",
        tags=["tools:good_tool"],
    )

    @router.get("/search")
    def search(q: str = "") -> dict:
        """Search the good_tool catalog."""
        return {"tool": "good_tool", "query": q, "results": []}

    @router.get("/health")
    def health() -> dict:
        """Return router health status."""
        return {"status": "ok"}

except ImportError:
    # FastAPI not installed — expose a minimal stub so the file is importable
    class _StubRouter:  # type: ignore[no-reuse-as-module]
        prefix = "/v1/tools/good_tool"
        tags = ["tools:good_tool"]
        routes: list = []

    router = _StubRouter()  # type: ignore[assignment]
