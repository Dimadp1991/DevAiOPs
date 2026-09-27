# AIOps Platform — Cluster Testing Guide

Step-by-step guide to verify each service and scenario on your Kubernetes cluster.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Checklist](#quick-checklist)
- [1. Platform Smoke Test](#1-platform-smoke-test)
- [2. Service Connectivity Tests](#2-service-connectivity-tests)
- [3. API Scenario Tests](#3-api-scenario-tests)
- [4. Alertmanager End-to-End](#4-alertmanager-end-to-end)
- [5. Optional Components](#5-optional-components)
- [6. Troubleshooting](#6-troubleshooting)

---

## Prerequisites

### Hosts file

Add the Traefik ingress IP to your hosts file:

| OS | File |
|----|------|
| Linux / macOS | `/etc/hosts` |
| Windows | `C:\Windows\System32\drivers\etc\hosts` |

```
<INGRESS_IP>  aiops.app.local
```

Get the ingress IP:

```bash
kubectl get ingress -n aiops-platform
```

### Set API base URL

For all tests below, set one of:

```bash
# Via ingress (recommended)
export API=http://aiops.app.local/api/v1

# Via port-forward
kubectl port-forward -n aiops-platform svc/aiops-backend 8000:8000
export API=http://localhost:8000/api/v1
```

### Find real pod names

Replace `<REAL-POD-NAME>` and namespaces in examples with pods from your cluster:

```bash
kubectl get pods -n devops-core
kubectl get pods -n default
kubectl get pods -n gpu-operator
```

### Useful URLs

| Service | URL |
|---------|-----|
| UI | http://aiops.app.local |
| API health | http://aiops.app.local/api/v1/health |
| API docs | http://aiops.app.local/api/v1/docs |
| Prometheus | http://prometheus.local |
| Grafana | http://grafana.local |
| vLLM | http://aiops-llm.local |

---

## Quick Checklist

| # | Component | Command / action | Pass signal |
|---|-----------|------------------|-------------|
| 1 | Backend pod | `kubectl get pods -n aiops-platform` | `aiops-backend` Running |
| 2 | UI pod | same | `aiops-ui` Running |
| 3 | Python deps PVC | `kubectl get pvc -n aiops-platform` | `python-deps-pvc` Bound |
| 4 | API health | `curl $API/health` | `"status":"ok"` |
| 5 | API ready | `curl $API/ready` | `"status":"ready"` |
| 6 | Ingress / UI | open http://aiops.app.local | Dashboard loads |
| 7 | Prometheus | query from backend pod | `"status":"success"` |
| 8 | K8s API | simulate with real pod + RBAC | real pod status/logs |
| 9 | GPU / DCGM | simulate GPU alert | `telemetry.gpu` populated |
| 10 | vLLM agent | `/v1/models` + simulate | `agent_analysis` filled |
| 11 | Alertmanager | webhook POST | new incident created |
| 12 | Postgres | enable + health check | `"database":"postgresql"` |

---

## 1. Platform Smoke Test

### 1.1 Pods, services, ingress

```bash
kubectl get pods,svc,ingress -n aiops-platform
kubectl get pvc -n aiops-platform
```

**Expected:**

```
pod/aiops-backend-*     1/1  Running
pod/aiops-ui-*          1/1  Running
pvc/python-deps-pvc     Bound
service/aiops-backend   ClusterIP  8000
service/aiops-ui        ClusterIP  80
ingress/aiops-ingress   traefik    aiops.app.local
```

### 1.2 Backend logs

```bash
kubectl logs -n aiops-platform deploy/aiops-backend --tail=50
```

**Pass:** log line `AIOps backend started` with `mock=False`.

**Fail:** `ModuleNotFoundError` → run `./setup-deps-storage.sh` to populate `python-deps-pvc`.

### 1.3 UI logs

```bash
kubectl logs -n aiops-platform deploy/aiops-ui --tail=30
```

**Pass:** gunicorn workers started, no connection errors to backend.

---

## 2. Service Connectivity Tests

### 2.1 Backend API — health & ready

```bash
curl -s $API/health | jq .
```

**Expected response:**

```json
{
  "status": "ok",
  "service": "aiops-backend",
  "version": "2.0.0",
  "database": "memory",
  "mock_providers": false
}
```

```bash
curl -s $API/ready | jq .
```

**Expected:** `"status": "ready"`. With Postgres disabled, `"database": "memory_fallback"` is OK.

**In-cluster:**

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -s localhost:8000/api/v1/health
```

---

### 2.2 UI

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://aiops.app.local/
# Expected: 200

curl -s http://aiops.app.local/health
# Expected: {"status":"ok","service":"aiops-ui"}
```

---

### 2.3 UI → Backend connectivity

The UI pod must reach the backend service:

```bash
kubectl exec -n aiops-platform deploy/aiops-ui -- \
  python -c "import httpx; r=httpx.get('http://aiops-backend.aiops-platform.svc.cluster.local:8000/api/v1/incidents'); print(r.status_code)"
```

**Expected:** `200`

---

### 2.4 Prometheus

From the backend pod:

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -s "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/query?query=up"
```

**Pass:** JSON contains `"status":"success"`.

CPU metrics for a specific pod:

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -sG "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(container_cpu_usage_seconds_total{namespace="devops-core",container!=""}[5m]))'
```

Via ingress:

```bash
curl -sG "http://prometheus.local/api/v1/query" --data-urlencode 'query=up'
```

---

### 2.5 Kubernetes API

> **Note:** RBAC is disabled by default (`rbac.create: false`). Enable it first:

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set rbac.create=true
```

Test in-cluster K8s client from backend pod:

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  python -c "
from kubernetes import client, config
config.load_incluster_config()
api = client.CoreV1Api()
pods = api.list_namespaced_pod(namespace='devops-core', limit=3)
for p in pods.items:
    print(p.metadata.name, p.status.phase)
"
```

**Pass:** lists real pod names and phases.

**Fail:** `403 Forbidden` → RBAC not applied or ServiceAccount missing.

---

### 2.6 GPU / DCGM exporter

**Via Prometheus (preferred):**

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -sG "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/query" \
  --data-urlencode 'query=DCGM_FI_DEV_GPU_UTIL'
```

**Pass:** results with GPU utilization values.

**Fail (empty results):** enable DCGM ServiceMonitor:

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set dcgmServiceMonitor.enabled=true
```

**Direct DCGM exporter:**

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -s http://nvidia-dcgm-exporter.gpu-operator.svc.cluster.local:9400/metrics \
  | grep DCGM_FI_DEV_GPU_UTIL | head -3
```

---

### 2.7 vLLM / Qwen (LLM agent)

In-cluster:

```bash
kubectl exec -n aiops-platform deploy/aiops-backend -- \
  curl -s http://aiops-llm.devops-core.svc.cluster.local/v1/models
```

Via ingress:

```bash
curl -s http://aiops-llm.local/v1/models
```

**Pass:** returns model list including `qwen` (or your configured `LLM_MODEL`).

Minimal chat completion test:

```bash
curl -s http://aiops-llm.local/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role": "user", "content": "Say OK"}],
    "max_tokens": 10
  }' | jq .
```

---

### 2.8 Alertmanager webhook reachability

From the monitoring namespace:

```bash
kubectl run curl-test --rm -it --restart=Never -n monitoring --image=curlimages/curl -- \
  curl -s -w "\nHTTP %{http_code}\n" \
  -X POST http://aiops-backend.aiops-platform.svc.cluster.local:8000/api/v1/alerts/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical",
        "pod": "test-pod",
        "namespace": "default"
      },
      "annotations": {
        "summary": "Connectivity test alert"
      }
    }]
  }'
```

**Pass:** HTTP `200` and JSON incident returned.

---

## 3. API Scenario Tests

All endpoints are under `/api/v1`. Interactive testing: http://aiops.app.local/api/v1/docs

### API reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Liveness |
| `GET` | `/api/v1/ready` | Readiness |
| `GET` | `/api/v1/incidents` | List incidents |
| `GET` | `/api/v1/incidents/{id}` | Get full incident |
| `POST` | `/api/v1/incidents/{id}/enrich` | Re-run orchestrator |
| `PATCH` | `/api/v1/incidents/{id}/status?status=resolved` | Update status |
| `POST` | `/api/v1/alerts/simulate` | Manual alert trigger |
| `POST` | `/api/v1/alerts/webhook` | Alertmanager webhook |

---

### Scenario 1 — Pod crash loop (K8s + Prometheus)

Uses a **real pod** from your cluster for meaningful enrichment.

```bash
curl -s -X POST "$API/alerts/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "KubePodCrashLooping",
    "severity": "critical",
    "summary": "Pod <REAL-POD-NAME> is restarting repeatedly",
    "labels": {
      "pod": "<REAL-POD-NAME>",
      "namespace": "devops-core"
    }
  }' | jq '{
    incident_id,
    status,
    pod_status: .k8s_state.pod_status,
    restarts: .k8s_state.restarts,
    metrics: .telemetry.metrics,
    log_lines: (.telemetry.recent_logs | length),
    root_cause: .agent_analysis.root_cause
  }'
```

| Field | Working if |
|-------|------------|
| `k8s_state.pod_status` | Real phase (e.g. `Running`, `CrashLoopBackOff`), not `Unknown (mock)` |
| `telemetry.recent_logs` | Real log lines from the pod |
| `telemetry.metrics` | `cpu_usage_cores` and/or `memory_rss_bytes` present |
| `agent_analysis` | Root cause and remediation steps populated |
| `telemetry.gpu` | Empty or zero (non-GPU alert) |

---

### Scenario 2 — vLLM / GPU alert

Use a GPU workload pod (e.g. your vLLM Qwen deployment):

```bash
curl -s -X POST "$API/alerts/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPUHighUtilization",
    "severity": "critical",
    "summary": "vLLM GPU CUDA OOM on inference workload",
    "labels": {
      "pod": "<VLLM-POD-NAME>",
      "namespace": "devops-core",
      "app": "aiops-llm"
    }
  }' | jq '{
    incident_id,
    gpu: .telemetry.gpu,
    runbook: .knowledge_base.runbook,
    root_cause: .agent_analysis.root_cause,
    confidence: .agent_analysis.confidence
  }'
