# Scenario 10 — Missing ConfigMap and Secret

## Difficulty: Hard

## Problem Description

A Deployment references two non-existent Kubernetes objects:

1. **ConfigMap `app-config`** — mounted as a volume at `/etc/app/config` AND loaded as environment variables via `envFrom.configMapRef`.
2. **Secret `app-secrets`** — mounted as a volume in the init container at `/secrets`.

Neither object exists in the namespace. Kubernetes blocks pod creation entirely: the pods never leave `Pending` state, showing `CreateContainerConfigError` or remaining stuck because the volume references cannot be resolved.

This scenario layers multiple missing dependencies, requiring the model to identify all of them rather than stopping after finding the first issue.

## What's Broken

- `ConfigMap/app-config` does not exist → volume mount and `envFrom` both fail.
- `Secret/app-secrets` does not exist → init container volume mount fails.
- Pods are stuck in `Pending` / `CreateContainerConfigError` and never start.
- No application traffic can be served.

## What a Model Should Observe

```bash
# Check pod status — Pending or CreateContainerConfigError
kubectl get pods -n bench-configmap

# Describe a pod — look for volume-related error events
kubectl describe pod -n bench-configmap -l app=configmap-app

# Check events for the namespace
kubectl get events -n bench-configmap --sort-by='.lastTimestamp'

# Confirm ConfigMap does not exist
kubectl get configmap app-config -n bench-configmap

# Confirm Secret does not exist
kubectl get secret app-secrets -n bench-configmap

# Inspect the Deployment spec to enumerate all missing references
kubectl get deployment configmap-app -n bench-configmap -o yaml
```

Key signals:
- Events: `MountVolume.SetUp failed for volume "config-volume": configmap "app-config" not found`
- Events: `MountVolume.SetUp failed for volume "secrets-volume": secret "app-secrets" not found`
- `kubectl get configmap app-config -n bench-configmap` → `NotFound`
- `kubectl get secret app-secrets -n bench-configmap` → `NotFound`
- Pod spec references both objects in `volumes`, `envFrom`, and init container mounts

## Expected Fix

Create both missing objects. Minimal stubs for testing:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: bench-configmap
data:
  APP_ENV: "production"
  LOG_LEVEL: "info"
  SERVER_PORT: "8080"
---
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: bench-configmap
type: Opaque
stringData:
  db-password: "changeme-placeholder"
  api-key: "changeme-placeholder"
```

Apply and verify pods start:
```bash
kubectl apply -f fix.yaml
kubectl rollout status deployment/configmap-app -n bench-configmap
```

In production, ConfigMaps and Secrets should be created (e.g., via Helm, Kustomize, or an external secrets operator like External Secrets Operator) **before** the Deployment that depends on them.

## Skills Tested

- **gke-reliability**: Diagnose pods stuck due to unresolved volume or envFrom references
- **gke-observability**: Interpret mount failure events and distinguish ConfigMap vs. Secret errors
- **gke-workload-security**: Understand the role of Secrets in pod configuration and the risk of missing them
- **gke-reliability**: Handle multi-layered dependency failures (init container + main container both blocked)
