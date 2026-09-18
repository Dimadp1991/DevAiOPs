# Create destination directory
New-Item -ItemType Directory -Force -Path .\helm-charts | Out-Null

# Add verified upstream helm repositories
helm repo add jenkins https://charts.jenkins.io
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add gpu-operator https://nvidia.github.io/gpu-operator
helm repo add zot https://project-zot.github.io/helm-charts
helm repo update



Write-Host "===> Pulling Helm charts for offline packaging..." -ForegroundColor Green
helm pull jenkins/jenkins --destination ./helm-charts
helm pull argo/argo-cd --destination ./helm-charts
helm pull prometheus-community/kube-prometheus-stack --destination ./helm-charts
helm pull gpu-operator/gpu-operator --destination ./helm-charts
helm pull zot/zot --destination ./helm-charts

# Compress into a single bundle
Write-Host "===> Compressing charts archive..." -ForegroundColor Green
Compress-Archive -Path .\helm-charts\* -DestinationPath .\aiops_helm_charts.zip -Force

Write-Host "===> Complete! Transfer 'aiops_helm_charts.zip' across the air gap." -ForegroundColor Green