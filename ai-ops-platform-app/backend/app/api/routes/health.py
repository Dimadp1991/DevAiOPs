import logging

from fastapi import APIRouter

from app.config import settings
from app.services.storage import incident_store

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

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

# Filter out health check endpoints from standard access logs
class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/v1/health" not in record.getMessage() and "/api/v1/ready" not in record.getMessage()

# Apply to uvicorn/gunicorn logger
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())