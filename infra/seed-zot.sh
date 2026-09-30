#!/bin/bash
NAMESPACE="devops-core"
PVC_NAME="zot-storage-pvc"

echo "===> Spawning helper pod to populate $PVC_NAME..."
kubectl run zot-seeder -n "$NAMESPACE" --rm -it --image=alpine:latest --overrides='{
  "spec": {
    "volumes": [
      {
        "name": "zot-storage",
        "persistentVolumeClaim": {
          "claimName": "'"$PVC_NAME"'"
        }
      }
    ],
    "containers": [
      {
        "name": "seeder",
        "image": "alpine:latest",
        "command": ["sh", "-c", "echo 'PVC is ready for image unpacking.' && sleep 3600"],
        "volumeMounts": [
          {
            "name": "zot-storage",
            "mountPath": "/var/lib/registry"
          }
        ]
      }
    ]
  }
}'