```

| Field | Working if |
|-------|------------|
| `telemetry.gpu.utilization_pct` | > 0 |
| `telemetry.gpu.vram_used_mb` | > 0 |
| `knowledge_base.runbook` | CUDA/vLLM runbook text |
| `agent_analysis` | GPU-related root cause (LLM or rule-based) |

---

### Scenario 3 — High CPU (no GPU enrichment)

```bash
curl -s -X POST "$API/alerts/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HighCpuUsage",
    "severity": "warning",
    "summary": "CPU usage above 90%",
    "labels": {
      "pod": "<REAL-POD-NAME>",
      "namespace": "default"
    }
  }' | jq '{
    incident_id,
    metrics: .telemetry.metrics,
    gpu_util: .telemetry.gpu.utilization_pct,
    root_cause: .agent_analysis.root_cause
  }'
```

**Pass:** metrics populated, GPU utilization `0` or absent in UI.

---

### Scenario 4 — Incident lifecycle

```bash
# 1. Create incident (save incident_id from output)
INCIDENT_ID=$(curl -s -X POST "$API/alerts/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestAlert",
    "severity": "warning",
    "summary": "Lifecycle test",
    "labels": {"pod": "<REAL-POD-NAME>", "namespace": "default"}
  }' | jq -r .incident_id)

