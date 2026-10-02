# AIOps Platform: WSL Environment Setup, System Documentation & Operational Runbooks

Welcome to the comprehensive documentation and operational guide for the **AIOps Platform**. This document provides step-by-step instructions for establishing a fully functional, air-gapped GPU-accelerated Kubernetes environment using **WSL2 (Windows Subsystem for Linux)**, details the platform architecture, offline artifact packaging (Docker images & Helm charts), storage preparations, the automated GitOps CI/CD pipeline, and provides actionable runbooks for deployment, administration, and incident troubleshooting.

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
   - [3.0 End-to-End Air-Gap Workflow](#30-end-to-end-air-gap-workflow)
   - [3.1 Docker Images List & Export Script](#31-docker-images-list--export-script)
   - [3.2 Helm Charts Pull & Bundle Script](#32-helm-charts-pull--bundle-script)
   - [3.3 Python Wheels Download for Offline PVC Hydration](#33-python-wheels-download-for-offline-pvc-hydration)
   - [3.4 Bulk Tag & Push to Zot (`push_all_images_to_zotRegistry.ps1`)](#34-bulk-tag--push-to-zot-push_all_images_to_zotregistryps1)
   - [3.5 Custom Jenkins DinD Agent Image (`infra/custom_dind`)](#35-custom-jenkins-dind-agent-image-infracustom_dind)
4. [Storage Preparation & Hydration Scripts](#4-storage-preparation--hydration-scripts)
   - [4.1 Python Dependencies PVC Initialization (`setup-deps-storage.sh`)](#41-python-dependencies-pvc-initialization-setup-deps-storagesh)
   - [4.2 Shared LLM Model Storage Hydration (`setup-model-storage.sh`)](#42-shared-llm-model-storage-hydration-setup-model-storagesh)
   - [4.3 Cross-Namespace Storage Migration (`pv-migrate`)](#43-cross-namespace-storage-migration-pv-migrate)
5. [Automated & Manifest-Based Stack Installations](#5-automated--manifest-based-stack-installations)
   - [5.1 Automated Offline Helm Stack Deployment (`install_helm_stack.sh`)](#51-automated-offline-helm-stack-deployment-install_helm_stacksh)
   - [5.2 GPU-Only Helm Install (`install_helm_only_gpu.sh`)](#52-gpu-only-helm-install-install_helm_only_gpush)
   - [5.3 Ingress & ArgoCD Application Manifests](#53-ingress--argocd-application-manifests)
   - [5.4 Direct Manifest Installations (URL Fallbacks)](#54-direct-manifest-installations-url-fallbacks)
6. [CI/CD & GitOps Automated Deployment Flow](#6-cicd--gitops-automated-deployment-flow)
   - [6.1 End-to-End Pipeline Architecture](#61-end-to-end-pipeline-architecture)
   - [6.2 Stage 1: Developer Git PR & Gogs Event Notification](#62-stage-1-developer-git-pr--gogs-event-notification)
   - [6.3 Stage 2: Webhook Gateway Handler (`webhook_gogs.py`)](#63-stage-2-webhook-gateway-handler-webhook_gogspy)
   - [6.4 Stage 3: Jenkins Dynamic Kubernetes Build Runner](#64-stage-3-jenkins-dynamic-kubernetes-build-runner)
   - [6.5 Stage 4: Docker Image Containerization & Push to Zot](#65-stage-4-docker-image-containerization--push-to-zot)
   - [6.6 Stage 5: Helm Chart Manifest Update & Git Auto-Commit](#66-stage-5-helm-chart-manifest-update--git-auto-commit)
   - [6.7 Stage 6: ArgoCD GitOps Cluster Synchronization](#67-stage-6-argocd-gitops-cluster-synchronization)
7. [Component Configuration & Credentials](#7-component-configuration--credentials)
   - [7.1 DevOps Core (Gogs, Zot, Jenkins, ArgoCD)](#71-devops-core-gogs-zot-jenkins-argocd)
   - [7.2 Observability Stack (Prometheus, Grafana, DCGM)](#72-observability-stack-prometheus-grafana-dcgm)
   - [7.3 AI Model Inference Engine (vLLM / Qwen)](#73-ai-model-inference-engine-vllm--qwen)
   - [7.4 AIOps Core Application (Backend & UI)](#74-aiops-core-application-backend--ui)
8. [Networking, Ingress & Access Management](#8-networking-ingress--access-management)
   - [8.1 Local Domain Hosts Mapping](#81-local-domain-hosts-mapping)
   - [8.2 Service Port-Forwarding Guide](#82-service-port-forwarding-guide)
9. [Operational Runbooks](#9-operational-runbooks)
   - [Runbook 01: RKE2 CNI & Traefik Network Recovery](#runbook-01-rke2-cni--traefik-network-recovery)
   - [Runbook 02: NVIDIA GPU Operator & Node Labeling Setup](#runbook-02-nvidia-gpu-operator--node-labeling-setup)
   - [Runbook 03: Gogs Git Server Initial Bootstrap & Webhook Registration](#runbook-03-gogs-git-server-initial-bootstrap--webhook-registration)
   - [Runbook 04: Air-Gapped Image Ingestion to Zot Registry](#runbook-04-air-gapped-image-ingestion-to-zot-registry)
   - [Runbook 05: Port-Forwarding Process Management](#runbook-05-port-forwarding-process-management)
   - [Runbook 06: Incident Remediation – CrashLoopBackOff & OOM Troubleshooting](#runbook-06-incident-remediation--crashloopbackoff--oom-troubleshooting)
   - [Runbook 07: Testing & Validating the GitOps Deployment Loop (PR -> Webhook -> Jenkins -> ArgoCD)](#runbook-07-testing--validating-the-gitops-deployment-loop-pr---webhook---jenkins---argocd)
10. [Appendix: Repository Script & Artifact Inventory](#appendix-repository-script--artifact-inventory)

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
│  │  │  • Gogs (Git)  │   │  • Prometheus  │   │  • FastApi     │   │  • vLLM Engine │  │  
│  │  │  • Zot Reg.    │   │  • Grafana     │   │  • Flask UI    │   │  • Qwen 2.5 │  │  │
│  │  │  • Jenkins CI  │   │  • DCGM GPU Ex.│   │  •             │   │    (3B/1.5B)│  │  │
│  │  │  • ArgoCD      │   │  • Alertmgr    │   │                │   │             │  │  │
│  │  └────────┬───────┘   └────────┬───────┘   └────────▲───────┘   └──────▲──────┘  │  │
│  │           │                    │                    │                  │     │   │  │
│  │           │ Webhooks           │ Metrics/Alerts     │ Ingest           │ API │   │  │
│  │           └────────────────────┼────────────────────┼──────────────────┘     │   │  │
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

#### Hardware & host OS

- **Host OS**: Windows 10/11 or Windows Server with **Hyper-V** and **Virtual Machine Platform** enabled (`wsl --install` enables these on supported builds).
- **GPU**: NVIDIA GPU with current **Windows** NVIDIA drivers (WSL CUDA passthrough).
- **RAM / disk**: 32 GB RAM recommended (16 GB minimum for basic ops); **100 GB+** free for images, Helm charts, and model weights.

#### Connected workstation (pull & package artifacts)

Use a machine with internet access **before** moving tarballs into the air-gapped WSL cluster:

| Tool | Purpose |
|------|---------|
| **Docker Desktop** (Windows) or Docker Engine (Linux) | `docker pull`, `docker save`, tag/push to `zot.local` |
| **Helm 3** | Run `infra/air_gap_helm.ps1` or `infra/air_gap_helm.sh` |
| **PowerShell 5+** | `infra/push_all_images_to_zotRegistry.ps1`, `infra/air_gap_helm.ps1` |
| **Python 3.12 + pip** | `pip download` wheels for offline PVC hydration (section 3.3) |

**Docker Desktop — insecure registry (required for `zot.local` push from Windows):**

1. Open **Settings → Docker Engine**.
2. Add `zot.local` (and `localhost:5000` if you port-forward Zot) under `insecure-registries`:

```json
{
  "insecure-registries": [
    "zot.local",
    "localhost:5000"
  ]
}
```

3. Apply & restart Docker Desktop.
4. Map `zot.local` in `C:\Windows\System32\drivers\etc\hosts` to `127.0.0.1` and keep Zot reachable (ingress or `kubectl port-forward`; see section 8).

#### WSL2 cluster host (RKE2 target)

Install inside **Ubuntu 24.04** on WSL2 (sections 2.2–2.6):

| Package / tool | Install command / notes |
|----------------|-------------------------|
| Base utilities | `sudo apt-get install -y iptables curl git jq build-essential unzip` |
| **apache2-utils** | `sudo apt-get install -y apache2-utils` — provides `htpasswd` for Zot Helm install in `install_helm_stack.sh` |
| **Helm 3** | Section 2.5 |
| **RKE2** | Section 2.3 — `kubectl`, `crictl`, `ctr` aliases |
| **NVIDIA Container Toolkit** | Section 2.4; alternate step list in `infra/install_nvidia_on_wsl` |
| **Optional: pv-migrate** | Cross-namespace PVC copy (section 4.3) |

**Working directory (Windows repo mounted in WSL):**

```bash
cd /mnt/c/Users/user/Desktop/TargilBait/infra
```

> **Before going air-gapped:** run storage hydration in **each application repo** (`ai-ops-platform-app/setup-deps-storage.sh`, `ai-ops-llm-model/setup-model-storage.sh`) while you still have network or pre-staged artifacts.

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

### 3.0 End-to-End Air-Gap Workflow

Typical sequence (matches `infra/installation.txt`):

1. **Connected host:** pull images → `docker save` to `infra/aiops_images.tar` (section 3.1) **or** push directly to Zot with `infra/push_all_images_to_zotRegistry.ps1` (section 3.4) when the cluster/registry is already up.
2. **Connected host:** `.\infra\air_gap_helm.ps1` → `infra/aiops_helm_charts.zip` and bundled `infra/helm-charts/gogs.yaml`.
3. **Connected host:** download Python wheels for the platform app (section 3.3).
4. **WSL / RKE2:** import tarball into containerd if not using Zot-only flow:
   ```bash
   cd /mnt/c/Users/user/Desktop/TargilBait/infra
   sudo ctr --address /run/k3s/containerd/containerd.sock --namespace k8s.io images import aiops_images.tar
   ```
5. **WSL:** `./install_helm_stack.sh` (from `infra/`, with charts zip present).
6. **Windows or WSL:** tag & push any remaining images to `zot.local` (section 3.4 / Runbook 04).
7. **WSL:** build & push `python-git-dind:27-pg-dind` (section 3.5) before first Jenkins pipeline run.
8. **WSL:** `kubectl apply -f all-ingress.yaml` and `kubectl apply -f argocd/` (section 5.3).
9. Hydrate PVCs (section 4) and register Gogs webhooks (Runbook 03).

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
docker pull postgres:16-alpine
docker pull python:3.11-slim

# Save into single air-gapped tarball
docker save \
    vllm/vllm-openai:v0.6.3 \
    python:3.12-slim \
    python:3.11-slim \
    gogs/gogs:latest \
    docker:27-dind \
    ghcr.io/project-zot/zot-linux-amd64:latest \
    jenkins/jenkins:lts-jdk17 \
    gcr.io/kaniko-project/executor:debug \
    rancher/local-path-provisioner:v0.0.30 \
    nvcr.io/nvidia/gpu-operator:v26.7.0 \
    nvcr.io/nvidia/k8s-device-plugin:v0.16.2 \
    postgres:16-alpine \
    -o ./infra/aiops_images.tar
```

> **Full stack images** (Argo CD, Prometheus, Grafana, GPU operator validators, etc.) are listed in `infra/push_all_images_to_zotRegistry.ps1`. After Helm installs pull many sub-images, use that script on a connected host to mirror everything into Zot. Supplementary list: `infra/required_images.txt` (Argo CD–related pulls).

On Windows (PowerShell equivalent):
```powershell
$images = @(
    "vllm/vllm-openai:v0.6.3",
    "python:3.12-slim",
    "python:3.11-slim",
    "postgres:16-alpine",
    "gogs/gogs:latest",
    "docker:27-dind",
    "ghcr.io/project-zot/zot-linux-amd64:latest",
    "jenkins/jenkins:lts-jdk17",
    "gcr.io/kaniko-project/executor:debug",
    "rancher/local-path-provisioner:v0.0.30",
    "nvcr.io/nvidia/gpu-operator:v26.7.0",
    "nvcr.io/nvidia/k8s-device-plugin:v0.16.2"
)
foreach ($img in $images) { docker pull $img }

docker save `
    vllm/vllm-openai:v0.6.3 `
    gogs/gogs:latest `
    ghcr.io/project-zot/zot-linux-amd64:latest `
    jenkins/jenkins:lts-jdk17 `
    gcr.io/kaniko-project/executor:debug `
    rancher/local-path-provisioner:v0.0.30 `
    nvcr.io/nvidia/gpu-operator:v26.7.0 `
    nvcr.io/nvidia/k8s-device-plugin:v0.16.2 `
    postgres:16-alpine `
    python:3.12-slim `
    python:3.11-slim `
    docker:27-dind `
    -o "C:\Users\user\Desktop\TargilBait\infra\aiops_images.tar"
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

> **Note:** `install_helm_stack.sh` deploys Gogs from the **raw manifest** `infra/helm-charts/gogs.yaml` (bundled in this repo), not from the Gogs Helm chart tarball. The bash script `air_gap_helm.sh` also pulls `gpu-operator` and `zot` charts; keep `air_gap_helm.ps1` in sync (add `helm repo add zot` and `helm pull zot/zot` if missing). Copy or vendor `gogs.yaml` into `helm-charts/` before running the stack installer offline.

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

### 3.4 Bulk Tag & Push to Zot (`push_all_images_to_zotRegistry.ps1`)

Script path: **`infra/push_all_images_to_zotRegistry.ps1`**.

Use when Zot is running and reachable from Docker Desktop (hosts file + insecure registry from section 2.1). The script logs in (default user/password **`zot` / `zot`**, matching `htpasswd` in `install_helm_stack.sh`), pulls each upstream image, retags as `zot.local/<original-path>`, and pushes.

```powershell
cd C:\Users\user\Desktop\TargilBait\infra
# Ensure Zot is reachable, e.g. port-forward or ingress:
# kubectl port-forward -n devops-core svc/zot 5000:5000 --address 0.0.0.0
.\push_all_images_to_zotRegistry.ps1
```

Edit `$Registry`, `$ZotUser`, and `$ZotPass` at the top of the script if you use a NodePort IP or different credentials.

**Verify:**

```bash
curl -u zot:zot http://zot.local/v2/_catalog
# or
curl http://localhost:5000/v2/_catalog
```

**Delete a bad manifest (if needed):**

```bash
curl -X DELETE "http://zot.local/v2/<repo>/manifests/sha256:<digest>"
```

### 3.5 Custom Jenkins DinD Agent Image (`infra/custom_dind`)

Jenkins Kubernetes agents in each repo’s `Jenkinsfile` use **`zot.local/python-git-dind:27-pg-dind`**. That image is not on Docker Hub; build it after `docker:27-dind` exists in Zot:

```bash
cd /mnt/c/Users/user/Desktop/TargilBait/infra/custom_dind
docker build -t python-git-dind:27-pg-dind .
docker tag python-git-dind:27-pg-dind zot.local/python-git-dind:27-pg-dind
docker login zot.local -u zot -p zot
docker push zot.local/python-git-dind:27-pg-dind
```

The Dockerfile extends `zot.local/docker:27-dind` with Python 3, git, bash, and PyYAML for pipeline steps that patch Helm `values.yaml`.

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

### 5.2 GPU-Only Helm Install (`install_helm_only_gpu.sh`)

Partial reinstall when only the **NVIDIA GPU Operator** stack needs to be applied (uses the same `helm-charts/` / `aiops_helm_charts.zip` layout as `install_helm_stack.sh`):

```bash
cd /mnt/c/Users/user/Desktop/TargilBait/infra
chmod +x install_helm_only_gpu.sh
./install_helm_only_gpu.sh
```

This chart install sets `nfd.enabled=false`, `driver.enabled=false`, `toolkit.enabled=false`, and `dcgmExporter.enabled=true` (WSL-friendly; drivers/toolkit run on the host).

### 5.3 Ingress & ArgoCD Application Manifests

After core Helm releases are healthy:

```bash
cd /mnt/c/Users/user/Desktop/TargilBait/infra
kubectl apply -f all-ingress.yaml
kubectl apply -f argocd/
```

| File | Purpose |
|------|---------|
| `all-ingress.yaml` | Local hostnames (`gogs.local`, `jenkins.local`, `zot.local`, `argo.local`, `grafana.local`, `prometheus.local`, `webhook.local`, `aiops-llm.local`, `aiops.app.local`) |
| `argocd/argocd-app-aiops-platform.yaml` | GitOps app for platform backend/UI |
| `argocd/argocd-app-gogs-webhook.yaml` | Webhook proxy deployment |
| `argocd/argocd-app-vllm.yaml` | vLLM / Qwen inference |
| `argocd/argocd-app-custom-dcgm.yaml` | Custom DCGM exporter (optional path) |

**Zot PVC helper:** `infra/seed-zot.sh` attaches an Alpine pod to `zot-storage-pvc` for manual registry data seeding or inspection (`/var/lib/registry`).

### 5.4 Direct Manifest Installations (URL Fallbacks)

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

## 6. CI/CD & GitOps Automated Deployment Flow

### 6.1 End-to-End Pipeline Architecture

The platform features a fully automated GitOps deployment pipeline:

```
[ Developer ]
      │
      │ 1. Git PR Merge / Push
      ▼
┌───────────┐         2. Webhook HTTP POST           ┌─────────────────────┐
│   Gogs    ├───────────────────────────────────────►│  Gogs Webhook Proxy │
│ (Git Repo)│                                        │  (Flask / Port 9000)│
└─────▲─────┘                                        └──────────┬──────────┘
      │                                                         │
      │ 6. Git Push Updated values.yaml                         │ 3. Trigger Job API
      │    (tag: v1.0.0-${BUILD_NUMBER})                        ▼
      │                                              ┌─────────────────────┐
      │                                              │ Jenkins CI Pipeline │
      │                                              │ (K8s DinD Runner)   │
      │                                              └──────────┬──────────┘
      │                                                         │
      │                                                         │ 4. Docker Build & Push
      │                                                         ▼
      │                                              ┌─────────────────────┐
      │                                              │    Zot OCI Registry │
      │                                              │     (zot.local)     │
      │                                              └─────────────────────┘
      │ 7. Detects Git Manifest Change
      ▼
┌───────────┐         8. Sync State / Rolling Update ┌─────────────────────┐
│  ArgoCD   ├───────────────────────────────────────►│ RKE2 K8s Cluster    │
│  GitOps   │                                        │ (App Pods Updated)  │
└───────────┘                                        └─────────────────────┘
```

### 6.2 Stage 1: Developer Git PR & Gogs Event Notification

When a developer opens or merges a Pull Request (or pushes code directly to `main`), Gogs emits a JSON webhook payload to the configured endpoint:
- **Event Header**: `X-Gogs-Event: pull_request`
- **Payload Data**: Contains `action: closed`, `pull_request.merged: true`, and branch references.

### 6.3 Stage 2: Webhook Gateway Handler (`webhook_gogs.py`)

The lightweight Flask Webhook service (`gogs_webhook/webhook_gogs.py`) validates incoming requests and proxies triggers to Jenkins:
- **Security Check**: Validates query parameter `?token=gogs-secret-token`.
- **Target Job Identification**: Extracts target pipeline from `?job=aiops-deploy-platform-app`.
- **Merge Evaluation**: Ensures the event represents a merged PR (`merged == True` or `action in ["closed", "merged"]`).
- **Jenkins Authentication**: Retrieves CSRF Crumb (`/crumbIssuer/api/json`) using basic auth (`admin:admin`) and issues an HTTP POST to `http://jenkins.local/job/<job_name>/build`.

### 6.4 Stage 3: Jenkins Dynamic Kubernetes Build Runner

Jenkins spawns an ephemeral build agent pod inside the cluster using the Kubernetes plugin:
- **Pod Spec**: Contains two sidecar containers:
  1. `tools` (`python:3.12-slim`): Handles git configuration, YAML parsing, and credential manipulation.
  2. `dind` (`docker:27-dind`): Privileged DinD (Docker-in-Docker) container for docker daemon execution.

### 6.5 Stage 4: Docker Image Containerization & Push to Zot

Inside the `dind` container, Jenkins builds and tags application microservices:
```bash
# Build Backend container image
cd backend
docker build -t zot.local/aiops-backend:v1.0.0-${BUILD_NUMBER} .
docker push zot.local/aiops-backend:v1.0.0-${BUILD_NUMBER}

# Build UI container image
cd ui
docker build -t zot.local/aiops-ui:v1.0.0-${BUILD_NUMBER} .
docker push zot.local/aiops-ui:v1.0.0-${BUILD_NUMBER}
```

### 6.6 Stage 5: Helm Chart Manifest Update & Git Auto-Commit

Inside the `tools` container, Jenkins programmatically updates the image tags in the application's Helm chart `values.yaml` and commits back to Gogs:

```python
import yaml

path = 'k8s/ai-ops-platform-chart/values.yaml'
with open(path, 'r') as f:
    data = yaml.safe_load(f)

if 'backend' in data and 'image' in data['backend']:
    data['backend']['image']['tag'] = f'v1.0.0-{BUILD_NUMBER}'
if 'ui' in data and 'image' in data['ui']:
    data['ui']['image']['tag'] = f'v1.0.0-{BUILD_NUMBER}'

with open(path, 'w') as f:
    yaml.safe_dump(data, f, sort_keys=False)
```

Jenkins then commits and pushes the updated `values.yaml` back to Gogs:
```bash
git config user.name "Jenkins CI"
git config user.email "jenkins@aiops.local"
git add k8s/ai-ops-platform-chart/values.yaml
git commit -m "CI: Update image tags to build ${BUILD_NUMBER}"
git push origin HEAD:main
```

### 6.7 Stage 6: ArgoCD GitOps Cluster Synchronization

1. **Detection**: ArgoCD monitors the Gogs git repository (`http://gogs.local/gogs/ai-ops-platform-app.git`).
2. **Reconciliation**: ArgoCD detects that `values.yaml` has changed to tag `v1.0.0-${BUILD_NUMBER}`.
3. **Automated Rollout**: ArgoCD applies the updated Helm chart onto the RKE2 Kubernetes cluster, triggering a zero-downtime rolling update for `aiops-backend` and `aiops-ui` pods.

---

## 7. Component Configuration & Credentials

### 7.1 DevOps Core (Gogs, Zot, Jenkins, ArgoCD)

- **Namespace**: `devops-core` & `gogs` & `argocd`
- **Gogs Git Server**:
  - URL: `http://gogs.local` or `http://localhost:3000`
  - Admin User: `gogs` / `gogs`
  - Note: Enable `LOCAL_NETWORK_ALLOWLIST = *` in `/data/gogs/conf/app.ini`.
- **Zot OCI Registry**:
  - URL: `http://zot.local` or `http://localhost:5000`
  - Push endpoint: `zot.local/<repository>:<tag>`
  - Default credentials (from `install_helm_stack.sh` / `push_all_images_to_zotRegistry.ps1`): user **`zot`**, password **`zot`**
  - Bulk mirror script: `infra/push_all_images_to_zotRegistry.ps1`
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

### 7.2 Observability Stack (Prometheus, Grafana, DCGM)

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

### 7.3 AI Model Inference Engine (vLLM / Qwen)

- **Namespace**: `aiops`
- **Model**: `Qwen2.5-Coder-1.5B-Instruct` or `Qwen2.5-3B-AWQ`
- **Service Endpoint**: `http://aiops-llm-qwen.aiops.svc.cluster.local:8080`
- **Port Forward Target**: `http://localhost:8070`

### 7.4 AIOps Core Application (Backend & UI)

- **Backend (FastAPI)**: Evaluates incidents, invokes vector store (Qdrant RAG), queries Prometheus & K8s APIs.
- **UI (React/Flask)**: Provides interactive incident view and visual execution recommendations.

---

## 8. Networking, Ingress & Access Management

### 8.1 Local Domain Hosts Mapping

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

### 8.2 Service Port-Forwarding Guide

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

## 9. Operational Runbooks

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

#### Gogs local network allowlist (webhooks from cluster)

If Gogs rejects webhook callbacks from private IPs, edit `/data/gogs/conf/app.ini` inside the Gogs pod:

```ini
[security]
LOCAL_NETWORK_ALLOWLIST = *
```

Restart the Gogs pod after changing configuration.

#### Webhook Registration
To register pipeline webhook triggers to Gogs:
- Webhook Payload URL: `http://webhook.local/webhook?token=gogs-secret-token&job=aiops-deploy-platform-app`
- LLM repo example: `http://webhook.local/webhook?token=gogs-secret-token&job=aiops-LLM-deploy`
- Secret Token: `gogs-secret-token` (`f8558cd963f0001bcb579378e6a67a73e3bb8cb2`)

---

### Runbook 04: Air-Gapped Image Ingestion to Zot Registry

#### Option A — Automated bulk push (recommended when Docker Desktop can reach Zot)

1. Configure Docker insecure registry and `hosts` (section 2.1).
2. Port-forward or expose Zot:
   ```bash
   kubectl port-forward -n devops-core svc/zot 5000:5000 --address 0.0.0.0
   ```
3. From Windows:
   ```powershell
   cd C:\Users\user\Desktop\TargilBait\infra
   .\push_all_images_to_zotRegistry.ps1
   ```
4. Verify: `curl http://zot.local/v2/_catalog` or `curl -u zot:zot http://zot.local/v2/_catalog`

#### Option B — Tarball import + manual tag/push

1. Load image tarball into containerd (cluster node):
   ```bash
   sudo ctr --address /run/k3s/containerd/containerd.sock --namespace k8s.io images import /mnt/c/Users/user/Desktop/TargilBait/infra/aiops_images.tar
   ```
2. Import into **Docker Desktop** as well if you push via `docker push` (Docker and containerd are separate stores on WSL).
3. Tag and push application images, e.g.:
   ```bash
   docker tag aiops-vllm-qwen:v0.6.3 zot.local/aiops-vllm-qwen:v0.6.3
   docker login zot.local -u zot -p zot
   docker push zot.local/aiops-vllm-qwen:v0.6.3
   ```
4. Ensure RKE2 pulls from Zot (`/etc/rancher/rke2/registries.yaml`, section 2.6) and restart `rke2-server` after changes.

#### Zot credentials (Helm)

```bash
kubectl get secret -n devops-core -l owner=helm,name=zot -o name
# htpasswd is set at install time via install_helm_stack.sh (user zot / password zot)
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

### Runbook 07: Testing & Validating the GitOps Deployment Loop (PR -> Webhook -> Jenkins -> ArgoCD)

#### Step 1: Simulate or Merge a Pull Request in Gogs
1. Log into Gogs at `http://gogs.local` (or `http://localhost:3000`).
2. Navigate to `gogs/ai-ops-platform-app`.
3. Create a test branch, edit a file (e.g. `README.md` or a comment in `backend/app.py`), and open a Pull Request.
4. Merge the Pull Request.

#### Step 2: Test the Webhook Endpoint Directly via cURL
To verify the Webhook Proxy gateway independently:
```bash
curl -X POST "http://webhook.local/webhook?token=gogs-secret-token&job=aiops-deploy-platform-app" \
     -H "Content-Type: application/json" \
     -H "X-Gogs-Event: pull_request" \
     -d '{
       "action": "closed",
       "pull_request": {
         "merged": true
       }
     }'
```
*Expected HTTP Response: `200 OK` with payload `{"status": "success", "triggered": true, "job": "aiops-deploy-platform-app"}`.*

#### Step 3: Monitor Jenkins Build Execution
1. Open Jenkins UI at `http://localhost:8085` (`http://jenkins.local`).
2. Observe job `aiops-deploy-platform-app`.
3. Check the console log to verify:
   - Dynamic agent pod initialization (`dind-builder-pod`).
   - Image building and pushing to `zot.local/aiops-backend:v1.0.0-<BUILD_NUMBER>`.
   - `values.yaml` Python modification and Git push back to Gogs.

#### Step 4: Verify ArgoCD Auto-Sync & Kubernetes Deployment Rollout
1. Open ArgoCD UI at `http://argo.local` (`http://localhost:8080`).
2. Select application `ai-ops-platform-app`.
3. Confirm that the Sync status changes to `Synced` / `Processing` and rolling deployment applies the new image tag.
4. Verify cluster pods:
   ```bash
   kubectl get pods -n aiops-platform -o wide
   ```

---

## Appendix: Repository Script & Artifact Inventory

| Path | Role |
|------|------|
| `infra/install_helm_stack.sh` | Offline install: Gogs manifest, Jenkins, Argo CD, Prometheus stack, GPU operator, Zot |
| `infra/install_helm_only_gpu.sh` | GPU operator only (DCGM exporter enabled; no driver/toolkit in cluster) |
| `infra/air_gap_helm.ps1` / `air_gap_helm.sh` | Download and bundle Helm charts to `aiops_helm_charts.zip` / `.tar.gz` |
| `infra/push_all_images_to_zotRegistry.ps1` | Pull upstream images, retag under `zot.local/`, push to private registry |
| `infra/seed-zot.sh` | Helper pod mounted on `zot-storage-pvc` |
| `infra/rke2-network-recovery.sh` | Canal / Traefik CNI recovery (Runbook 01) |
| `infra/all-ingress.yaml` | Ingress rules for `*.local` hostnames |
| `infra/argocd/*.yaml` | Argo CD Application definitions |
| `infra/custom_dind/Dockerfile` | Build `zot.local/python-git-dind:27-pg-dind` for Jenkins |
| `infra/installation.txt` | Operator scratch notes (complements this document) |
| `infra/install_nvidia_on_wsl` | NVIDIA container toolkit + CDI notes for RKE2 on WSL |
| `infra/required_images.txt` | Extra Argo CD–related image references |
| `infra/aiops_images.tar` | Saved Docker images (generated; not committed) |
| `infra/aiops_helm_charts.zip` | Bundled charts (generated; not committed) |
| `ai-ops-platform-app/setup-deps-storage.sh` | Hydrate `python-deps-pvc` |
| `ai-ops-llm-model/setup-model-storage.sh` | Hydrate shared LLM model PVC |

**Multi-repo layout:** `ai-ops-platform-app`, `gogs_webhook`, and `ai-ops-llm-model` are separate Gogs repos with their own `Jenkinsfile` and Helm charts; CI pushes to `zot.local` and commits tag bumps back to Git for Argo CD.

---
*Documentation generated for AIOps Platform Setup & Operations.*
