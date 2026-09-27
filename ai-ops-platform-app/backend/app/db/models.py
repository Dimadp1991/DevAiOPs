from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    alert: Mapped[dict] = mapped_column(JSONB, nullable=False)
    service_info: Mapped[dict] = mapped_column(JSONB, nullable=False)
    k8s_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    telemetry: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    knowledge_base: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class RunbookRow(Base):
    __tablename__ = "runbooks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class HistoricalIncidentRow(Base):
    __tablename__ = "historical_incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