echo "Incident: $INCIDENT_ID"

# 2. List incidents
curl -s "$API/incidents" | jq .

# 3. Get full detail
curl -s "$API/incidents/$INCIDENT_ID" | jq .

# 4. Re-enrich
curl -s -X POST "$API/incidents/$INCIDENT_ID/enrich" | jq .status

# 5. Resolve
curl -s -X PATCH "$API/incidents/$INCIDENT_ID/status?status=resolved" | jq .status
# Expected: "resolved"
```

---

### Scenario 5 — UI end-to-end

1. Run **Scenario 1** or **Scenario 2** above.
2. Open http://aiops.app.local
3. Verify the incident appears in the dashboard table.
4. Click the incident row.
5. Confirm sections: Alert, Service, Kubernetes State, Metrics, Logs, Agent Analysis.
6. If `agent_analysis` is missing, click **Run Orchestrator / Enrich Incident**.

---

### Scenario 6 — Alertmanager webhook payload

Simulates the exact payload Alertmanager sends:

```bash
curl -s -X POST "$API/alerts/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "firing",
    "receiver": "aiops-webhook",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "KubePodCrashLooping",
        "severity": "critical",
        "pod": "<REAL-POD-NAME>",
        "namespace": "devops-core"
      },
      "annotations": {
        "summary": "Pod <REAL-POD-NAME> is crash looping"
      },
      "startsAt": "2026-09-24T10:00:00.000Z"
    }]
  }' | jq '{incident_id, status, alert: .alert.name}'
```

---

## 4. Alertmanager End-to-End

### 4.1 Apply AlertmanagerConfig

```bash
kubectl apply -f deploy/alertmanager-config.yaml
kubectl get alertmanagerconfig -n monitoring
```

Webhook URL configured:

```
http://aiops-backend.aiops-platform.svc.cluster.local:8000/api/v1/alerts/webhook
```

### 4.2 Enable Prometheus alert rules

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set prometheusRules.enabled=true
```

Verify rules loaded in Prometheus: http://prometheus.local/rules

### 4.3 Fire a real alert

Options:

