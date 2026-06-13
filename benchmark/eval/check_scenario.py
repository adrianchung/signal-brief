"""
Scenario health checkers for the k8s DevOps benchmark.

Each checker connects to the cluster via the GKE MCP server and validates
whether a scenario's broken state has been resolved by the agent under test.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


@dataclass
class CheckResult:
    scenario: str
    passed: bool
    reason: str
    details: dict | None = None


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _kubectl(*args: str) -> tuple[int, str, str]:
    """Run kubectl and return (returncode, stdout, stderr)."""
    cmd = ["kubectl", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _get_pods(namespace: str, label: str | None = None) -> list[dict]:
    extra = ["-l", label] if label else []
    rc, out, _ = _kubectl("get", "pods", "-n", namespace, *extra, "-o", "json")
    if rc != 0:
        return []
    return json.loads(out).get("items", [])


def _pod_phases(pods: list[dict]) -> list[str]:
    return [p["status"].get("phase", "Unknown") for p in pods]


def _container_restarts(pods: list[dict]) -> int:
    total = 0
    for pod in pods:
        for cs in pod["status"].get("containerStatuses", []):
            total += cs.get("restartCount", 0)
    return total


# ---------------------------------------------------------------------------
# Scenario checkers
# ---------------------------------------------------------------------------

def check_01_crashloop(namespace: str = "bench-crashloop") -> CheckResult:
    """Passes when no pods in the namespace are in CrashLoopBackOff."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("01-crashloop", False, "No pods found — nothing deployed?")

    bad = []
    for pod in pods:
        for cs in pod["status"].get("containerStatuses", []):
            w = cs.get("state", {}).get("waiting", {})
            if w.get("reason") in ("CrashLoopBackOff", "Error"):
                bad.append(pod["metadata"]["name"])

    if bad:
        return CheckResult("01-crashloop", False, f"Pods still crashing: {bad}")
    phases = _pod_phases(pods)
    all_running = all(p == "Running" for p in phases)
    return CheckResult(
        "01-crashloop",
        all_running,
        "All pods running" if all_running else f"Phases: {phases}",
    )


def check_02_oom(namespace: str = "bench-oom") -> CheckResult:
    """Passes when pods are Running and not OOMKilled."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("02-oom-killed", False, "No pods found")

    oom = []
    for pod in pods:
        for cs in pod["status"].get("containerStatuses", []):
            last = cs.get("lastState", {}).get("terminated", {})
            if last.get("reason") == "OOMKilled":
                oom.append(pod["metadata"]["name"])

    if oom:
        return CheckResult("02-oom-killed", False, f"OOMKilled pods: {oom}")
    phases = _pod_phases(pods)
    all_running = all(p == "Running" for p in phases)
    return CheckResult(
        "02-oom-killed",
        all_running,
        "All pods running without OOM" if all_running else f"Phases: {phases}",
    )


def check_03_image_pull(namespace: str = "bench-imagepull") -> CheckResult:
    """Passes when pods are Running (image pull resolved)."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("03-image-pull-error", False, "No pods found")

    bad = []
    for pod in pods:
        for cs in pod["status"].get("containerStatuses", []):
            w = cs.get("state", {}).get("waiting", {})
            if w.get("reason") in ("ImagePullBackOff", "ErrImagePull"):
                bad.append(pod["metadata"]["name"])

    if bad:
        return CheckResult("03-image-pull-error", False, f"Image pull failing: {bad}")
    phases = _pod_phases(pods)
    all_running = all(p == "Running" for p in phases)
    return CheckResult(
        "03-image-pull-error",
        all_running,
        "Pods running with valid image" if all_running else f"Phases: {phases}",
    )


