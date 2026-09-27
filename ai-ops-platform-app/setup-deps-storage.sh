#!/bin/bash
set -e

NAMESPACE="aiops-platform"
PVC_NAME="python-deps-pvc"
PVC_SIZE="1Gi"
LOCAL_WHEELS_PATH="./wheels"

echo "=== Step 1: Creating Namespace and PVC ==="
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

cat <<EOF > python-deps-pvc.yaml
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

kubectl apply -f python-deps-pvc.yaml

echo "=== Step 2: Spinning up temporary helper pod ==="
cat <<EOF > temp-helper-pod.yaml
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

kubectl apply -f temp-helper-pod.yaml
kubectl wait --for=condition=Ready pod/storage-initializer -n ${NAMESPACE} --timeout=60s

echo "=== Step 3: Copying wheel files into PVC ==="
if [ ! -d "$LOCAL_WHEELS_PATH" ]; then
    echo "Error: Local wheels path '$LOCAL_WHEELS_PATH' does not exist."
    echo "Generate wheels: pip download -r all_requirements.txt -d ./wheels"
    kubectl delete pod storage-initializer -n ${NAMESPACE}
    exit 1
fi

kubectl exec storage-initializer -n ${NAMESPACE} -- rm -rf /pvc/wheels
kubectl exec storage-initializer -n ${NAMESPACE} -- mkdir -p /pvc/wheels
kubectl cp "${LOCAL_WHEELS_PATH}/." ${NAMESPACE}/storage-initializer:/pvc/wheels/

echo "=== Step 4: Installing wheels into PVC site-packages ==="
kubectl exec storage-initializer -n ${NAMESPACE} -- sh -c "pip install --no-index --find-links=/pvc/wheels --target=/pvc/site-packages /pvc/wheels/*.whl"

echo "=== Step 5: Cleanup ==="
kubectl delete pod storage-initializer -n ${NAMESPACE}
rm -f temp-helper-pod.yaml python-deps-pvc.yaml

echo "SUCCESS! Dependencies installed on PVC '${PVC_NAME}'."