- Wait for a natural firing rule (e.g. `KubePodCrashLooping`, `GPUHighUtilization`)
- Use Prometheus UI → Alerts tab to see firing alerts
- Temporarily lower alert thresholds in `k8s/ai-ops-platform-chart/templates/prometheus-rules.yaml`

### 4.4 Confirm incident created

```bash
# Watch backend logs
kubectl logs -n aiops-platform deploy/aiops-backend -f

# List incidents
curl -s $API/incidents | jq .
```

### 4.5 Verify in Grafana

Open http://grafana.local → explore firing alerts and correlate with AIOps incidents.

---

## 5. Optional Components

### 5.1 PostgreSQL persistence

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set postgres.enabled=true

kubectl get pods -n aiops-platform -l app=aiops-postgres
curl -s $API/health | jq .database
# Expected: "postgresql"
```

Create an incident, restart backend, verify incident still exists:

```bash
kubectl rollout restart deployment/aiops-backend -n aiops-platform
kubectl rollout status deployment/aiops-backend -n aiops-platform
curl -s $API/incidents | jq .
```

---

### 5.2 RBAC for Kubernetes enrichment

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set rbac.create=true

kubectl get clusterrole,clusterrolebinding | grep aiops
```

Re-run **Scenario 1** — `k8s_state` should show real data.

---

### 5.3 DCGM ServiceMonitor

```bash
helm upgrade aiops-platform ./k8s/ai-ops-platform-chart -n aiops-platform \
  --reuse-values --set dcgmServiceMonitor.enabled=true

kubectl get servicemonitor -n monitoring | grep dcgm
```

Wait ~30s, then re-run **Section 2.6** Prometheus DCGM query.

---

### 5.4 Python deps PVC (slim images)

Required when `pythonDeps.enabled: true` (default).

```bash
# Download wheels
pip download -r all_requirements.txt -d ./wheels

# Populate PVC
chmod +x setup-deps-storage.sh
./setup-deps-storage.sh

# Verify
kubectl get pvc python-deps-pvc -n aiops-platform
```

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Backend `CrashLoopBackOff`, `ModuleNotFoundError` | Python wheels not on PVC | Run `./setup-deps-storage.sh` |
| `k8s_state.pod_status` = `Unknown (mock)` | RBAC disabled or wrong pod name | `--set rbac.create=true`, use real pod in labels |
| `telemetry.metrics` empty | Prometheus unreachable or wrong namespace/pod | Test PromQL from backend pod (Section 2.4) |
| `telemetry.gpu` always empty | DCGM not scraped by Prometheus | `--set dcgmServiceMonitor.enabled=true` |
| `agent_analysis` generic / empty | LLM unreachable or wrong model name | Test `/v1/models`, check `llmApiUrl` / `llmModel` in values |
| UI shows no incidents but API has data | UI cannot reach backend | Check `ui.env.apiUrl` in Helm values |
| `curl aiops.app.local` fails | Hosts / ingress not configured | Add hosts entry, check Traefik ingress |
| Alertmanager fires but no incident | Webhook config not picked up | Verify `AlertmanagerConfig` labels match Prometheus operator |
| Incidents lost after restart | Postgres disabled (in-memory store) | `--set postgres.enabled=true` |
| `403` from K8s API in backend | Missing RBAC | `--set rbac.create=true` and restart backend |

### Debug commands

```bash
# All env vars on backend
kubectl exec -n aiops-platform deploy/aiops-backend -- env | sort

# Describe backend pod events
kubectl describe pod -n aiops-platform -l app=aiops-backend

# Helm values in use
helm get values aiops-platform -n aiops-platform

# Backend live logs during simulate
kubectl logs -n aiops-platform deploy/aiops-backend -f
```

---

## Recommended test order

1. **Smoke** — pods, PVC, `/api/v1/health`, `/api/v1/ready`
2. **Connectivity** — Prometheus, K8s (with RBAC), DCGM, vLLM
3. **Scenarios** — simulate pod crash, GPU, CPU alerts
4. **UI** — dashboard and incident detail page
5. **Alertmanager** — webhook + real firing alert
6. **Optional** — Postgres persistence, DCGM ServiceMonitor, Prometheus rules

---

## Local development (docker-compose)

For offline testing without a cluster:

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000/api/v1/health |
| API docs | http://localhost:8000/api/v1/docs |
| UI | http://localhost:5000 |

Uses `Dockerfile.dev` with dependencies baked in (`USE_MOCK_PROVIDERS=true`).

```bash
curl -s -X POST http://localhost:8000/api/v1/alerts/simulate \
  -H "Content-Type: application/json" \
  -d '{"name":"TestAlert","severity":"warning","summary":"Local test","labels":{}}'
```
