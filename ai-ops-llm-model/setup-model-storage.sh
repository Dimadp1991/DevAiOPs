#!/bin/bash
set -e

# Configuration
NAMESPACE="devops-core"
PVC_NAME="shared-model-pvc"
PVC_SIZE="20Gi"

# Local path to your model files
LOCAL_MODEL_PATH="./qwen2.5-3b-awq"

# Dynamically derive the model name from the local folder name
# (e.g., "qwen2.5-1.5b-instruct-hebrew"), or override it manually if needed:
MODEL_NAME=$(basename "${LOCAL_MODEL_PATH}")

echo "=== Step 1: Ensuring Namespace exists ==="
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

echo "=== Step 2: Checking if PVC '${PVC_NAME}' already exists ==="
if kubectl get pvc "${PVC_NAME}" -n "${NAMESPACE}" &>/dev/null; then
    echo "PVC '${PVC_NAME}' already exists in namespace '${NAMESPACE}'. Skipping creation."
else
    echo "PVC '${PVC_NAME}' does not exist. Creating..."
    cat <<EOF > model-pvc.yaml
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
    kubectl apply -f model-pvc.yaml
    rm -f model-pvc.yaml
fi

echo "=== Step 3: Spinning up temporary helper pod to bind the PVC ==="
cat <<EOF > temp-helper-pod.yaml
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

kubectl apply -f temp-helper-pod.yaml

echo "Waiting for helper pod to become ready..."
kubectl wait --for=condition=Ready pod/storage-initializer -n ${NAMESPACE} --timeout=60s

echo "=== Step 4: Copying model files into the PVC via kubectl cp ==="
if [ ! -d "$LOCAL_MODEL_PATH" ]; then
    echo "Error: Local model path '$LOCAL_MODEL_PATH' does not exist. Please update the script variable."
    kubectl delete pod storage-initializer -n ${NAMESPACE} --ignore-not-found
    rm -f temp-helper-pod.yaml
    exit 1
fi

# Check if model directory already exists on the PVC
if kubectl exec storage-initializer -n ${NAMESPACE} -- test -d "/pvc/${MODEL_NAME}"; then
    echo "Warning: Model directory '/pvc/${MODEL_NAME}' already exists on the PVC."
    read -p "Do you want to overwrite/re-copy the files? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping file copy."
        kubectl delete pod storage-initializer -n ${NAMESPACE} --ignore-not-found
        rm -f temp-helper-pod.yaml
        echo "SUCCESS! Operation completed safely."
        exit 0
    fi
fi

echo "Creating target directory inside the pod: /pvc/${MODEL_NAME}"
kubectl exec storage-initializer -n ${NAMESPACE} -- mkdir -p "/pvc/${MODEL_NAME}"

echo "Uploading model files to /pvc/${MODEL_NAME}/ (this may take a minute)..."
kubectl cp "${LOCAL_MODEL_PATH}/." ${NAMESPACE}/storage-initializer:"/pvc/${MODEL_NAME}/"

echo "=== Step 5: Cleaning up helper pod ==="
kubectl delete pod storage-initializer -n ${NAMESPACE} --ignore-not-found
rm -f temp-helper-pod.yaml

echo "SUCCESS! Model files are safely populated on the PVC at /pvc/${MODEL_NAME}."