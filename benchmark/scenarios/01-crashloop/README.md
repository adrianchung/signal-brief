# Scenario 01 — CrashLoopBackOff

## Difficulty: Easy

## Problem Description

A Deployment runs a container that immediately exits with a non-zero exit code (`exit 1`). Kubernetes restarts the container repeatedly, applying an exponential back-off delay between attempts. The pods enter **CrashLoopBackOff** state and never reach Running.

## What's Broken

- Container command is `sh -c "echo 'Starting...'; exit 1"` — always fails instantly.
- Both replicas are stuck in CrashLoopBackOff.
- No application traffic can be served.

## What a Model Should Observe

```bash
# Check pod status
kubectl get pods -n bench-crashloop

# Describe a crashing pod — look for Last State / Exit Code / Restart Count
kubectl describe pod -n bench-crashloop -l app=crashloop-app

# Read the container logs from the most recent failed attempt
kubectl logs -n bench-crashloop -l app=crashloop-app --previous

# Inspect the Deployment spec
kubectl get deployment crashloop-app -n bench-crashloop -o yaml
```

Key signals:
- `State: Waiting`, `Reason: CrashLoopBackOff`
- `Last State: Terminated`, `Exit Code: 1`
- High `Restart Count`
- Logs show `Starting...` then nothing more

## Expected Fix

Replace the container command with one that keeps the process alive, e.g.:

```yaml
command: ["sh", "-c", "echo 'Starting...'; sleep infinity"]
```

Or point to a real application image/command that exits 0 only on intentional shutdown.

## Skills Tested

- **gke-reliability**: Identify and resolve pod restart loops
- **gke-observability**: Read pod events, describe output, and prior-run logs
