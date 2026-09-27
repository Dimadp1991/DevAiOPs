from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class RemediationAction(str, Enum):
    ALL = "all"
    ROLLBACK = "rollback"
    DELETE_POD = "delete_pod"


class RemediateRequest(BaseModel):
    action: RemediationAction = RemediationAction.ALL


class Alert(BaseModel):
    name: str
    severity: Severity
    summary: str
    labels: dict[str, str] = Field(default_factory=dict)
    fired_at: datetime | None = None


class ServiceInfo(BaseModel):
    name: str
    owner: str
    criticality: str
    namespace: str = "default"
    labels: dict[str, str] = Field(default_factory=dict)


class K8sState(BaseModel):
    pod_name: str = ""
    pod_status: str = ""
    restarts: int = 0
    deployment_ready_replicas: str = ""
    health_check: str = ""
    namespace: str = "default"


class GpuMetrics(BaseModel):
    model: str = ""
    utilization_pct: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    temperature_celsius: float | None = None
    power_watts: float | None = None
    xid_errors: list[int] = Field(default_factory=list)


class Telemetry(BaseModel):
    gpu: GpuMetrics = Field(default_factory=GpuMetrics)
    metrics: dict[str, Any] = Field(default_factory=dict)
    recent_logs: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)


class KnowledgeBase(BaseModel):
    runbook: str = ""
    historical_incidents: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)


class AgentAnalysis(BaseModel):
    root_cause: str = ""
    confidence: float = 0.0
    remediation_steps: list[str] = Field(default_factory=list)
    reasoning: str = ""


class Incident(BaseModel):
    incident_id: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    alert: Alert
    service_info: ServiceInfo
    k8s_state: K8sState = Field(default_factory=K8sState)
    telemetry: Telemetry = Field(default_factory=Telemetry)
    knowledge_base: KnowledgeBase = Field(default_factory=KnowledgeBase)
    agent_analysis: AgentAnalysis | None = None
    can_remediate: bool = False


class AlertmanagerWebhook(BaseModel):
    """Subset of Alertmanager webhook payload."""

    version: str = "4"
    status: str = "firing"
    receiver: str = ""
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class IncidentSummary(BaseModel):
    incident_id: str
    status: IncidentStatus
    alert_name: str
    severity: Severity
    summary: str
    service_name: str
    created_at: datetime
