# Scenario 05 — Service Selector Mismatch

## Difficulty: Medium

## Problem Description

A backend Deployment runs pods labeled `app: backend`. A Service intended to route traffic to those pods has its selector set to `app: frontend` — a label that no pod in the namespace carries. As a result the Service has **no Endpoints**, and a client pod that repeatedly tries to reach the service fails every time with a connection timeout.

## What's Broken

- **Deployment pod labels**: `app: backend`
- **Service selector**: `app: frontend`
- The Service `backend-svc` has 0 endpoints; all traffic is dropped.
- The `client-pod` logs repeated connection failures to `http://backend-svc/`.

## What a Model Should Observe

```bash
# Check that pods are Running (they will be — the pods themselves are fine)
kubectl get pods -n bench-selector

# Inspect the Service — Endpoints field should be <none>
kubectl get endpoints backend-svc -n bench-selector
kubectl describe svc backend-svc -n bench-selector

# Check the Deployment pod labels
kubectl get pods -n bench-selector --show-labels

# Read client-pod logs to confirm connection failures
kubectl logs client-pod -n bench-selector

# Compare Service selector vs pod labels directly
kubectl get svc backend-svc -n bench-selector -o jsonpath='{.spec.selector}'
kubectl get pods -n bench-selector -l app=backend --show-labels
```

Key signals:
- `Endpoints: <none>` on the Service
- Service selector `app: frontend` does not match any pod label
- Client logs show repeated `wget` timeouts / failures

## Expected Fix

Fix the Service selector to match the actual pod labels:

```yaml
spec:
  selector:
    app: backend
```

Apply with:
```bash
kubectl patch svc backend-svc -n bench-selector -p '{"spec":{"selector":{"app":"backend"}}}'
```

After the patch, verify endpoints are populated:
```bash
kubectl get endpoints backend-svc -n bench-selector
```

## Skills Tested

- **gke-reliability**: Diagnose services with no endpoints and traffic routing failures
- **gke-observability**: Correlate pod labels, service selectors, and endpoint objects
- **gke-workload-security**: Understand label-based routing as a Kubernetes primitive
