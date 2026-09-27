from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.schemas import Alert, AlertmanagerWebhook, Incident, Severity
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _parse_alertmanager_alert(raw: dict) -> tuple[Alert, dict[str, str]]:
    labels = raw.get("labels", {})
    annotations = raw.get("annotations", {})
    severity_raw = labels.get("severity", "warning").lower()
    try:
        severity = Severity(severity_raw)
    except ValueError:
        severity = Severity.WARNING

    fired_at = None
    if starts := raw.get("startsAt"):
        try:
            fired_at = datetime.fromisoformat(starts.replace("Z", "+00:00"))
        except ValueError:
            fired_at = None

    alert = Alert(
        name=labels.get("alertname", "UnknownAlert"),
        severity=severity,
        summary=annotations.get("summary", annotations.get("description", "")),
        labels=labels,
        fired_at=fired_at,
    )
    return alert, labels


@router.post("/webhook", response_model=Incident)
async def alertmanager_webhook(payload: AlertmanagerWebhook) -> Incident:
    """Receive Alertmanager webhook and trigger orchestrator pipeline."""
    if not payload.alerts:
        raise HTTPException(status_code=400, detail="No alerts in payload")

    # Process first firing alert
    firing = next(
        (a for a in payload.alerts if a.get("status", "firing") == "firing"),
        payload.alerts[0],
    )
    alert, labels = _parse_alertmanager_alert(firing)
    return await orchestrator.process_alert(alert, labels)


@router.post("/simulate", response_model=Incident)
async def simulate_alert(alert: Alert) -> Incident:
    """Manually trigger an alert for testing."""
    return await orchestrator.process_alert(alert, alert.labels)
