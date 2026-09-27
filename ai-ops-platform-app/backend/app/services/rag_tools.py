"""Runbook and historical incident retrieval — PostgreSQL RAG search."""

import logging

from app.config import settings
from app.db.models import HistoricalIncidentRow, RunbookRow
from app.db.session import SessionLocal
from app.models.schemas import KnowledgeBase

logger = logging.getLogger(__name__)


class RAGTools:
    """Search runbooks and past incidents."""

    def _score(self, text: str, keywords: list[str]) -> int:
        lower = text.lower()
        return sum(1 for kw in keywords if kw.lower() in lower)

    async def search_runbooks(self, query: str, limit: int = 3) -> list[str]:
        if SessionLocal is not None and settings.uses_postgres:
            try:
                with SessionLocal() as session:
                    rows = session.query(RunbookRow).all()
                    scored = sorted(
                        rows,
                        key=lambda r: self._score(query, r.keywords or []),
                        reverse=True,
                    )
                    return [
                        r.content
                        for r in scored[:limit]
                        if self._score(query, r.keywords or []) > 0
                    ]
            except Exception as exc:
                logger.error("DB runbook search failed: %s", exc)

        return []

    async def get_past_incidents(self, query: str, limit: int = 5) -> list[str]:
        if SessionLocal is not None and settings.uses_postgres:
            try:
                with SessionLocal() as session:
                    rows = session.query(HistoricalIncidentRow).all()
                    scored = sorted(
                        rows,
                        key=lambda r: self._score(query, r.keywords or []),
                        reverse=True,
                    )
                    return [
                        f"{r.id}: {r.resolution or r.summary}"
                        for r in scored[:limit]
                        if self._score(query, r.keywords or []) > 0
                    ]
            except Exception as exc:
                logger.error("DB historical incident search failed: %s", exc)

        return []

    async def build_knowledge_base(self, alert_summary: str, logs: list[str]) -> KnowledgeBase:
        query = f"{alert_summary} {' '.join(logs)}"
        runbooks = await self.search_runbooks(query)
        incidents = await self.get_past_incidents(query)

        suggested: list[str] = []
        if runbooks:
            suggested.append(f"Follow runbook: {runbooks[0][:100]}")

        return KnowledgeBase(
            runbook=runbooks[0] if runbooks else "",
            historical_incidents=incidents,
            suggested_actions=suggested,
        )


rag_tools = RAGTools()
