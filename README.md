# AIOps Platform: WSL Environment Setup, System Documentation & Operational Runbooks

Welcome to the comprehensive documentation and operational guide for the **AIOps Platform**. This document provides step-by-step instructions for establishing a fully functional, air-gapped GPU-accelerated Kubernetes environment using **WSL2 (Windows Subsystem for Linux)**, details the platform architecture, offline artifact packaging (Docker images & Helm charts), storage preparations, and provides actionable runbooks for deployment, administration, and incident troubleshooting.

---

## Table of Contents

1. [System Architecture & Component Overview](#1-system-architecture--component-overview)
2. [WSL2 Environment Setup Guide](#2-wsl2-environment-setup-guide)
   - [2.1 Prerequisites](#21-prerequisites)
   - [2.2 WSL2 & Ubuntu Installation](#22-wsl2--ubuntu-installation)
   - [2.3 RKE2 Kubernetes Cluster Setup](#23-rke2-kubernetes-cluster-setup)
   - [2.4 NVIDIA Container Toolkit & GPU Passthrough](#24-nvidia-container-toolkit--gpu-passthrough)
   - [2.5 Local Storage Provisioner & Helm Setup](#25-local-storage-provisioner--helm-setup)
   - [2.6 Private OCI Registry (Zot) & Air-Gapped Image Import](#26-private-oci-registry-zot--air-gapped-image-import)
3. [Air-Gapped Artifact Packaging (Connected Host Setup)](#3-air-gapped-artifact-packaging-connected-host-setup)
   - [3.1 Docker Images List & Export Script](#31-docker-images-list--export-script)
   - [3.2 Helm Charts Pull & Bundle Script](#32-helm-charts-pull--bundle-script)
   - [3.3 Python Wheels Download for Offline PVC Hydration](#33-python-wheels-download-for-offline-pvc-hydration)
4. [Storage Preparation & Hydration Scripts](#4-storage-preparation--hydration-scripts)
   - [4.1 Python Dependencies PVC Initialization (`setup-deps-storage.sh`)](#41-python-dependencies-pvc-initialization-setup-deps-storagesh)
   - [4.2 Shared LLM Model Storage Hydration (`setup-model-storage.sh`)](#42-shared-llm-model-storage-hydration-setup-model-storagesh)
   - [4.3 Cross-Namespace Storage Migration (`pv-migrate`)](#43-cross-namespace-storage-migration-pv-migrate)
5. [Automated & Manifest-Based Stack Installations](#5-automated--manifest-based-stack-installations)
   - [5.1 Automated Offline Helm Stack Deployment (`install_helm_stack.sh`)](#51-automated-offline-helm-stack-deployment-install_helm_stacksh)
   - [5.2 Direct Manifest Installations (URL Fallbacks)](#52-direct-manifest-installations-url-fallbacks)
6. [Component Configuration & Credentials](#6-component-configuration--credentials)
   - [6.1 DevOps Core (Gogs, Zot, Jenkins, ArgoCD)](#61-devops-core-gogs-zot-jenkins-argocd)
   - [6.2 Observability Stack (Prometheus, Grafana, DCGM)](#62-observability-stack-prometheus-grafana-dcgm)
   - [6.3 AI Model Inference Engine (vLLM / Qwen)](#63-ai-model-inference-engine-vllm--qwen)
   - [6.4 AIOps Core Application (Backend & UI)](#64-aiops-core-application-backend--ui)
7. [Networking, Ingress & Access Management](#7-networking-ingress--access-management)
   - [7.1 Local Domain Hosts Mapping](#71-local-domain-hosts-mapping)
   - [7.2 Service Port-Forwarding Guide](#72-service-port-forwarding-guide)
8. [Operational Runbooks](#8-operational-runbooks)
   - [Runbook 01: RKE2 CNI & Traefik Network Recovery](#runbook-01-rke2-cni--traefik-network-recovery)
   - [Runbook 02: NVIDIA GPU Operator & Node Labeling Setup](#runbook-02-nvidia-gpu-operator--node-labeling-setup)
   - [Runbook 03: Gogs Git Server Initial Bootstrap & Webhook Registration](#runbook-03-gogs-git-server-initial-bootstrap--webhook-registration)
   - [Runbook 04: Air-Gapped Image Ingestion to Zot Registry](#runbook-04-air-gapped-image-ingestion-to-zot-registry)
   - [Runbook 05: Port-Forwarding Process Management](#runbook-05-port-forwarding-process-management)
   - [Runbook 06: Incident Remediation – CrashLoopBackOff & OOM Troubleshooting](#runbook-06-incident-remediation--crashloopbackoff--oom-troubleshooting)

---

## 1. System Architecture & Component Overview

The **AIOps Platform** is an enterprise-grade, autonomous Kubernetes observability and incident-remediation ecosystem. It ingests cluster alerts, telemetry, pod logs, and hardware metrics (GPU/CPU/RAM), analyzes them using a locally deployed LLM (vLLM Qwen 2.5), and provides intelligent root-cause analysis and automated remediation suggestions.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    WSL2 UBUNTU HOST                                    │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              RKE2 KUBERNETES CLUSTER                             │  │
│  │                                                                                  │  │
│  │  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐   ┌─────────────┐  │  │
│  │  │  DEVOPS CORE   │   │  OBSERVABILITY │   │   AIOPS APP    │   │  AI MODEL   │  │  │
│  │  │ ────────────── │   │ ────────────── │   │ ────────────── │   │ ─────────── │  │  │
│  │  │  • Gogs (Git)  │   │  • Prometheus  │   │  • FastMCP Api │   │  • vLLM Engine │  │  
│  │  │  • Zot Reg.    │   │  • Grafana     │   │  • Flask UI    │   │  • Qwen 2.5 │  │  │
│  │  │  • Jenkins CI  │   │  • DCGM GPU Ex.│   │  •             │   │    (3B/1.5B)│  │  │
│  │  │  • ArgoCD      │   │  • Alertmgr    │   │                │   │             │  │  │
│  │  └────────┬───────┘   └────────┬───────┘   └────────▲───────┘   └──────▲──────┘  │  │
│  │           │                    │                    │                  │         │  │ 
│  │           │ Webhooks           │ Metrics/Alerts     │ Ingest           │ API     │  │
│  │           └────────────────────┼────────────────────┼──────────────────┘         │  │
│  └────────────────────────────────┼────────────────────┼────────────────────────────┘  │
│                                   ▼                    │                               │
│                       ┌───────────────────────┐        │                               │
│                       │  Gogs Webhook Proxy   ├────────┘                               │
│                       └───────────────────────┘                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. WSL2 Environment Setup Guide

### 2.1 Prerequisites

- **Host OS**: Windows 10/11 or Windows Server with Hyper-V and Virtual Machine Platform enabled.
- **GPU**: NVIDIA GPU with up-to-date Windows NVIDIA Drivers (supporting WSL CUDA passthrough).
- **RAM/Storage**: Minimum 32 GB RAM recommended (16 GB for basic operations), 100 GB available disk space.

### 2.2 WSL2 & Ubuntu Installation

1. Open PowerShell as Administrator on Windows and execute:
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
2. Set up your standard non-root user when prompted.
3. Configure WSL mount propagation (Required for Kubernetes container storage drivers):
   Execute inside Ubuntu WSL:
   ```bash
   sudo mount --make-rshared /

   sudo bash -c 'cat <<EOF >> /etc/wsl.conf

   [boot]
   command="mount --make-rshared /"
   EOF'
   ```
4. Update package repositories:
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   sudo apt-get install -y iptables curl git jq build-essential unzip
   ```

### 2.3 RKE2 Kubernetes Cluster Setup

1. **Install RKE2 Server**:
   ```bash
   curl -sfL https://get.rke2.io | sudo sh -
   sudo systemctl enable rke2-server.service
   sudo systemctl start rke2-server.service
   ```
2. **Configure `kubectl` and Environment Variables**:
   Add RKE2 binary paths and CRI config to `~/.bashrc`:
   ```bash
   sudo ln -s /var/lib/rancher/rke2/bin/kubectl /usr/local/bin/kubectl
   sudo ln -s /var/lib/rancher/rke2/bin/crictl /usr/local/bin/crictl

   mkdir -p $HOME/.kube
   sudo cp /etc/rancher/rke2/rke2.yaml $HOME/.kube/config
   sudo chown $USER:$USER $HOME/.kube/config
   chmod 600 $HOME/.kube/config

   cat <<'EOF' >> ~/.bashrc
   export PATH=$PATH:/var/lib/rancher/rke2/bin
   export CRI_CONFIG_FILE=/var/lib/rancher/rke2/agent/etc/crictl.yaml
   export KUBECONFIG=$HOME/.kube/config

   alias k=kubectl
   alias crictl='sudo /var/lib/rancher/rke2/bin/crictl --runtime-endpoint unix:///run/k3s/containerd/containerd.sock'
   alias ctr='sudo /var/lib/rancher/rke2/bin/ctr --address /run/k3s/containerd/containerd.sock --namespace k8s.io'
   EOF

   source ~/.bashrc
   ```

3. **Configure `crictl.yaml`**:
   ```bash
   cat <<EOF | sudo tee /etc/crictl.yaml
   runtime-endpoint: unix:///run/k3s/containerd/containerd.sock
   image-endpoint: unix:///run/k3s/containerd/containerd.sock
   timeout: 10
   debug: false
   EOF
   ```

### 2.4 NVIDIA Container Toolkit & GPU Passthrough

1. **Install NVIDIA Container Toolkit inside WSL**:
   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
       sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
       sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   ```

2. **Generate CDI Spec & Configure ContainderD for RKE2**:
   ```bash
   sudo mkdir -p /etc/cdi
   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
   sudo nvidia-ctk runtime configure --runtime=containerd --config=/var/lib/rancher/rke2/agent/etc/containerd/config.toml
   sudo systemctl restart rke2-server
   ```

### 2.5 Local Storage Provisioner & Helm Setup

1. **Install Helm**:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
   ```

2. **Deploy Local Path Storage Provisioner**:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
   kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
   ```

### 2.6 Private OCI Registry (Zot) & Air-Gapped Image Import

1. **Configure Insecure / Private Registry Mirror in RKE2**:
   ```bash
   sudo mkdir -p /etc/rancher/rke2/
   cat <<EOF | sudo tee /etc/rancher/rke2/registries.yaml
   mirrors:
     "zot.local":
       endpoint:
         - "http://zot.local"
   configs:
     "zot.local":
       tls:
         insecure_skip_verify: true
   EOF

   sudo systemctl restart rke2-server
   ```

---

## 3. Air-Gapped Artifact Packaging (Connected Host Setup)

To bundle all required container images, helm charts, and python packages on an internet-connected workstation prior to air-gapped deployment:

### 3.1 Docker Images List & Export Script

On an internet-connected workstation with Docker installed, pull all required cluster images:

```bash
# Pull container images
docker pull vllm/vllm-openai:v0.6.3
docker pull python:3.12-slim
docker pull gogs/gogs:latest
docker pull docker:27-dind
docker pull ghcr.io/project-zot/zot-linux-amd64:latest
docker pull jenkins/jenkins:lts-jdk17
docker pull gcr.io/kaniko-project/executor:debug
docker pull rancher/local-path-provisioner:v0.0.30
docker pull nvcr.io/nvidia/gpu-operator:v26.7.0
docker pull nvcr.io/nvidia/k8s-device-plugin:v0.16.2
docker pull postgres:latest

# Save into single air-gapped tarball
docker save \
    vllm/vllm-openai:v0.6.3 \
    python:3.12-slim \
    gogs/gogs:latest \
    docker:27-dind \
    ghcr.io/project-zot/zot-linux-amd64:latest \
    jenkins/jenkins:lts-jdk17 \
    gcr.io/kaniko-project/executor:debug \
    rancher/local-path-provisioner:v0.0.30 \
    nvcr.io/nvidia/gpu-operator:v26.7.0 \
    nvcr.io/nvidia/k8s-device-plugin:v0.16.2 \
    postgres:latest \
    -o ./infra/aiops_images.tar
```

On Windows (PowerShell equivalent):
```powershell
docker save `
    vllm/vllm-openai:v0.6.3 `
    python:3.12-slim `
    gogs/gogs:latest `
    docker:27-dind `
    ghcr.io/project-zot/zot-linux-amd64:latest `
    jenkins/jenkins:lts-jdk17 `
    gcr.io/kaniko-project/executor:debug `
    rancher/local-path-provisioner:v0.0.30 `
    nvcr.io/nvidia/gpu-operator:v26.7.0 `
    nvcr.io/nvidia/k8s-device-plugin:v0.16.2 `
    postgres:latest `
    -o C:\Users\user\Desktop\TargilBait\infra\aiops_images.tar
```

### 3.2 Helm Charts Pull & Bundle Script

Download upstream Helm charts into `./helm-charts` and compress into `aiops_helm_charts.zip`:

**Bash (`air_gap_helm.sh`)**:
```bash
#!/usr/bin/env bash
set -euo pipefail

helm repo add gogs https://gogs.github.io/helm-charts
helm repo add jenkins https://charts.jenkins.io
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add gpu-operator https://nvidia.github.io/gpu-operator
helm repo add zot https://project-zot.github.io/helm-charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

mkdir -p ./helm-charts
helm pull jenkins/jenkins --destination ./helm-charts
helm pull argo/argo-cd --destination ./helm-charts
helm pull prometheus-community/kube-prometheus-stack --destination ./helm-charts
helm pull gpu-operator/gpu-operator --destination ./helm-charts
helm pull zot/zot --destination ./helm-charts
helm pull bitnami/postgresql --destination ./helm-charts

tar -czvf aiops_helm_charts.tar.gz ./helm-charts
```

**PowerShell (`air_gap_helm.ps1`)**:
```powershell
New-Item -ItemType Directory -Force -Path .\helm-charts | Out-Null

helm repo add jenkins https://charts.jenkins.io
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add gpu-operator https://nvidia.github.io/gpu-operator
helm repo add zot https://project-zot.github.io/helm-charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm pull jenkins/jenkins --destination .\helm-charts
helm pull argo/argo-cd --destination .\helm-charts
helm pull prometheus-community/kube-prometheus-stack --destination .\helm-charts
helm pull gpu-operator/gpu-operator --destination .\helm-charts
helm pull zot/zot --destination .\helm-charts
helm pull bitnami/postgresql --destination .\helm-charts

Compress-Archive -Path .\helm-charts\* -DestinationPath .\aiops_helm_charts.zip -Force
```

### 3.3 Python Wheels Download for Offline PVC Hydration

For the AIOps platform app backend dependencies:
```bash
pip download \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --implementation cp \
  --abi cp312 \
  --only-binary=:all: \
  -r all_requirements.txt \
  -d ./wheels
```

---

## 4. Storage Preparation & Hydration Scripts

### 4.1 Python Dependencies PVC Initialization (`setup-deps-storage.sh`)

This script creates the `python-deps-pvc` in the `aiops-platform` namespace, spins up a temporary helper pod, copies pre-downloaded wheel files, and installs them into `/pvc/site-packages`.

```bash
#!/bin/bash
set -e

NAMESPACE="aiops-platform"
PVC_NAME="python-deps-pvc"
PVC_SIZE="1Gi"
LOCAL_WHEELS_PATH="./wheels"

kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${PVC_NAME}
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: ${PVC_SIZE}
EOF

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: storage-initializer
  namespace: ${NAMESPACE}
spec:
  containers:
  - name: initializer
    image: python:3.12-slim
    command: ["sleep", "3600"]
    volumeMounts:
    - name: pvc-mount
      mountPath: /pvc
  volumes:
  - name: pvc-mount
    persistentVolumeClaim:
      claimName: ${PVC_NAME}
EOF

kubectl wait --for=condition=Ready pod/storage-initializer -n ${NAMESPACE} --timeout=60s

kubectl exec storage-initializer -n ${NAMESPACE} -- rm -rf /pvc/wheels
kubectl exec storage-initializer -n ${NAMESPACE} -- mkdir -p /pvc/wheels
kubectl cp "${LOCAL_WHEELS_PATH}/." ${NAMESPACE}/storage-initializer:/pvc/wheels/

kubectl exec storage-initializer -n ${NAMESPACE} -- sh -c "pip install --no-index --find-links=/pvc/wheels --target=/pvc/site-packages /pvc/wheels/*.whl"

kubectl delete pod storage-initializer -n ${NAMESPACE}
```

### 4.2 Shared LLM Model Storage Hydration (`setup-model-storage.sh`)

Populates the 20Gi `shared-model-pvc` in `devops-core` with model weights (e.g. `qwen2.5-3b-awq` or `qwen2.5-coder-1.5b-instruct`).

```bash
#!/bin/bash
set -e

NAMESPACE="devops-core"
PVC_NAME="shared-model-pvc"
PVC_SIZE="20Gi"
LOCAL_MODEL_PATH="./qwen2.5-3b-awq"
MODEL_NAME=$(basename "${LOCAL_MODEL_PATH}")

kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

if ! kubectl get pvc "${PVC_NAME}" -n "${NAMESPACE}" &>/dev/null; then
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${PVC_NAME}
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: ${PVC_SIZE}
EOF
fi

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: storage-initializer
  namespace: ${NAMESPACE}
spec:
  containers:
  - name: initializer
    image: alpine:latest
    command: ["sleep", "3600"]
    volumeMounts:
    - name: pvc-mount
      mountPath: /pvc
  volumes:
  - name: pvc-mount
    persistentVolumeClaim:
      claimName: ${PVC_NAME}
EOF

kubectl wait --for=condition=Ready pod/storage-initializer -n ${NAMESPACE} --timeout=60s

kubectl exec storage-initializer -n ${NAMESPACE} -- mkdir -p "/pvc/${MODEL_NAME}"
kubectl cp "${LOCAL_MODEL_PATH}/." ${NAMESPACE}/storage-initializer:"/pvc/${MODEL_NAME}/"

kubectl delete pod storage-initializer -n ${NAMESPACE} --ignore-not-found
```

### 4.3 Cross-Namespace Storage Migration (`pv-migrate`)

If moving persistent volumes between namespaces (e.g., from `aiops-platform` to `devops-core`):

```bash
pv-migrate migrate \
  --source-namespace aiops-platform \
  --dest-namespace devops-core \
  --ignore-mounted \
  python-deps-pvc python-deps-pvc
```

---

## 5. Automated & Manifest-Based Stack Installations

### 5.1 Automated Offline Helm Stack Deployment (`install_helm_stack.sh`)

This script extracts `aiops_helm_charts.zip` and deploys the core infrastructure components using offline `.tgz` archives:

```bash
#!/usr/bin/env bash
set -euo pipefail

CHARTS_DIR="./helm-charts"
ZIP_FILE="aiops_helm_charts.zip"

if [ ! -d "$CHARTS_DIR" ]; then
    if [ -f "$ZIP_FILE" ]; then
        echo "===> Unpacking $ZIP_FILE..."
        unzip "$ZIP_FILE" -d "$CHARTS_DIR"
    else
        echo "Error: Neither $CHARTS_DIR directory nor $ZIP_FILE exists."
        exit 1
    fi
fi

find_chart() {
    local pattern="$1"
    find "$CHARTS_DIR" -maxdepth 1 -name "${pattern}-*.tgz" | head -n 1
}

# 1. Deploy Gogs
if [ -f "$CHARTS_DIR/gogs.yaml" ]; then
    kubectl apply -f "$CHARTS_DIR/gogs.yaml"
fi

# 2. Deploy Jenkins
JENKINS_CHART=$(find_chart "jenkins")
if [ -n "$JENKINS_CHART" ]; then
    helm upgrade --install jenkins "$JENKINS_CHART" \
        --namespace devops-core \
        --create-namespace \
        --set controller.image.pullPolicy=IfNotPresent \
        --set controller.installPlugins[0]=kubernetes \
        --set controller.installPlugins[1]=workflow-aggregator \
        --set controller.installPlugins[2]=git \
        --set controller.installPlugins[3]=generic-webhook-trigger \
        --set controller.admin.username=admin \
        --set controller.admin.password=admin
fi

# 3. Deploy ArgoCD
ARGO_CHART=$(find_chart "argo-cd")
if [ -n "$ARGO_CHART" ]; then
    helm upgrade --install argo-cd "$ARGO_CHART" \
        --namespace argocd \
        --create-namespace \
        --set global.image.imagePullPolicy=IfNotPresent \
        --set server.insecure=true \
        --set server.extraArgs[0]="--insecure"
fi

# 4. Deploy Prometheus / Grafana Stack
PROM_CHART=$(find_chart "kube-prometheus-stack")
if [ -n "$PROM_CHART" ]; then
    helm upgrade --install prometheus "$PROM_CHART" \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.prometheusSpec.image.pullPolicy=IfNotPresent \
        --set-json 'alertmanager.config.inhibit_rules=[]'
fi

# 5. Deploy GPU Operator
GPU_CHART=$(find_chart "gpu-operator")
if [ -n "$GPU_CHART" ]; then
    helm upgrade --install gpu-operator "$GPU_CHART" \
      --namespace gpu-operator \
      --create-namespace \
      --version v26.7.0 \
      --set operator.version=v26.7.0 \
      --wait
fi

# 6. Deploy Zot Registry
GENERATED_HTPASSWD=$(htpasswd -Bbn "zot" "zot")
ZOT_CHART=$(find_chart "zot")
if [ -n "$ZOT_CHART" ]; then
    helm upgrade --install zot "$ZOT_CHART" \
        --namespace devops-core \
        --create-namespace \
        --set image.repository=ghcr.io/project-zot/zot-linux-amd64 \
        --set secretFiles.htpasswd="$GENERATED_HTPASSWD" \
        --set image.pullPolicy=IfNotPresent
fi
```

### 5.2 Direct Manifest Installations (URL Fallbacks)

If deploying connected or via direct Kubernetes manifests:

```bash
# 1. Namespace & DevOps Core (Gogs, Zot, Jenkins)
kubectl create namespace devops-core
kubectl apply -n devops-core -f https://raw.githubusercontent.com/gogs/gogs/main/docker/kubernetes/gogs.yaml
kubectl apply -n devops-core -f https://raw.githubusercontent.com/project-zot/zot/main/deploy/k8s/zot.yaml

kubectl create namespace jenkins
kubectl apply -n jenkins -f https://raw.githubusercontent.com/jenkins-infra/jenkins-on-kubernetes/main/jenkins-k8s-manifests.yaml

# 2. Monitoring & GPU DCGM Exporter
kubectl create namespace monitoring
kubectl apply --server-side -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/rbac/prometheus-operator/prometheus-operator-crd.yaml
kubectl apply -n monitoring -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/rbac/prometheus-operator/prometheus-operator-deployment.yaml
kubectl apply -n monitoring -f https://raw.githubusercontent.com/NVIDIA/dcgm-exporter/main/deployment/k8s/dcgm-exporter.yaml

# 3. NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# 4. NVIDIA Device Plugin
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.16.2/deployments/static/nvidia-device-plugin.yml
```

---

## 6. Component Configuration & Credentials

### 6.1 DevOps Core (Gogs, Zot, Jenkins, ArgoCD)

- **Namespace**: `devops-core` & `gogs` & `argocd`
- **Gogs Git Server**:
  - URL: `http://gogs.local` or `http://localhost:3000`
  - Admin User: `gogs` / `gogs`
  - Note: Enable `LOCAL_NETWORK_ALLOWLIST = *` in `/data/gogs/conf/app.ini`.
- **Zot OCI Registry**:
  - URL: `http://zot.local` or `http://localhost:5000`
  - Push endpoint: `zot.local/<repository>:<tag>`
- **Jenkins CI/CD**:
  - URL: `http://localhost:8085`
  - Secret retrieval: `kubectl get secret -n devops-core jenkins -o jsonpath='{.data}' | base64 --decode`
  - Agent Tunnel: `jenkins-agent.devops-core.svc.cluster.local:50000`
- **ArgoCD GitOps**:
  - URL: `http://argo.local` or `http://localhost:8080`
  - Admin Password Retrieval:
    ```bash
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
    ```

### 6.2 Observability Stack (Prometheus, Grafana, DCGM)

- **Namespace**: `monitoring`
- **Grafana**:
  - URL: `http://grafana.local` or `http://localhost:3001`
  - Admin Username: `admin`
  - Admin Password Retrieval:
    ```bash
    kubectl get secret --namespace monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode; echo
    ```
- **Prometheus**:
  - URL: `http://prometheus.local` or `http://localhost:9090`
- **DCGM Exporter**:
  - Scrapes GPU utilization, VRAM metrics, and hardware XID error codes.

### 6.3 AI Model Inference Engine (vLLM / Qwen)

- **Namespace**: `aiops`
- **Model**: `Qwen2.5-Coder-1.5B-Instruct` or `Qwen2.5-3B-AWQ`
- **Service Endpoint**: `http://aiops-llm-qwen.aiops.svc.cluster.local:8080`
- **Port Forward Target**: `http://localhost:8070`

### 6.4 AIOps Core Application (Backend & UI)

- **Backend (FastAPI)**: Evaluates incidents, invokes vector store (Qdrant RAG), queries Prometheus & K8s APIs.
- **UI (React/Flask)**: Provides interactive incident view and visual execution recommendations.

---

## 7. Networking, Ingress & Access Management

### 7.1 Local Domain Hosts Mapping

Add the following lines to your Windows host file (`C:\Windows\System32\drivers\etc\hosts`) or WSL `/etc/hosts`:

```text
127.0.0.1  zot.local
127.0.0.1  jenkins.local
127.0.0.1  argo.local
127.0.0.1  gogs.local
127.0.0.1  grafana.local
127.0.0.1  prometheus.local
127.0.0.1  webhook.local
127.0.0.1  aiops-llm.local
127.0.0.1  aiops.app.local
```

### 7.2 Service Port-Forwarding Guide

To map Kubernetes cluster services to local ports for external browser/CLI access:

```bash
# Clean up any stale port-forwards
pkill -f "kubectl port-forward"

# Launch background port-forwards
nohup kubectl port-forward -n gogs svc/gogs 3000:3000 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n devops-core svc/jenkins 8085:8080 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n argocd svc/argo-cd-argocd-server 8080:80 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n monitoring svc/prometheus-grafana 3001:80 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n devops-core svc/zot 5000:5000 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n aiops svc/aiops-llm-qwen 8070:8080 --address 0.0.0.0 >/dev/null 2>&1 &
```

---

## 8. Operational Runbooks

---

### Runbook 01: RKE2 CNI & Traefik Network Recovery

> [!WARNING]
> Perform this procedure if pods fail to get IP addresses, Canal CNI enters a CrashLoop, or Traefik Ingress fails to initialize after WSL restarts.

#### Symptoms
- Pods stuck in `ContainerCreating` or `Init:0/1`.
- Traefik ingress controller logs CNI network allocation timeouts.

#### Recovery Procedure
1. Execute the automated network recovery script (located in `infra/rke2-network-recovery.sh`):
   ```bash
   cd /mnt/c/Users/user/Desktop/TargilBait/infra
   chmod +x rke2-network-recovery.sh
   sudo ./rke2-network-recovery.sh
   ```

2. Manual Step-by-Step Fix:
   ```bash
   sudo systemctl stop rke2-server

   # Remove corrupted CNI network state
   sudo rm -rf /var/lib/cni/
   sudo rm -rf /var/lib/calico/
   sudo rm -rf /etc/cni/net.d/*

   sudo systemctl start rke2-server
   sudo mkdir -p /var/lib/calico

   # Force recreate CNI pods
   kubectl delete pod -n kube-system -l k8s-app=canal --force --grace-period=0
   kubectl delete pod -n kube-system -l app.kubernetes.io/name=rke2-traefik --force --grace-period=0
   ```

3. Verification:
   ```bash
   kubectl get pods -n kube-system -l k8s-app=canal
   ```
   Ensure all CNI pods are in `Running` status (1/1).

---

### Runbook 02: NVIDIA GPU Operator & Node Labeling Setup

> [!IMPORTANT]
> NVIDIA GPU operator requires node labels to detect GPU devices and allocate CUDA resources to vLLM.

#### Procedure
1. Identify node name:
   ```bash
   kubectl get nodes
   ```
2. Label node for GPU presence:
   ```bash
   kubectl label node <NODE_NAME> nvidia.com/gpu.present=true --overwrite
   ```
3. Deploy / Upgrade NVIDIA Device Plugin:
   ```bash
   helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
   helm repo update
   helm upgrade --install nvidia-device-plugin nvdp/k8s-device-plugin --namespace kube-system
   ```
4. Verification:
   ```bash
   kubectl get node <NODE_NAME> -o jsonpath='{.status.allocatable.nvidia\.com/gpu}'
   ```
   *Expected output: `>= 1`*

---

### Runbook 03: Gogs Git Server Initial Bootstrap & Webhook Registration

#### Initial Admin Setup
1. Exec into Gogs container:
   ```bash
   GOGS_POD=$(kubectl get pods -n gogs -l app=gogs -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -it $GOGS_POD -n gogs -c gogs -- /bin/sh
   ```
2. Create admin account CLI:
   ```sh
   su git
   ./gogs admin create-user --name gogs --password gogs --email admin@example.com --admin
   exit
   ```

#### Webhook Registration
To register pipeline webhook triggers to Gogs:
- Webhook Payload URL: `http://webhook.local/webhook?token=gogs-secret-token&job=aiops-LLM-deploy`
- Secret Token: `gogs-secret-token` (`f8558cd963f0001bcb579378e6a67a73e3bb8cb2`)

---

### Runbook 04: Air-Gapped Image Ingestion to Zot Registry

#### Steps
1. Load image tarball into ContainerD:
   ```bash
   ctr images import /mnt/c/Users/user/Desktop/TargilBait/infra/aiops_images.tar
   ```
2. Tag container images for `zot.local`:
   ```bash
   docker tag aiops-vllm-qwen:v0.6.3 zot.local/aiops-vllm-qwen:v0.6.3
   ```
3. Push to Zot Registry:
   ```bash
   docker push zot.local/aiops-vllm-qwen:v0.6.3
   ```
4. Verify image catalog:
   ```bash
   curl http://zot.local/v2/_catalog
   ```

---

### Runbook 05: Port-Forwarding Process Management

#### Check Active Port Forwards
```bash
ps aux | grep "kubectl port-forward"
```

#### Kill All Port Forwards
```bash
pkill -f "kubectl port-forward"
```

#### Relaunch Port-Forwarding Suite
```bash
nohup kubectl port-forward -n gogs svc/gogs 3000:3000 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n devops-core svc/jenkins 8085:8080 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n argocd svc/argo-cd-argocd-server 8080:80 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n monitoring svc/prometheus-grafana 3001:80 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n devops-core svc/zot 5000:5000 --address 0.0.0.0 >/dev/null 2>&1 &
nohup kubectl port-forward -n aiops svc/aiops-llm-qwen 8070:8080 --address 0.0.0.0 >/dev/null 2>&1 &
```

---

### Runbook 06: Incident Remediation – CrashLoopBackOff & OOM Troubleshooting

#### Scenario A: ImagePullBackOff / Erroneous Image Tag
1. Check events:
   ```bash
   kubectl get events --field-selector reason=Failed -n <NAMESPACE>
   ```
2. Verify image availability in Zot:
   ```bash
   curl http://zot.local/v2/<IMAGE_NAME>/tags/list
   ```
3. Update deployment image in Helm values or ArgoCD repository.

#### Scenario B: CUDA Out Of Memory (OOM) in vLLM / Model Pods
1. Check pod logs:
   ```bash
   kubectl logs -n aiops -l app=aiops-llm-qwen --tail=100
   ```
2. If `CUDA error: out of memory` is detected:
   - Decrease `gpu_memory_utilization` in deployment parameters (e.g., from `0.9` to `0.75`).
   - Reduce max token context size (`--max-model-len 4096`).
   - Restart model deployment:
     ```bash
     kubectl rollout restart deployment/aiops-llm-qwen -n aiops
     ```

---
*Documentation generated for AIOps Platform Setup & Operations.*
