# Scenario 02 — OOMKilled

## Difficulty: Easy

## Problem Description

A Deployment runs a memory stress tool (`polinux/stress`) that intentionally allocates 100MB of memory. The container's memory limit is set to only **10Mi**, so the Linux kernel OOM killer terminates the process as soon as it exceeds the limit. Kubernetes restarts it, causing a repeated OOMKilled / CrashLoopBackOff cycle.

## What's Broken

- Container memory limit: `10Mi`
- Container memory allocation attempt: `100M` (10× over the limit)
- Pods cycle through `OOMKilled` → `CrashLoopBackOff` indefinitely.

## What a Model Should Observe

```bash
# Check pod status — look for OOMKilled reason
kubectl get pods -n bench-oom

# Describe a pod for detailed last-state info
kubectl describe pod -n bench-oom -l app=oom-app

# Check events on the namespace
kubectl get events -n bench-oom --sort-by='.lastTimestamp'

# Review resource limits in the Deployment
kubectl get deployment oom-app -n bench-oom -o yaml
```

Key signals:
- `Last State: Terminated`, `Reason: OOMKilled`
- `Exit Code: 137` (SIGKILL from kernel)
- Memory limit `10Mi` is far below what the process needs

## Expected Fix

Either increase the memory limit to accommodate the workload:

```yaml
resources:
  limits:
    memory: "256Mi"
  requests:
    memory: "128Mi"
```

Or reduce the stress tool's allocation to fit within the existing limit:

```yaml
args: ["stress", "--vm", "1", "--vm-bytes", "8M", "--vm-hang", "0"]
```

In a real scenario the fix is to right-size the limit based on actual application memory profiling.

## Skills Tested

- **gke-reliability**: Diagnose OOMKilled pods and memory pressure
- **gke-observability**: Interpret exit codes, last-state reason, and resource limit fields
- **gke-workload-scaling**: Understand resource requests vs. limits and their impact on scheduling/runtime
