# Scenario 08 — RBAC Violation / Insufficient Permissions

## Difficulty: Hard

## Problem Description

A Pod uses a ServiceAccount (`restricted-sa`) that has **no RBAC bindings** — no Role, ClusterRole, RoleBinding, or ClusterRoleBinding is attached to it. A sidecar container in the same Pod runs a loop that repeatedly calls `kubectl get pods` and `kubectl get services`. Every call fails with a **403 Forbidden** error because the ServiceAccount token has no permissions in the Kubernetes API.

The main `nginx` container runs fine — this scenario tests whether the model can identify that the *application's* Kubernetes API calls are being denied due to missing RBAC, rather than a container runtime problem.

## What's Broken

- `restricted-sa` ServiceAccount has zero RBAC bindings.
- The `kubectl-sidecar` container attempts API calls (`list pods`, `list services`) that are unauthorized.
- Sidecar logs show repeated `Error from server (Forbidden): pods is forbidden: User "system:serviceaccount:bench-rbac:restricted-sa" cannot list resource "pods" in API group "" in the namespace "bench-rbac"`.

## What a Model Should Observe

```bash
# Check pod status — pod may appear Running (nginx container is healthy)
kubectl get pods -n bench-rbac

# Read sidecar container logs — look for Forbidden errors
kubectl logs rbac-test-pod -n bench-rbac -c kubectl-sidecar

# Inspect the ServiceAccount
kubectl get serviceaccount restricted-sa -n bench-rbac -o yaml

# Check for any RoleBindings or ClusterRoleBindings referencing this SA
kubectl get rolebindings -n bench-rbac -o yaml
kubectl get clusterrolebindings -o yaml | grep -A5 restricted-sa

# Verify what the SA is allowed to do (should return nothing or denied)
kubectl auth can-i list pods -n bench-rbac \
  --as system:serviceaccount:bench-rbac:restricted-sa

kubectl auth can-i list services -n bench-rbac \
  --as system:serviceaccount:bench-rbac:restricted-sa
```

Key signals:
- Sidecar logs: `Error from server (Forbidden)` on every `kubectl` call
- `kubectl auth can-i` returns `no` for all actions under `restricted-sa`
- No RoleBinding or ClusterRoleBinding references `restricted-sa`

## Expected Fix

Create a Role and RoleBinding granting the ServiceAccount the minimum permissions it needs:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: bench-rbac
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: restricted-sa-pod-reader
  namespace: bench-rbac
subjects:
  - kind: ServiceAccount
    name: restricted-sa
    namespace: bench-rbac
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

Apply and verify:
```bash
kubectl apply -f fix.yaml
kubectl auth can-i list pods -n bench-rbac \
  --as system:serviceaccount:bench-rbac:restricted-sa
# Expected: yes
```

## Skills Tested

- **gke-workload-security**: Diagnose RBAC permission failures via `kubectl auth can-i` and log analysis
- **gke-observability**: Identify 403 Forbidden errors in sidecar logs vs. container runtime issues
- **gke-reliability**: Distinguish a pod that is "Running" from a pod whose workload is actually failing
