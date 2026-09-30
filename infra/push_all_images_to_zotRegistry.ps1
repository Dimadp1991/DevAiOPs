# Configuration
$Registry = "zot.local" # Replace with your Zot registry URL, Ingress IP, or port (e.g., localhost:5000)
$ZotUser = "zot"
$ZotPass = "zot" # Default from your htpasswd setup, change if needed

Write-Host "=== 1. Logging into Zot Registry ($Registry) ===" -ForegroundColor Cyan
$PasswordSecure = ConvertTo-SecureString $ZotPass -AsPlainText -Force
$Credential = New-Object System.Management.Automation.PSCredential ($ZotUser, $PasswordSecure)
# If using standard Docker CLI:
$ZotPass | docker login $Registry -u $ZotUser --password-stdin

# List of images contained in your tarball that you want to tag and push
$Images = @(
    "vllm/vllm-openai:v0.6.3"
    "gogs/gogs:latest"
    "ghcr.io/project-zot/zot-linux-amd64:latest"
    "jenkins/jenkins:lts-jdk17"
    "gcr.io/kaniko-project/executor:debug"
    "rancher/local-path-provisioner:v0.0.30"
    "postgres:16-alpine"
    "python:3.12-slim"
    "python:3.11-slim"
    "python-git-dind:27-pg-dind"
    "quay.io/argoproj/argocd:v3.5.3"
    "ghcr.io/dexidp/dex:v2.45.1"
    "ecr-public.aws.com/docker/library/redis:8.6.4-alpine"
    "quay.io/prometheus-operator/prometheus-operator:v0.78.1"
    "quay.io/prometheus/prometheus:v2.54.1"
    "quay.io/prometheus/alertmanager:v0.27.0"
    "quay.io/prometheus/node-exporter:v1.8.2"
    "registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0"
    "quay.io/kiwigrid/k8s-sidecar:v1.28.0"
    "grafana/grafana:11.2.0"
    "nvcr.io/nvidia/gpu-operator:v26.7.0"
    "nvcr.io/nvidia/k8s-device-plugin:v0.16.2"
    "nvcr.io/nvidia/cloud-native/gpu-operator-validator:v26.7.0"
    "nvcr.io/nvidia/container-toolkit:v1.16.2-cuda"
    "nvcr.io/nvidia/driver:550.54.14"
    "registry.k8s.io/nfd/node-feature-discovery:v0.16.2"

)

Write-Host "=== 2. Tagging and pushing images to Zot ===" -ForegroundColor Cyan
foreach ($img in $Images) {
    $TargetTag = "$Registry/$img"
    docker pull $img
    Write-Host "Processing: $img -> $TargetTag" -ForegroundColor Yellow
    docker tag $img $TargetTag

    Write-Host "Pushing $TargetTag..." -ForegroundColor Green
    docker push $TargetTag
}

Write-Host "=== Done! All images successfully pushed to Zot. ===" -ForegroundColor Green