# Scenario 09 — Impossible Node Affinity

## Difficulty: Hard

## Problem Description

A Deployment has a **required** `nodeAffinity` rule demanding that every pod runs on a node labeled `disktype: ssd-nvme-ultra`. No node in the cluster carries this label. Additionally the pod spec includes a toleration for a taint `gpu=true:NoSchedule`, which implies the intent was to run on GPU nodes — but neither that taint nor the required label exist on any node.

The result is that **all pods are permanently Pending**. Unlike a resource shortage (which could be resolved by adding nodes), this failure requires either relabeling existing nodes or removing/relaxing the affinity rule.

## What's Broken

- `nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution` requires `disktype=ssd-nvme-ultra` on the target node.
- No node in the cluster has this label.
- The toleration for `gpu=true:NoSchedule` is harmless on its own but signals confused scheduling intent.
- All 3 replicas are Pending indefinitely.

## What a Model Should Observe

```bash
# Check pod status — all Pending
kubectl get pods -n bench-affinity

# Describe a pending pod — look for node affinity failure in Events
kubectl describe pod -n bench-affinity -l app=affinity-app

# Check scheduler events
kubectl get events -n bench-affinity --sort-by='.lastTimestamp'

# List all node labels — confirm disktype=ssd-nvme-ultra is absent
kubectl get nodes --show-labels
kubectl get nodes -o custom-columns='NAME:.metadata.name,LABELS:.metadata.labels'

# Inspect the Deployment nodeAffinity spec
kubectl get deployment affinity-app -n bench-affinity -o yaml
```

Key signals:
- Events: `0/N nodes are available: N node(s) didn't match Pod's node affinity/selector`
- `kubectl get nodes --show-labels` shows no node with `disktype=ssd-nvme-ultra`
- `requiredDuringSchedulingIgnoredDuringExecution` is a hard constraint — no fallback

## Expected Fix

**Option A — Remove or relax the node affinity rule** (if the label requirement is wrong):

```bash
kubectl patch deployment affinity-app -n bench-affinity --type=json \
  -p='[{"op":"remove","path":"/spec/template/spec/affinity"}]'
```

**Option B — Label an existing node to satisfy the requirement** (if the affinity intent is correct):

```bash
kubectl label node <node-name> disktype=ssd-nvme-ultra
```

**Option C — Change to `preferredDuringSchedulingIgnoredDuringExecution`** (soft preference, not hard requirement):

```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
            - key: disktype
              operator: In
              values:
                - ssd-nvme-ultra
```

## Skills Tested

- **gke-reliability**: Diagnose impossible scheduling constraints vs. resource-based Pending
- **gke-observability**: Interpret scheduler affinity/selector mismatch events
- **gke-workload-security**: Understand the difference between taints/tolerations and node affinity
- **gke-workload-scaling**: Distinguish `required` vs. `preferred` scheduling constraints
