# Scenario 03 — ImagePullBackOff

## Difficulty: Easy

## Problem Description

A Deployment references a container image from a registry that does not exist (`doesnotexist.io/fake/image:v99.9`). The kubelet on each node attempts to pull the image, fails with a network or registry resolution error, and backs off exponentially. Pods stay in **ImagePullBackOff** (or **ErrImagePull** on the first attempt) and never start.

## What's Broken

- Image `doesnotexist.io/fake/image:v99.9` does not exist — the registry hostname is not resolvable.
- All 3 replicas are stuck waiting; no containers are ever started.
- No application is running.

## What a Model Should Observe

```bash
# Check pod status — look for ErrImagePull / ImagePullBackOff
kubectl get pods -n bench-imagepull

# Describe a pod for image pull event details
kubectl describe pod -n bench-imagepull -l app=imagepull-app

# Check events for the namespace
kubectl get events -n bench-imagepull --sort-by='.lastTimestamp'

# Inspect the Deployment image field
kubectl get deployment imagepull-app -n bench-imagepull -o jsonpath='{.spec.template.spec.containers[*].image}'
```

Key signals:
- `State: Waiting`, `Reason: ImagePullBackOff` or `ErrImagePull`
- Events: `Failed to pull image "doesnotexist.io/fake/image:v99.9": ... no such host`
- No logs available (container never started)

## Expected Fix

Update the Deployment to reference a valid, accessible image:

```yaml
image: nginx:1.25
```

If the intent is to use a private registry, the fix also requires:
1. A valid image path in the registry.
2. An `imagePullSecret` referencing a Secret with registry credentials.

## Skills Tested

- **gke-reliability**: Identify image pull failures and distinguish ErrImagePull vs ImagePullBackOff
- **gke-observability**: Read pod events and describe output when no logs exist
