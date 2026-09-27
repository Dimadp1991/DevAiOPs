#!/bin/bash

set -e

echo "===> RKE2 Network Recovery Script (Canal / Calico IPAM fix)"
echo

# 1. Make sure we have the tools
if ! command -v iptables >/dev/null 2>&1; then
  echo "[+] Installing iptables..."
  sudo apt update
  sudo apt install -y iptables
fi

# 2. Stop RKE2
echo "[+] Stopping rke2-server..."
sudo systemctl stop rke2-server

# 3. Clean corrupted CNI / Calico state
echo "[+] Cleaning CNI and Calico state..."
sudo rm -rf /var/lib/cni/networks/* 2>/dev/null || true
sudo rm -rf /var/lib/cni/results/* 2>/dev/null || true
sudo rm -rf /var/run/calico/* 2>/dev/null || true
sudo rm -rf /var/lib/calico/* 2>/dev/null || true

# Recreate required directory
sudo mkdir -p /var/lib/calico

# Optional: clean old containerd sandboxes (safe)
sudo rm -rf /var/lib/rancher/rke2/agent/containerd/io.containerd.grpc.v1.cri/sandboxes/* 2>/dev/null || true

# 4. Start RKE2 again
echo "[+] Starting rke2-server..."
sudo systemctl start rke2-server

echo "[+] Waiting for API server to become ready..."
sleep 20

# 5. Set kubeconfig
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml

# Wait until API is reachable
for i in {1..30}; do
  if kubectl get nodes >/dev/null 2>&1; then
    echo "[+] API server is up"
    break
  fi
  echo "    waiting for API... ($i/30)"
  sleep 5
done

# 6. Restart Canal
echo "[+] Restarting Canal..."
kubectl delete pod -n kube-system -l k8s-app=canal --force --grace-period=0 2>/dev/null || true

# 7. Clean any remaining non-running pods
echo "[+] Cleaning non-running pods..."
kubectl delete pods -A --field-selector=status.phase!=Running --force --grace-period=0 2>/dev/null || true

echo
echo "===> Recovery finished. Current status:"
kubectl get pods -A
echo
echo "Check Traefik and CoreDNS especially."