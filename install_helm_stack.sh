#!/usr/bin/env bash
set -euo pipefail

CHARTS_DIR="./helm-charts"
ZIP_FILE="aiops_helm_charts.zip"

# 1. Unpack the zip archive if the directory does not exist
if [ ! -d "$CHARTS_DIR" ]; then
    if [ -f "$ZIP_FILE" ]; then
        echo "===> Unpacking $ZIP_FILE..."
        unzip "$ZIP_FILE" -d "$CHARTS_DIR"
    else
        echo "Error: Neither $CHARTS_DIR directory nor $ZIP_FILE exists."
        exit 1
    fi
fi

# 2. Function to find matching .tgz archive by pattern
find_chart() {
    local pattern="$1"
    find "$CHARTS_DIR" -maxdepth 1 -name "${pattern}-*.tgz" | head -n 1
}

echo "===> Starting deployment of AIOps stack..."

# --- Deploy Gogs (Raw Manifest) ---
if [ -f "$CHARTS_DIR/gogs.yaml" ]; then
    echo "===> Deploying Gogs..."
    kubectl apply -f "$CHARTS_DIR/gogs.yaml"
else
    echo "Warning: $CHARTS_DIR/gogs.yaml not found, skipping Gogs."
fi

# --- Deploy Jenkins ---
JENKINS_CHART=$(find_chart "jenkins")
if [ -n "$JENKINS_CHART" ]; then
    echo "===> Installing Jenkins from $JENKINS_CHART..."
    helm upgrade --install jenkins "$JENKINS_CHART" \
        --namespace devops-core \
        --create-namespace \
        --set controller.image.pullPolicy=IfNotPresent
else
    echo "Warning: Jenkins chart .tgz not found."
fi

# --- Deploy ArgoCD ---
ARGO_CHART=$(find_chart "argo-cd")
if [ -n "$ARGO_CHART" ]; then
    echo "===> Installing ArgoCD from $ARGO_CHART..."
    helm upgrade --install argo-cd "$ARGO_CHART" \
        --namespace argocd \
        --create-namespace \
        --set global.image.imagePullPolicy=IfNotPresent \
        --set server.insecure=true \
        --set server.extraArgs[0]="--insecure"
else
    echo "Warning: ArgoCD chart .tgz not found."
fi

# --- Deploy Prometheus / Grafana Stack ---
PROM_CHART=$(find_chart "kube-prometheus-stack")
if [ -n "$PROM_CHART" ]; then
    echo "===> Installing Prometheus Stack from $PROM_CHART..."
    helm upgrade --install prometheus "$PROM_CHART" \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.prometheusSpec.image.pullPolicy=IfNotPresent
else
    echo "Warning: Prometheus Stack chart .tgz not found."
fi

# --- Deploy GPU Operator ---
GPU_CHART=$(find_chart "gpu-operator")
if [ -n "$GPU_CHART" ]; then
    echo "===> Installing GPU Operator from $GPU_CHART..."
    helm upgrade --install gpu-operator "$GPU_CHART" \
      --namespace gpu-operator \
        --create-namespace \
        --set operator.repository="nvcr.io/nvidia" \
        --set operator.image="gpu-operator" \
        --set operator.version="v26.7.0" \
        --set operator.upgradeCRD.repository="nvcr.io/nvidia" \
        --set operator.upgradeCRD.image="gpu-operator" \
        --set operator.upgradeCRD.version="v26.7.0" \
        --set image.repository="nvcr.io/nvidia/gpu-operator" \
        --set image.pullPolicy="IfNotPresent"
else
    echo "Warning: GPU Operator chart .tgz not found."
fi


# --- Deploy Zot Registry ---
ZOT_CHART=$(find_chart "zot")
if [ -n "$ZOT_CHART" ]; then
    echo "===> Installing Zot Registry from $ZOT_CHART..."
    helm upgrade --install zot "$ZOT_CHART" \
        --namespace devops-core \
        --create-namespace \
        --set image.repository=ghcr.io/project-zot/zot-linux-amd64 \
        --set image.pullPolicy=IfNotPresent
else
    echo "Warning: Zot chart .tgz not found."
fi

echo "===> Deployment completed! Checking pod statuses across namespaces:"
kubectl get pods -A