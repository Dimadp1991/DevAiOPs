import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base, HistoricalIncidentRow, RunbookRow

logger = logging.getLogger(__name__)

engine = None
SessionLocal: sessionmaker[Session] | None = None

DEFAULT_RUNBOOKS = [
    {
        "id": "Runbook-CUDA-OOM",
        "title": "CUDA Out of Memory",
        "content": (
            "Runbook-CUDA-OOM: Increase GPU batch size limit or expand memory limit "
            "in Helm values. Check DCGM XID errors and reduce model batch parallelism."
        ),
        "keywords": ["cuda", "oom", "gpu", "memory", "vllm", "crashloop"],
    },
    {
        "id": "Runbook-PodCrashLoop",
        "title": "Pod Crash Loop",
        "content": (
            "Runbook-PodCrashLoop: Inspect container logs, verify liveness probe "
            "endpoint, check resource limits and recent deployments."
        ),
        "keywords": ["crashloop", "restart", "liveness", "backoff"],
    },
    {
        "id": "Runbook-HighCPU",
        "title": "High CPU Usage",
        "content": (
            "Runbook-HighCPU: Check for traffic spikes, review HPA settings, "
            "profile application hot paths, and verify resource requests/limits."
        ),
        "keywords": ["cpu", "high", "utilization", "throttle"],
    },
]

DEFAULT_HISTORY = [
    {
        "id": "INC-2026-0412",
        "summary": "vLLM Qwen CUDA OOM during high concurrent requests",
        "root_cause": "GPU VRAM exhausted — batch size too large",
        "resolution": "Reduced max_num_seqs and gpu_memory_utilization in vLLM args",
        "keywords": ["cuda", "oom", "batch", "gpu", "vllm", "qwen"],
    },
    {
        "id": "INC-2025-1120",
        "summary": "API pod crash loop after deployment",
        "root_cause": "Liveness probe timeout under load",
        "resolution": "Increased liveness probe timeout and initialDelaySeconds",
        "keywords": ["crashloop", "liveness", "probe"],
    },
]


def init_db() -> bool:
    """Create tables and seed runbooks. Returns True if PostgreSQL is ready."""
    global engine, SessionLocal

    if not settings.uses_postgres:
        logger.info("DATABASE_URL is not PostgreSQL — using in-memory incident store")
        return False

    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)
        _seed_reference_data()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected and schema ready")
        return True
    except Exception as exc:
        logger.warning("PostgreSQL unavailable (%s) — falling back to in-memory store", exc)
        engine = None
        SessionLocal = None
        return False


def _seed_reference_data() -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        if session.query(RunbookRow).count() == 0:
            for rb in DEFAULT_RUNBOOKS:
                session.add(RunbookRow(**rb))
        if session.query(HistoricalIncidentRow).count() == 0:
            for h in DEFAULT_HISTORY:
                session.add(HistoricalIncidentRow(**h))
        session.commit()


def get_db_session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()
