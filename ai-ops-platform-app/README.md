# AIOps Platform

AI-driven incident orchestration platform built with **FastAPI** (backend/API) and **Flask** (UI). Ingests alerts from Prometheus Alertmanager, enriches incidents with Kubernetes state, Prometheus/GPU telemetry, and runbook RAG, then produces agent-assisted root-cause analysis and remediation steps.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Data Schemas](#data-schemas)
- [Data Source Mapping](#data-source-mapping)
- [API Reference](#api-reference)
- [Orchestrator Pipeline](#orchestrator-pipeline)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [Docker](#docker)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Alertmanager Integration](#alertmanager-integration)

---

## Architecture

```
                    [ Alertmanager / Incident Trigger ]
                                  |
                                  v
                        [ AI Agent Orchestrator ]
                                  |
            +---------------------+---------------------+
            |                     |                     |
            v                     v                     v
   [ FastMCP K8s Tools ]  [ FastMCP Prom/GPU Tools ]  [ Local Vector DB (RAG) ]
   - get_pod_status()     - query_prometheus()        - search_runbooks()
   - get_k8s_events()     - get_gpu_metrics()         - get_past_incidents()
   - fetch_pod_logs()

[ Telemetry Sources ] --> [ Collector / Storage ] --> [ AIOps App / Agent ] --> [ Execution / Remediation ]
 (K8s, Prometheus, DCGM)    (Prometheus, Loki)         (FastMCP + LLM)            (Kubernetes API, GitOps)
```

| Component | Technology | Port | Role |
|-----------|------------|------|------|
| Backend API | FastAPI + Uvicorn | 8000 | Incidents, webhooks, orchestrator |
| UI | Flask + Gunicorn | 5000 | Dashboard and incident detail views |
| Storage | In-memory (MVP) | — | Replace with PostgreSQL in production |
| RAG | Keyword match (MVP) | — | Replace with Qdrant vector search |

---

## Project Structure

```
aiOps/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Environment settings
│   │   ├── api/routes/
│   │   │   ├── health.py
│   │   │   ├── incidents.py
│   │   │   └── alerts.py
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic data models
│   │   └── services/
│   │       ├── orchestrator.py     # Agent orchestrator
│   │       ├── k8s_tools.py        # Kubernetes data tools
│   │       ├── prometheus_tools.py # Prometheus / GPU metrics
│   │       ├── rag_tools.py        # Runbook & incident RAG
│   │       └── storage.py          # Incident store
│   ├── requirements.txt
│   └── Dockerfile
├── ui/
│   ├── app.py
│   ├── templates/
│   ├── static/
│   ├── requirements.txt
│   └── Dockerfile
├── k8s/ai-ops-platform-chart/      # Helm chart (aligned with working deployment)
├── setup-deps-storage.sh           # Populate python-deps-pvc for K8s slim images
├── Jenkinsfile                     # CI build → zot.local registry
├── deploy/                         # Alertmanager config sample
├── docker-compose.yml
└── .env.example
```

---

## Data Schemas

### Enums

#### `Severity`

| Value | Description |
|-------|-------------|
| `critical` | Highest priority — immediate action required |
| `warning` | Elevated concern — investigate soon |
| `info` | Informational alert |

#### `IncidentStatus`

| Value | Description |
|-------|-------------|
| `open` | Incident created, not yet processed |
| `investigating` | Orchestrator is gathering context |
| `remediating` | Root cause identified, remediation in progress |
| `resolved` | Incident closed |

---

### Core Models

#### `Alert`

Incoming alert from Alertmanager or manual simulation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | yes | Alert name (e.g. `KubePodCrashLooping`) |
| `severity` | `Severity` | yes | Alert severity level |
| `summary` | `string` | yes | Human-readable alert summary |
| `labels` | `object<string,string>` | no | Key-value labels (pod, namespace, etc.) |
| `fired_at` | `datetime` | no | When the alert fired (ISO 8601) |

```json
{
  "name": "KubePodCrashLooping",
  "severity": "critical",
  "summary": "Pod worker-app-7d9b4f98d-x9z2q is restarting repeatedly",
  "labels": {
    "pod": "worker-app-7d9b4f98d-x9z2q",
    "namespace": "default",
    "app": "data-processing-worker"
  },
  "fired_at": "2026-09-17T13:45:00Z"
}
```

---

#### `ServiceInfo`

Metadata about the affected service.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | yes | Service name |
| `owner` | `string` | yes | Owning team |
| `criticality` | `string` | yes | Business criticality tier (`high`, `medium`, `low`) |
| `namespace` | `string` | no | Kubernetes namespace (default: `default`) |
| `labels` | `object<string,string>` | no | Additional metadata labels |

```json
{
  "name": "data-processing-worker",
  "owner": "DevOps Team",
  "criticality": "high",
  "namespace": "default",
  "labels": {}
}
```

---

#### `K8sState`

Kubernetes pod and deployment state.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pod_name` | `string` | no | Affected pod name |
| `pod_status` | `string` | no | Pod phase (e.g. `CrashLoopBackOff`, `Running`) |
| `restarts` | `integer` | no | Container restart count |
| `deployment_ready_replicas` | `string` | no | Ready/desired replicas (e.g. `1/3`) |
| `health_check` | `string` | no | Liveness/readiness probe result |
| `namespace` | `string` | no | Kubernetes namespace |

```json
{
  "pod_name": "worker-app-7d9b4f98d-x9z2q",
  "pod_status": "CrashLoopBackOff",
  "restarts": 12,
  "deployment_ready_replicas": "1/3",
  "health_check": "Liveness probe failed: HTTP 500",
  "namespace": "default"
}
```

---

#### `GpuMetrics`

GPU telemetry from DCGM exporter / NVML.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `utilization_pct` | `float` | no | GPU utilization percentage |
| `vram_used_mb` | `float` | no | VRAM used in megabytes |
| `vram_total_mb` | `float` | no | Total VRAM in megabytes |
| `xid_errors` | `integer[]` | no | NVIDIA XID hardware error codes |

```json
{
  "utilization_pct": 98,
  "vram_used_mb": 24100,
  "vram_total_mb": 24576,
  "xid_errors": [31]
}
```

---

#### `Telemetry`

Aggregated observability data for an incident.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gpu` | `GpuMetrics` | no | GPU hardware metrics |
| `metrics` | `object` | no | Prometheus metrics (CPU, memory, etc.) |
| `recent_logs` | `string[]` | no | Tail of pod logs |
| `events` | `string[]` | no | Recent Kubernetes warning events |

```json
{
  "gpu": {
    "utilization_pct": 98,
    "vram_used_mb": 24100,
    "vram_total_mb": 24576,
    "xid_errors": [31]
  },
  "metrics": {
    "cpu_usage_cores": 3.8,
    "memory_rss_bytes": "7.8Gi"
  },
  "recent_logs": [
    "2026-09-17T13:48:10Z CUDA error: out of memory",
    "2026-09-17T13:48:11Z Fatal python exception: MemoryError"
  ],
  "events": [
    "Warning BackOff 2m ago kubelet Back-off restarting failed container"
  ]
}
```

---

#### `KnowledgeBase`

Runbook and historical incident context from RAG.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `runbook` | `string` | no | Best-matching runbook text |
| `historical_incidents` | `string[]` | no | Similar past incidents and resolutions |
| `suggested_actions` | `string[]` | no | Recommended remediation actions |

```json
{
  "runbook": "Runbook-CUDA-OOM: Increase GPU batch size limit or expand memory limit in Helm values.",
  "historical_incidents": [
    "INC-2026-0412: Fixed by adjusting batch size parameter in ConfigMap."
  ],
  "suggested_actions": [
    "Reduce GPU batch size in ConfigMap/Helm values",
    "Increase GPU memory limit or request additional GPU node"
  ]
}
```

---

#### `AgentAnalysis`

AI agent root-cause analysis and remediation plan.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `root_cause` | `string` | no | Identified root cause |
| `confidence` | `float` | no | Confidence score (0.0 – 1.0) |
| `remediation_steps` | `string[]` | no | Ordered remediation steps |
| `reasoning` | `string` | no | Agent reasoning chain |

```json
{
  "root_cause": "GPU CUDA out-of-memory (OOM) causing container crash",
  "confidence": 0.92,
  "remediation_steps": [
    "Reduce batch size in deployment ConfigMap (e.g. BATCH_SIZE=16 → 8)",
    "Verify GPU memory limits in Helm values",
    "Consider scaling to additional GPU nodes if sustained load"
  ],
  "reasoning": "Logs show CUDA OOM; GPU VRAM at 24100/24576 MB (98% util) | DCGM XID errors detected: [31]"
}
```

---

#### `Incident` (full document)

Top-level incident object combining all context.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `incident_id` | `string` | yes | Unique ID (format: `INC-YYYY-MMDD-XXXXXX`) |
| `status` | `IncidentStatus` | no | Current lifecycle status |
| `created_at` | `datetime` | no | Creation timestamp (UTC) |
| `updated_at` | `datetime` | no | Last update timestamp (UTC) |
| `alert` | `Alert` | yes | Source alert |
| `service_info` | `ServiceInfo` | yes | Affected service metadata |
| `k8s_state` | `K8sState` | no | Kubernetes state |
| `telemetry` | `Telemetry` | no | Logs, metrics, GPU data |
| `knowledge_base` | `KnowledgeBase` | no | Runbook and history |
| `agent_analysis` | `AgentAnalysis` | no | Agent output (null until enriched) |

#### Full example

```json
{
  "incident_id": "INC-2026-0917-01",
  "status": "remediating",
  "created_at": "2026-09-17T13:45:00Z",
  "updated_at": "2026-09-17T13:48:30Z",
  "alert": {
    "name": "KubePodCrashLooping",
    "severity": "critical",
    "summary": "Pod worker-app-7d9b4f98d-x9z2q is restarting repeatedly",
    "labels": {
      "pod": "worker-app-7d9b4f98d-x9z2q",
      "namespace": "default",
      "app": "data-processing-worker"
    },
    "fired_at": "2026-09-17T13:45:00Z"
  },
  "service_info": {
    "name": "data-processing-worker",
    "owner": "DevOps Team",
    "criticality": "high",
    "namespace": "default",
    "labels": {}
  },
  "k8s_state": {
    "pod_name": "worker-app-7d9b4f98d-x9z2q",
    "pod_status": "CrashLoopBackOff",
    "restarts": 12,
    "deployment_ready_replicas": "1/3",
    "health_check": "Liveness probe failed: HTTP 500",
    "namespace": "default"
  },
  "telemetry": {
    "gpu": {
      "utilization_pct": 98,
      "vram_used_mb": 24100,
      "vram_total_mb": 24576,
      "xid_errors": [31]
    },
    "metrics": {
      "cpu_usage_cores": 3.8,
      "memory_rss_bytes": "7.8Gi"
    },
    "recent_logs": [
      "2026-09-17T13:48:10Z CUDA error: out of memory",
      "2026-09-17T13:48:11Z Fatal python exception: MemoryError"
    ],
    "events": [
      "Warning BackOff 2m ago kubelet Back-off restarting failed container"
    ]
  },
  "knowledge_base": {
    "runbook": "Runbook-CUDA-OOM: Increase GPU batch size limit or expand memory limit in Helm values.",
    "historical_incidents": [
      "INC-2026-0412: Fixed by adjusting batch size parameter in ConfigMap."
    ],
    "suggested_actions": [
      "Reduce GPU batch size in ConfigMap/Helm values",
      "Increase GPU memory limit or request additional GPU node"
    ]
  },
  "agent_analysis": {
    "root_cause": "GPU CUDA out-of-memory (OOM) causing container crash",
    "confidence": 0.92,
    "remediation_steps": [
      "Reduce batch size in deployment ConfigMap (e.g. BATCH_SIZE=16 → 8)",
      "Verify GPU memory limits in Helm values",
      "Consider scaling to additional GPU nodes if sustained load",
      "Apply runbook: Runbook-CUDA-OOM"
    ],
    "reasoning": "Logs show CUDA OOM; GPU VRAM at 24100.0/24576.0 MB (98.0% util) | DCGM XID errors detected: [31] | Similar past incident: INC-2026-0412: Fixed by adjusting batch size parameter in ConfigMap."
  }
}
```

---

#### `IncidentSummary`

Lightweight list view returned by `GET /api/v1/incidents`.

| Field | Type | Description |
|-------|------|-------------|
| `incident_id` | `string` | Incident ID |
| `status` | `IncidentStatus` | Current status |
| `alert_name` | `string` | Alert name |
| `severity` | `Severity` | Alert severity |
| `summary` | `string` | Alert summary text |
| `service_name` | `string` | Affected service |
| `created_at` | `datetime` | Creation timestamp |

---

#### `AlertmanagerWebhook`

Subset of the [Alertmanager webhook v4](https://prometheus.io/docs/alerting/latest/notifications/) payload.

| Field | Type | Description |
|-------|------|-------------|
| `version` | `string` | Webhook version (default: `"4"`) |
| `status` | `string` | `firing` or `resolved` |
| `receiver` | `string` | Alertmanager receiver name |
| `alerts` | `object[]` | Array of alert objects with `labels`, `annotations`, `startsAt`, `status` |

---

## Data Source Mapping

| Category | Data Field | Source System | Access Method / Query | Output / Data Payload |
|----------|------------|---------------|----------------------|------------------------|
| Alerting | Alert Details | Prometheus Alertmanager | Webhook `POST /api/v1/alerts/webhook` or `/api/v2/alerts` | Alert name, severity, firing timestamp, labels, summary |
| K8s State | Pod Status | Kubernetes API (`core/v1`) | `get_namespaced_pod()` | Pod phase, restart count, exit codes, container statuses |
| K8s State | Deployment Status | Kubernetes API (`apps/v1`) | `read_namespaced_deployment()` | Desired vs. ready replicas, rollout conditions |
| K8s State | Kubernetes Events | Kubernetes Event API | `list_namespaced_event()` | Warning events (OOMKills, ImagePullBackOff, etc.) |
| K8s State | Health Checks | K8s Probes & API | Pod `status.conditions` | Liveness/readiness probe status and failure details |
| Telemetry | Recent Logs | VictoriaLogs / Loki / K8s API | `read_namespaced_pod_log()` | Stderr/stdout log tail (100–500 lines) |
| Telemetry | Prometheus Metrics | Prometheus Server | `GET /api/v1/query_range` | CPU, memory RSS, network I/O, error rates |
| Hardware | GPU Status | DCGM Exporter / NVML | PromQL on DCGM metrics | GPU util %, VRAM, power, XID error codes |
| Knowledge | Local Runbook | Qdrant / Git (RAG) | Vector similarity search | Matched operational runbook |
| Knowledge | Historical Incidents | PostgreSQL / Vector DB | SQL or vector search | Past post-mortems and proven fixes |
| Context | Service Metadata | CMDB / K8s Labels | Annotations, labels, ConfigMap | Owner, criticality, SLA, dependencies |

**Implementation mapping (code):**

| Tool Service | Methods | File |
|--------------|---------|------|
| K8s Tools | `get_pod_status()`, `get_k8s_events()`, `fetch_pod_logs()` | `backend/app/services/k8s_tools.py` |
| Prometheus Tools | `query_prometheus()`, `get_gpu_metrics()`, `get_pod_metrics()` | `backend/app/services/prometheus_tools.py` |
| RAG Tools | `search_runbooks()`, `get_past_incidents()`, `build_knowledge_base()` | `backend/app/services/rag_tools.py` |

---

## API Reference

Base URL: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Liveness check |
| `GET` | `/api/v1/ready` | Readiness check |

### Incidents

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/incidents` | List all incidents | `IncidentSummary[]` |
| `GET` | `/api/v1/incidents/{id}` | Get full incident | `Incident` |
| `POST` | `/api/v1/incidents/{id}/enrich` | Re-run orchestrator | `Incident` |
| `PATCH` | `/api/v1/incidents/{id}/status?status=resolved` | Update status | `Incident` |

### Alerts

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| `POST` | `/api/v1/alerts/webhook` | Alertmanager webhook | `AlertmanagerWebhook` | `Incident` |
| `POST` | `/api/v1/alerts/simulate` | Manual alert trigger | `Alert` | `Incident` |

### Example: simulate an alert

```bash
curl -X POST http://localhost:8000/api/v1/alerts/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "KubePodCrashLooping",
    "severity": "critical",
    "summary": "Pod worker-app-7d9b4f98d-x9z2q is restarting repeatedly",
    "labels": {
      "pod": "worker-app-7d9b4f98d-x9z2q",
      "namespace": "default",
      "app": "data-processing-worker"
    }
  }'
```

### Example: Alertmanager webhook payload

```json
{
  "version": "4",
  "status": "firing",
  "receiver": "aiops-webhook",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "KubePodCrashLooping",
        "severity": "critical",
        "pod": "worker-app-7d9b4f98d-x9z2q",
        "namespace": "default"
      },
      "annotations": {
        "summary": "Pod worker-app-7d9b4f98d-x9z2q is restarting repeatedly"
      },
      "startsAt": "2026-09-17T13:45:00.000Z"
    }
  ]
}
```

---

## Orchestrator Pipeline

When an alert is received, the orchestrator (`backend/app/services/orchestrator.py`) runs:

1. **Create incident** — Generate `incident_id`, parse pod/service from alert labels
2. **Gather K8s state** — Pod status, events, logs
3. **Gather telemetry** — Prometheus metrics, DCGM GPU data
4. **RAG lookup** — Search runbooks and historical incidents
5. **Agent analysis** — Root cause, confidence, remediation steps
6. **Persist** — Save enriched incident to store

```
Alert → process_alert() → enrich_incident() → agent_analysis → Incident (status: remediating)
```

---

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ENABLED` | `true` | Enable agent root-cause analysis |
| `KUBERNETES_NAMESPACE` | `default` | Default K8s namespace |
| `PROMETHEUS_URL` | `""` | Prometheus base URL (empty = mock) |
| `LOKI_URL` | `""` | Loki base URL for log queries |
| `QDRANT_URL` | `""` | Qdrant vector DB URL |
| `DATABASE_URL` | `sqlite:///./aiops.db` | Persistent storage URL |
| `OPENAI_API_KEY` | `""` | LLM API key (future) |
| `AIOPS_API_URL` | `http://localhost:8000` | Backend URL (Flask UI) |

---

## Local Development

### Prerequisites

- Python 3.12+
- pip

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### UI

```bash
cd ui
pip install -r requirements.txt
set AIOPS_API_URL=http://localhost:8000   # Windows
# export AIOPS_API_URL=http://localhost:8000  # Linux/macOS
python app.py
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| UI dashboard | http://localhost:5000 |

---

## Docker

```bash
docker compose up --build
```

| Service | Image | Port |
|---------|-------|------|
| `backend` | `aiops-backend` | 8000 |
| `ui` | `aiops-ui` | 5000 |

---

## Kubernetes Deployment (Helm)

Matches the working `ai-ops-platform-app` layout: slim images + `python-deps-pvc` for dependencies.

### 1. Prepare Python wheels PVC (first time only)

```bash
pip download -r all_requirements.txt -d ./wheels
chmod +x setup-deps-storage.sh
./setup-deps-storage.sh
```

### 2. Build & push images (or use Jenkins → `zot.local`)

```bash
docker build -t zot.local/aiops-backend:v1.0.0 ./backend
docker build -t zot.local/aiops-ui:v1.0.0 ./ui
```

### 3. Install with Helm

```bash
helm install aiops-platform ./k8s/ai-ops-platform-chart \
  --namespace aiops-platform \
  --create-namespace

# Upgrade
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform

# Optional features
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --set rbac.create=true \
  --set postgres.enabled=true \
  --set dcgmServiceMonitor.enabled=true \
  --set prometheusRules.enabled=true
```

### 4. Alertmanager

Apply `alertmanager-config.yaml` to route alerts to the webhook.

### Resources created

| Resource | Name | Details |
|----------|------|---------|
| Namespace | `aiops-platform` | Isolated namespace |
| Deployment | `aiops-backend` | API on port 8000 |
| Deployment | `aiops-ui` | UI on port 80 → 5000 |
| Deployment | `aiops-postgres` | PostgreSQL (if enabled) |
| Service | `aiops-backend` | ClusterIP :8000 |
| Service | `aiops-ui` | ClusterIP :80 |
| Ingress | `aiops-ingress` | Routes `/` → UI, `/api` → backend |

Configure `ingress.host` in `k8s/ai-ops-platform-chart/values.yaml` (default: `aiops.app.local`).

API docs: `http://aiops.app.local/api/v1/docs`

---

## Alertmanager Integration

Add the webhook receiver from `deploy/alertmanager-webhook.yml`:

```yaml
receivers:
  - name: aiops-webhook
    webhook_configs:
      - url: http://aiops-backend.aiops.svc.cluster.local:8000/api/v1/alerts/webhook
        send_resolved: true
```

Route critical alerts to the AIOps webhook to automatically create and enrich incidents.
