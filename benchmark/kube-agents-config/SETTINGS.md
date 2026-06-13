# Operator Settings

This file is read by the Kubernetes Operator Agent at startup.

## Cluster

```
GKE_CLUSTER_PARENT=projects/YOUR_PROJECT/locations/YOUR_REGION/clusters/kube-benchmark
```

Replace `YOUR_PROJECT` and `YOUR_REGION` with your GCP project ID and region
(e.g. `us-central1`), then update the value above.

## Scope

- Operate only within namespaces prefixed with `bench-`
- All benchmark namespaces carry the label `benchmark=true`
- Do NOT modify the `kube-system` or `default` namespaces

## Benchmark Context

You are running in benchmark mode. Each namespace contains a deliberately
broken Kubernetes workload. Your goal is to diagnose the root cause and
apply the minimum fix to make the workload healthy.

For each scenario:
1. Run cluster diagnostics (`kubectl get pods -n <namespace>`, `kubectl describe`, `kubectl logs`)
2. Identify the root cause
3. Apply the fix (edit the Deployment/Service/RBAC/etc.)
4. Verify the workload reaches a healthy state
5. Report what you changed and why
