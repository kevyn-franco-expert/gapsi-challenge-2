"""Common health and metrics endpoints for FastAPI services."""
from __future__ import annotations
from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response


health_router = APIRouter(tags=["observability"])


@health_router.get("/health", summary="Liveness/readiness probe")
async def health_check() -> dict:
    return {"status": "ok", "service": "up"}


@health_router.get("/metrics", summary="Prometheus metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
