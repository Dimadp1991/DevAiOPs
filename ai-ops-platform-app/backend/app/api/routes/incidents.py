from fastapi import APIRouter, HTTPException

from app.models.schemas import Incident, IncidentStatus, IncidentSummary, RemediateRequest
from app.services.orchestrator import orchestrator
from app.services.storage import incident_store

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentSummary])
async def list_incidents() -> list[IncidentSummary]:
    return incident_store.list_summaries()


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str) -> Incident:
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/enrich", response_model=Incident)
async def enrich_incident(incident_id: str) -> Incident:
    try:
        return await orchestrator.enrich_incident(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{incident_id}/remediate", response_model=Incident)
async def remediate_incident(incident_id: str, req: RemediateRequest | None = None) -> Incident:
    action = req.action.value if req else "all"
    try:
        return await orchestrator.remediate_incident(incident_id, action=action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{incident_id}/status", response_model=Incident)
async def update_status(incident_id: str, status: IncidentStatus) -> Incident:
    incident = incident_store.update_status(incident_id, status)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
