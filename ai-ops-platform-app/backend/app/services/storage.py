from datetime import datetime, timezone

from app.config import settings
from app.db.models import IncidentRow
from app.db.session import SessionLocal, init_db
from app.models.schemas import Incident, IncidentStatus, IncidentSummary


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class IncidentStore:
    """PostgreSQL-backed store with in-memory fallback."""

    def __init__(self) -> None:
        self._memory: dict[str, Incident] = {}
        self._db_enabled = False

    def initialize(self) -> None:
        self._db_enabled = init_db()

    @property
    def db_enabled(self) -> bool:
        return self._db_enabled

    def save(self, incident: Incident) -> Incident:
        incident.updated_at = datetime.now(timezone.utc)
        if self._db_enabled:
            self._save_db(incident)
        else:
            self._memory[incident.incident_id] = incident
        return incident

    def get(self, incident_id: str) -> Incident | None:
        if self._db_enabled:
            return self._get_db(incident_id)
        return self._memory.get(incident_id)

    def list_all(self) -> list[Incident]:
        if self._db_enabled:
            return self._list_db()
        return sorted(self._memory.values(), key=lambda i: i.created_at, reverse=True)

    def list_summaries(self) -> list[IncidentSummary]:
        return [
            IncidentSummary(
                incident_id=i.incident_id,
                status=i.status,
                alert_name=i.alert.name,
                severity=i.alert.severity,
                summary=i.alert.summary,
                service_name=i.service_info.name,
                created_at=i.created_at,
            )
            for i in self.list_all()
        ]

    def update_status(self, incident_id: str, status: IncidentStatus) -> Incident | None:
        incident = self.get(incident_id)
        if not incident:
            return None
        incident.status = status
        return self.save(incident)

    def _save_db(self, incident: Incident) -> None:
        from app.db.session import SessionLocal as SL

        assert SL is not None
        with SL() as session:
            row = session.get(IncidentRow, incident.incident_id)
            payload = incident.model_dump(mode="json")
            if row is None:
                row = IncidentRow(
                    incident_id=incident.incident_id,
                    status=incident.status.value,
                    alert=payload["alert"],
                    service_info=payload["service_info"],
                    k8s_state=payload["k8s_state"],
                    telemetry=payload["telemetry"],
                    knowledge_base=payload["knowledge_base"],
                    agent_analysis=payload.get("agent_analysis"),
                )
                session.add(row)
            else:
                row.status = incident.status.value
                row.alert = payload["alert"]
                row.service_info = payload["service_info"]
                row.k8s_state = payload["k8s_state"]
                row.telemetry = payload["telemetry"]
                row.knowledge_base = payload["knowledge_base"]
                row.agent_analysis = payload.get("agent_analysis")
                row.updated_at = incident.updated_at
            session.commit()

    def _get_db(self, incident_id: str) -> Incident | None:
        from app.db.session import SessionLocal as SL

        assert SL is not None
        with SL() as session:
            row = session.get(IncidentRow, incident_id)
            if not row:
                return None
            return self._row_to_incident(row)

    def _list_db(self) -> list[Incident]:
        from app.db.session import SessionLocal as SL

        assert SL is not None
        with SL() as session:
            rows = session.query(IncidentRow).order_by(IncidentRow.created_at.desc()).all()
            return [self._row_to_incident(r) for r in rows]

    @staticmethod
    def _row_to_incident(row: IncidentRow) -> Incident:
        data = {
            "incident_id": row.incident_id,
            "status": row.status,
            "created_at": _to_utc(row.created_at),
            "updated_at": _to_utc(row.updated_at),
            "alert": row.alert,
            "service_info": row.service_info,
            "k8s_state": row.k8s_state or {},
            "telemetry": row.telemetry or {},
            "knowledge_base": row.knowledge_base or {},
            "agent_analysis": row.agent_analysis,
        }
        return Incident.model_validate(data)


incident_store = IncidentStore()
