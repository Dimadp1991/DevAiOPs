from fastapi import APIRouter

from app.config import settings
from app.services.storage import incident_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "aiops-backend",
        "version": "2.0.0",
        "database": "postgresql" if incident_store.db_enabled else "memory",
        "mock_providers": settings.use_mock_providers,
    }


@router.get("/ready")
async def ready() -> dict:
    checks: dict[str, str] = {"api": "ok"}
    if settings.uses_postgres and not incident_store.db_enabled:
        checks["database"] = "unavailable"
        return {"status": "not_ready", "checks": checks}
    checks["database"] = "ok" if incident_store.db_enabled else "memory_fallback"
    return {"status": "ready", "checks": checks}
