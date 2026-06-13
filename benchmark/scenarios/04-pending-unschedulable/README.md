# Scenario 04 — Pending / Unschedulable (Excessive CPU Request)

## Difficulty: Easy

## Problem Description

A Deployment requests **100 CPU cores** per pod. No realistic Kubernetes node has 100 allocatable CPU cores, so the scheduler cannot place the pods on any node. All replicas remain in **Pending** state indefinitely.

## What's Broken

- `resources.requests.cpu: "100"` — 100 cores per pod, far exceeding any node capacity.
- The scheduler emits `Insufficient cpu` as the reason for unschedulability.
- No pod ever transitions to Running; the Deployment is permanently degraded.

## What a Model Should Observe

```bash
# Check pod status — all should be Pending
kubectl get pods -n bench-pending

# Describe a pending pod — look for "Insufficient cpu" in Events
kubectl describe pod -n bench-pending -l app=pending-app

# Check scheduler events
kubectl get events -n bench-pending --sort-by='.lastTimestamp' | grep -i unschedulable

# Inspect node allocatable CPU capacity
kubectl get nodes -o custom-columns='NAME:.metadata.name,CPU:.status.allocatable.cpu'

# Inspect the Deployment resource requests
kubectl get deployment pending-app -n bench-pending -o yaml
```

Key signals:
- `Status: Pending` on all pods
- Events: `0/N nodes are available: N Insufficient cpu`
- Node allocatable CPU is far below 100 cores
- `resources.requests.cpu: "100"` in the pod spec

## Expected Fix

Lower the CPU request to a realistic value for the actual workload:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

In production, right-size requests based on `kubectl top pods` metrics from a staging environment.

## Skills Tested

- **gke-reliability**: Diagnose Pending pods due to resource pressure
- **gke-observability**: Interpret scheduler events and node allocatable capacity
- **gke-workload-scaling**: Understand CPU request sizing and its scheduling impact
