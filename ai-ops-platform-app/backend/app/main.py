import logging
from contextlib import asynccontextmanager
from fastapi import  FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, health, incidents
from app.config import settings
from app.services.orchestrator import orchestrator, seed_sample_incident
from app.services.storage import incident_store

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger(__name__)

_API_PREFIX = "/api/v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    incident_store.initialize()
    logger.info(
        "AIOps backend started (db=%s, mock=%s, prometheus=%s)",
        incident_store.db_enabled,
        settings.use_mock_providers,
        settings.prometheus_url or "disabled",
    )

    if settings.seed_demo_incident:
        demo = seed_sample_incident()
        await orchestrator.enrich_incident(demo.incident_id)
        logger.info("Seeded demo incident %s", demo.incident_id)

    yield


app = FastAPI(
    title=settings.app_name,
    description="AIOps incident orchestration API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=f"{_API_PREFIX}/docs",
    redoc_url=f"{_API_PREFIX}/redoc",
    openapi_url=f"{_API_PREFIX}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=_API_PREFIX)
app.include_router(incidents.router, prefix=_API_PREFIX)
app.include_router(alerts.router, prefix=_API_PREFIX)

#TO RUN LOCAL FOR DEBUG
# if __name__ == "__main__":
#     import uvicorn
#     # 3. Pass the lowercase string variable directly to Uvicorn
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=8000,
#         log_level="debug"
#     )