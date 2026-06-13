# Scenario 06 — ResourceQuota Exceeded

## Difficulty: Medium

## Problem Description

A `ResourceQuota` in namespace `bench-quota` caps total memory **requests** at 100Mi and memory **limits** at 200Mi. A Deployment attempts to create 5 replicas each requesting 50Mi memory — a total of 250Mi in requests — which **exceeds the quota by 150Mi**. Kubernetes will create as many pods as fit within the quota (at most 2) and block creation of the rest. The Deployment's desired replica count is never satisfied.

## What's Broken

- **Quota**: `requests.memory: 100Mi`, `limits.memory: 200Mi`
- **Per-pod request**: `memory: 50Mi` × 5 replicas = **250Mi total** (exceeds `requests.memory`)
- The ReplicaSet controller cannot create all 5 pods; at most 2 can be scheduled before the quota is exhausted.
- Deployment shows `AVAILABLE < DESIRED` indefinitely.

## What a Model Should Observe

```bash
# Check Deployment rollout status
kubectl rollout status deployment/quota-busting-app -n bench-quota --timeout=30s
kubectl get deployment quota-busting-app -n bench-quota

# Check ReplicaSet events for quota errors
kubectl describe replicaset -n bench-quota -l app=quota-busting-app

# Check namespace events — look for "exceeded quota" messages
kubectl get events -n bench-quota --sort-by='.lastTimestamp'

# Inspect current quota usage vs limits
kubectl describe resourcequota tight-quota -n bench-quota

# Count running pods
kubectl get pods -n bench-quota
```

Key signals:
- ReplicaSet events: `Error creating: pods ... exceeded quota: tight-quota, requested: requests.memory=50Mi, used: requests.memory=100Mi, limited: requests.memory=100Mi`
- `kubectl describe resourcequota` shows `Used` equals `Hard` for `requests.memory`
- Deployment shows fewer available replicas than desired

## Expected Fix

Choose one of:

**Option A — Increase the quota:**
```bash
kubectl patch resourcequota tight-quota -n bench-quota \
  -p '{"spec":{"hard":{"requests.memory":"500Mi","limits.memory":"1000Mi"}}}'
```

**Option B — Reduce per-pod memory requests:**
```yaml
resources:
  requests:
    memory: "16Mi"
  limits:
    memory: "32Mi"
```

**Option C — Reduce replica count to fit within quota:**
```bash
kubectl scale deployment quota-busting-app -n bench-quota --replicas=1
```

In production, audit quota policies and align them with actual workload needs using `kubectl describe resourcequota`.

## Skills Tested

- **gke-reliability**: Diagnose partial Deployment rollouts due to quota enforcement
- **gke-observability**: Read ResourceQuota usage and ReplicaSet events
- **gke-workload-scaling**: Understand how ResourceQuota interacts with replica scaling