def check_04_pending(namespace: str = "bench-pending") -> CheckResult:
    """Passes when no pods are stuck Pending."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("04-pending-unschedulable", False, "No pods found")

    pending = [p["metadata"]["name"] for p in pods if p["status"].get("phase") == "Pending"]
    if pending:
        return CheckResult("04-pending-unschedulable", False, f"Still pending: {pending}")
    phases = _pod_phases(pods)
    all_ok = all(p in ("Running", "Succeeded") for p in phases)
    return CheckResult(
        "04-pending-unschedulable",
        all_ok,
        "No pending pods" if all_ok else f"Phases: {phases}",
    )


def check_05_selector(namespace: str = "bench-selector") -> CheckResult:
    """Passes when the Service endpoints are non-empty (selector matches pods)."""
    rc, out, _ = _kubectl("get", "endpoints", "-n", namespace, "-o", "json")
    if rc != 0:
        return CheckResult("05-service-selector-mismatch", False, "Could not read endpoints")
    items = json.loads(out).get("items", [])
    for ep in items:
        name = ep["metadata"]["name"]
        if name == "kubernetes":
            continue
        subsets = ep.get("subsets", [])
        addresses = sum(len(s.get("addresses", [])) for s in subsets)
        if addresses == 0:
            return CheckResult(
                "05-service-selector-mismatch",
                False,
                f"Service '{name}' still has 0 endpoints",
            )
    return CheckResult("05-service-selector-mismatch", True, "Service endpoints populated")


def check_06_quota(namespace: str = "bench-quota") -> CheckResult:
    """Passes when the deployment has its desired replicas running."""
    rc, out, _ = _kubectl("get", "deployment", "-n", namespace, "-o", "json")
    if rc != 0:
        return CheckResult("06-quota-exceeded", False, "Could not read deployments")
    items = json.loads(out).get("items", [])
    if not items:
        return CheckResult("06-quota-exceeded", False, "No deployments found")

    for dep in items:
        desired = dep["spec"].get("replicas", 1)
        ready = dep["status"].get("readyReplicas", 0)
        if ready < desired:
            return CheckResult(
                "06-quota-exceeded",
                False,
                f"Deployment {dep['metadata']['name']}: {ready}/{desired} ready",
            )
    return CheckResult("06-quota-exceeded", True, "All deployment replicas ready")


def check_07_probes(namespace: str = "bench-probes") -> CheckResult:
    """Passes when all containers in the deployment have readiness + liveness probes."""
    rc, out, _ = _kubectl("get", "deployment", "-n", namespace, "-o", "json")
    if rc != 0:
        return CheckResult("07-missing-probes", False, "Could not read deployments")
    items = json.loads(out).get("items", [])
    if not items:
        return CheckResult("07-missing-probes", False, "No deployments found")

    missing = []
    for dep in items:
        for container in dep["spec"]["template"]["spec"].get("containers", []):
            name = container["name"]
            if not container.get("readinessProbe"):
                missing.append(f"{dep['metadata']['name']}/{name}: missing readinessProbe")
            if not container.get("livenessProbe"):
                missing.append(f"{dep['metadata']['name']}/{name}: missing livenessProbe")

    if missing:
        return CheckResult("07-missing-probes", False, "\n".join(missing))
    return CheckResult("07-missing-probes", True, "All containers have readiness + liveness probes")


def check_08_rbac(namespace: str = "bench-rbac") -> CheckResult:
    """Passes when the pod can successfully list pods (RBAC fixed)."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("08-rbac-violation", False, "No pods found")

    # Check pod logs for success marker
    for pod in pods:
        pod_name = pod["metadata"]["name"]
        rc, out, _ = _kubectl("logs", pod_name, "-n", namespace, "--tail=20")
        if rc == 0 and ("NAME" in out or "pod/" in out.lower()):
            return CheckResult("08-rbac-violation", True, "Pod can list pods via API")
        if "Forbidden" in out or "RBAC" in out or "forbidden" in out:
            return CheckResult(
                "08-rbac-violation",
                False,
                f"RBAC still blocking: {out[:200]}",
            )

    phases = _pod_phases(pods)
    return CheckResult("08-rbac-violation", False, f"Cannot confirm RBAC fix. Phases: {phases}")


def check_09_affinity(namespace: str = "bench-affinity") -> CheckResult:
    """Passes when pods are no longer stuck Pending due to node affinity."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("09-node-affinity-impossible", False, "No pods found")

    pending = []
    for pod in pods:
        if pod["status"].get("phase") == "Pending":
            for cond in pod["status"].get("conditions", []):
                if cond.get("reason") in ("Unschedulable",):
                    pending.append(pod["metadata"]["name"])

    if pending:
        return CheckResult(
            "09-node-affinity-impossible",
            False,
            f"Pods still unschedulable (affinity/taint not resolved): {pending}",
        )
    phases = _pod_phases(pods)
    all_ok = all(p in ("Running", "Succeeded") for p in phases)
    return CheckResult(
        "09-node-affinity-impossible",
        all_ok,
        "Pods schedulable" if all_ok else f"Phases: {phases}",
    )


def check_10_configmap(namespace: str = "bench-configmap") -> CheckResult:
    """Passes when pods are Running (ConfigMap + Secret mounted successfully)."""
    pods = _get_pods(namespace)
    if not pods:
        return CheckResult("10-configmap-missing", False, "No pods found")

    bad = []
    for pod in pods:
        phase = pod["status"].get("phase", "Unknown")
        if phase != "Running":
            for cond in pod["status"].get("conditions", []):
                msg = cond.get("message", "")
                if "configmap" in msg.lower() or "secret" in msg.lower():
                    bad.append(f"{pod['metadata']['name']}: {msg[:120]}")
            if not bad:
                bad.append(f"{pod['metadata']['name']}: phase={phase}")

    if bad:
        return CheckResult("10-configmap-missing", False, "\n".join(bad))
    return CheckResult("10-configmap-missing", True, "All pods running with ConfigMap + Secret mounted")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CHECKERS: dict[str, Callable[[], CheckResult]] = {
    "01-crashloop":              check_01_crashloop,
    "02-oom-killed":             check_02_oom,
    "03-image-pull-error":       check_03_image_pull,
    "04-pending-unschedulable":  check_04_pending,
    "05-service-selector-mismatch": check_05_selector,
    "06-quota-exceeded":         check_06_quota,
    "07-missing-probes":         check_07_probes,
    "08-rbac-violation":         check_08_rbac,
    "09-node-affinity-impossible": check_09_affinity,
    "10-configmap-missing":      check_10_configmap,
}


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else None
    targets = {name: CHECKERS[name]} if name else CHECKERS
    for scenario, fn in targets.items():
        result = fn()
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.scenario}: {result.reason}")
