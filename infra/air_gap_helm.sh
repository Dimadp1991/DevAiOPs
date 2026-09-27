#!/usr/bin/env bash
set -euo pipefail

# Add upstream helm repositories
helm repo add gogs https://gogs.github.io/helm-charts
helm repo add jenkins https://charts.jenkins.io
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add gpu-operator https://nvidia.github.io/gpu-operator
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Download chart tarballs
echo "===> Pulling Helm charts for offline packaging..."
helm pull gogs/gogs --destination ./helm-charts
helm pull jenkins/jenkins --destination ./helm-charts
helm pull argo/argo-cd --destination ./helm-charts
helm pull prometheus-community/kube-prometheus-stack --destination ./helm-charts
helm pull gpu-operator/dcgm-exporter --destination ./helm-charts
helm pull bitnami/postgresql --destination ./helm-charts

# Compress into a single bundle
tar -czvf aiops_helm_charts.tar.gz ./helm-charts
echo "===> Complete! Transfer 'aiops_helm_charts.tar.gz' across the air gap."