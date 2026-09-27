"""AI Agent Orchestrator — enriches incidents from real data sources."""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List

from app.config import settings
from app.models.schemas import (
    Alert,
    GpuMetrics,
    Incident,
    IncidentStatus,
    ServiceInfo,
    Severity,
    Telemetry,
)

from app.services.agent_service import analyze_incident
from app.services.argocd_api import argocd_client
from app.services.k8s_tools import k8s_tools
from app.services.prometheus_tools import prometheus_tools
from app.services.rag_tools import rag_tools
from app.services.storage import incident_store

GPU_KEYWORDS = ("gpu", "cuda", "vllm", "dcgm", "nvidia", "xid", "oom")

logger = logging.getLogger(__name__)

def _generate_incident_id() -> str:
    return f"INC-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:6].upper()}"


def _extract_pod_name(labels: dict[str, str], summary: str) -> str:
    if "pod" in labels:
        return labels["pod"]
    match = re.search(r"Pod\s+([\w-]+)", summary, re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_service_name(labels: dict[str, str], pod_name: str) -> str:
    if "service" in labels:
        return labels["service"]
    if "app" in labels:
        return labels["app"]
    if not pod_name:
        return labels.get("alertname", "unknown-service")
    parts = pod_name.rsplit("-", 2)
    if len(parts) >= 3 and len(parts[-2]) == 8:
        return "-".join(parts[:-2])
    return pod_name


def _is_gpu_related(alert: Alert, logs: list[str]) -> bool:
    text = f"{alert.name} {alert.summary} {' '.join(alert.labels.values())} {' '.join(logs)}".lower()
    return any(kw in text for kw in GPU_KEYWORDS)


class AgentOrchestrator:
    """Orchestrates data collection from K8s, Prometheus/GPU, and RAG sources."""

    async def process_alert(self, alert: Alert, labels: dict[str, str] | None = None) -> Incident:
        labels = labels or alert.labels
        namespace = labels.get("namespace", settings.kubernetes_namespace)
        pod_name = _extract_pod_name(labels, alert.summary)
        service_name = _extract_service_name(labels, pod_name)

        incident = Incident(
            incident_id=_generate_incident_id(),
            status=IncidentStatus.OPEN,
            alert=alert,
            service_info=ServiceInfo(
                name=service_name,
                owner=labels.get("owner", "unknown"),
                criticality=labels.get("criticality", "medium"),
                namespace=namespace,
                labels=labels,
            ),
        )

        incident_store.save(incident)

        if settings.auto_enrich_on_alert:
            return await self.enrich_incident(incident.incident_id, pod_name or None, namespace)

        incident.status = IncidentStatus.INVESTIGATING
        return incident_store.save(incident)

    async def enrich_incident(
        self, incident_id: str, pod_name: str | None = None, namespace: str | None = None
    ) -> Incident:
        incident = incident_store.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        incident.status = IncidentStatus.INVESTIGATING
        incident_store.save(incident)

        ns = namespace or incident.service_info.namespace
        pod = pod_name or incident.k8s_state.pod_name or _extract_pod_name(
            incident.alert.labels, incident.alert.summary
        )

        k8s_state, events, logs = await asyncio.gather(
            k8s_tools.get_pod_status(pod, ns),
            k8s_tools.get_k8s_events(pod, ns),
            k8s_tools.fetch_pod_logs(pod, ns),
        )

        incident.k8s_state = k8s_state
        incident.telemetry.events = events
        incident.telemetry.recent_logs = logs

        async def _no_metrics() -> dict:
            return {}

        metrics_task = prometheus_tools.get_pod_metrics(pod, ns) if pod else _no_metrics()
        gpu_task = self._maybe_fetch_gpu(incident, pod, ns, logs)
        knowledge_task = rag_tools.build_knowledge_base(incident.alert.summary, logs)

        metrics, gpu, knowledge = await asyncio.gather(metrics_task, gpu_task, knowledge_task)

        incident.telemetry.metrics = metrics
        if gpu is not None:
            incident.telemetry.gpu = gpu
        else:
            incident.telemetry.gpu = GpuMetrics()
        incident.knowledge_base = knowledge

        if settings.agent_enabled:
            incident.agent_analysis = await analyze_incident(incident)

        incident.status = IncidentStatus.INVESTIGATING

        # Remediation is available if deployment can be rollbacked or pod needs deletion
        pod_status = incident.k8s_state.pod_status or ""
        restarts = incident.k8s_state.restarts or 0
        needs_pod_deletion = bool(pod) and (
            pod_status in ("CrashLoopBackOff", "Error", "Failed", "OOMKilled", "Unknown", "Unknown (mock)")
            or restarts > 0
        )
        can_rollback = bool(incident.service_info.name) and incident.service_info.name != "unknown-service"
        incident.can_remediate = needs_pod_deletion or can_rollback

        return incident_store.save(incident)

    async def remediate_incident(self, incident_id: str, action: str = "all") -> Incident:
        incident = incident_store.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        ns = incident.service_info.namespace
        pod = incident.k8s_state.pod_name
        service = incident.service_info.name

        actions = []
        matched_app_name = None

        try:
            all_apps = await argocd_client.list_applications()
            app_names = {app.get("metadata", {}).get("name") for app in all_apps if app.get("metadata", {}).get("name")}
            logger.info(f"Found {app_names} applications")
        except Exception as ex:
            app_names = set()

        if service and service != "unknown-service" and service in app_names:
            matched_app_name = service
        elif pod and pod != "unknown-pod":
            pod_parts = pod.split("-")
            potential_names = []
            for i in range(len(pod_parts), 0, -1):
                potential_names.append("-".join(pod_parts[:i]))

            for name in potential_names:
                if name in app_names:
                    matched_app_name = name
                    break

        if matched_app_name:
            argocd_url = f"{argocd_client.server_url}/applications/{matched_app_name}"
            actions.append(f"Application '{matched_app_name}' is managed by ArgoCD. For further details, refer to the Dashboard: {argocd_url}")
        else:
            # Standard K8s remediation fallback
            if action in ("delete_pod", "all") and pod and pod != "unknown-pod":
                ok, msg = await k8s_tools.delete_pod(pod, ns)
                actions.append(msg)
            if action in ("rollback", "all") and service and service != "unknown-service":
                ok, msg = await k8s_tools.rollback_deployment(service, ns)
                actions.append(msg)

        if not actions:
            actions.append(f"No targeted K8s object found for action '{action}'")

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for act in actions:
            if "ArgoCD" in act:
                incident.telemetry.events.insert(0, f"{ts} AIOps {act}")
            incident.telemetry.events.insert(0, f"Normal RemediationExecuted {ts} AIOps {act}")

        incident.status = IncidentStatus.RESOLVED
        incident.can_remediate = False
        return incident_store.save(incident)

    async def _maybe_fetch_gpu(
        self, incident: Incident, pod: str, ns: str, logs: list[str]
    ) -> GpuMetrics | None:
        if not _is_gpu_related(incident.alert, logs):
            has_gpu = await k8s_tools.pod_requests_gpu(pod, ns) if pod else False
            if not has_gpu:
                return None

        node = await k8s_tools.get_pod_node(pod, ns) if pod else ""
        return await prometheus_tools.get_gpu_metrics(pod_name=pod, node_name=node, namespace=ns)


orchestrator = AgentOrchestrator()


def seed_sample_incident() -> Incident:
    """Optional demo incident — only when SEED_DEMO_INCIDENT=true."""
    alert = Alert(
        name="KubePodCrashLooping",
        severity=Severity.CRITICAL,
        summary="Pod worker-app-7d9b4f98d-x9z2q is restarting repeatedly",
        labels={
            "pod": "worker-app-7d9b4f98d-x9z2q",
            "namespace": "default",
            "app": "data-processing-worker",
        },
    )
    incident = Incident(
        incident_id="INC-DEMO-0001",
        status=IncidentStatus.OPEN,
        alert=alert,
        service_info=ServiceInfo(
            name="data-processing-worker",
            owner="DevOps Team",
            criticality="high",
            namespace="default",
        ),
    )
    incident_store.save(incident)
    return incident
