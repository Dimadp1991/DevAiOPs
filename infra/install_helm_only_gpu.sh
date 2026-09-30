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


# --- Deploy GPU Operator ---
GPU_CHART=$(find_chart "gpu-operator")
if [ -n "$GPU_CHART" ]; then
    echo "===> Installing GPU Operator from $GPU_CHART..."
    helm upgrade --install gpu-operator "$GPU_CHART" \
      --namespace gpu-operator \
      --create-namespace \
      --version v26.7.0 \
      --set nfd.enabled=false \
      --set driver.enabled=false \
      --set toolkit.enabled=false \
      --set dcgmExporter.enabled=true \
      --wait
else
    echo "Warning: GPU Operator chart .tgz not found."
fi



echo "===> Deployment completed! Checking pod statuses across namespaces:"
kubectl get pods -A