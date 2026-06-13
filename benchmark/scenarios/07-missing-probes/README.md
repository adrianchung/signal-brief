# Scenario 07 — Missing Probes and HPA Without Metrics

## Difficulty: Medium

## Problem Description

An nginx Deployment is missing **readiness probes**, **liveness probes**, and **resource requests/limits** entirely. A `HorizontalPodAutoscaler` (HPA) targets the Deployment using CPU utilization as the scaling metric. Without resource requests, the metrics-server cannot compute utilization percentages, so the HPA reports `unknown` for current metrics and cannot make scaling decisions.

This scenario surfaces two independent but related problems:
1. **No probes** — Kubernetes cannot determine when a pod is actually ready to serve traffic or needs restarting.
2. **HPA broken** — Without `resources.requests.cpu`, the HPA metric `averageUtilization` is undefined; the HPA shows `<unknown>/50%` and will not scale.

## What's Broken

- No `readinessProbe`: pods are added to Service endpoints immediately, even before the app is ready.
- No `livenessProbe`: a hung/deadlocked process won't be restarted automatically.
- No `resources`: scheduler cannot make informed bin-packing decisions; HPA CPU utilization is undefined.
- HPA shows `TARGETS: <unknown>/50%` and may emit `FailedGetScale` or `unable to get metrics` warnings.

## What a Model Should Observe

```bash
# Check pod status (pods may appear Running, but that's misleading without probes)
kubectl get pods -n bench-probes

# Inspect HPA status — look for <unknown> targets
kubectl get hpa nginx-hpa -n bench-probes
kubectl describe hpa nginx-hpa -n bench-probes

# Check HPA events for metrics errors
kubectl get events -n bench-probes --sort-by='.lastTimestamp'

# Inspect the Deployment spec — confirm no probes, no resources
kubectl get deployment nginx-no-probes -n bench-probes -o yaml

# Check if metrics-server is installed
kubectl get apiservice v1beta1.metrics.k8s.io
```

Key signals:
- `HPA: TARGETS <unknown>/50%`
- HPA events: `failed to get cpu utilization: unable to get metrics for resource cpu`
- Deployment spec has no `readinessProbe`, `livenessProbe`, or `resources` fields
- Even if metrics-server exists, missing requests prevent utilization calculation

## Expected Fix

Add resource requests/limits and health probes to the Deployment:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "64Mi"
  limits:
    cpu: "500m"
    memory: "128Mi"
readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 10
livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 15
  periodSeconds: 20
```

After adding resource requests, verify the HPA begins reporting real metrics:
```bash
kubectl get hpa nginx-hpa -n bench-probes --watch
```

## Skills Tested

- **gke-reliability**: Identify missing health probes and their operational risks
- **gke-observability**: Diagnose HPA metric collection failures
- **gke-workload-scaling**: Understand the dependency between resource requests and HPA CPU utilization metrics
