#!/usr/bin/env python3
"""
K8s DevOps Benchmark Runner

Deploys failing Kubernetes scenarios, waits for an agent to attempt fixes,
then evaluates and scores the results.

Usage:
    python benchmark/runner.py --model kube-agents --cluster <parent>
    python benchmark/runner.py --model baseline --scenarios 01,02,03
    python benchmark/runner.py --score-only benchmark/results.jsonl
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent
SCENARIOS_DIR = ROOT / "scenarios"
RESULTS_FILE = ROOT / "results.jsonl"

sys.path.insert(0, str(ROOT.parent))
from benchmark.eval.check_scenario import CHECKERS
from benchmark.eval.score_results import load_results, score, print_report


# ---------------------------------------------------------------------------
# Cluster helpers
# ---------------------------------------------------------------------------

def _kubectl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, check=check)


def apply_scenario(scenario_dir: Path) -> bool:
    manifest = scenario_dir / "setup.yaml"
    if not manifest.exists():
        print(f"  [SKIP] No setup.yaml in {scenario_dir}", file=sys.stderr)
        return False
    r = _kubectl("apply", "-f", str(manifest))
    if r.returncode != 0:
        print(f"  [ERROR] apply failed:\n{r.stderr}", file=sys.stderr)
        return False
    print(f"  [OK] Applied {manifest.name}")
    return True


def teardown_scenario(scenario_dir: Path) -> None:
    manifest = scenario_dir / "setup.yaml"
    if manifest.exists():
        _kubectl("delete", "-f", str(manifest), "--ignore-not-found=true")


def cleanup_all() -> None:
    """Remove all benchmark namespaces."""
    r = _kubectl("get", "namespace", "-l", "benchmark=true", "-o", "jsonpath={.items[*].metadata.name}")
    if r.returncode == 0 and r.stdout.strip():
        namespaces = r.stdout.strip().split()
        for ns in namespaces:
            print(f"  Deleting namespace {ns}")
            _kubectl("delete", "namespace", ns, "--ignore-not-found=true")


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------

def run_kube_agents(scenario: str, cluster_parent: str, timeout: int = 300) -> None:
    """
    Invoke the kube-agents operator agent against the given scenario.
    The agent receives the scenario namespace and cluster info, then
    autonomously diagnoses and fixes the issue.
    """
    config_dir = ROOT / "kube-agents-config"
    settings = config_dir / "SETTINGS.md"
    if not settings.exists():
        print(f"  [WARN] kube-agents config not found at {config_dir}; agent won't run")
        return

    # Build a task description pointing the agent at the failing namespace
    checker_fn = CHECKERS.get(scenario)
    namespace = _scenario_namespace(scenario)

    task = (
        f"Diagnose and fix the Kubernetes issue in namespace '{namespace}' "
        f"on cluster '{cluster_parent}'. "
        f"The cluster is a GKE cluster. "
        f"Use kubectl and GKE tools to investigate and resolve the issue. "
        f"Once fixed, confirm the workloads are healthy."
    )

    agent_script = config_dir / "run_agent.sh"
    if agent_script.exists():
        subprocess.run(
            ["bash", str(agent_script), scenario, namespace, cluster_parent, task],
            timeout=timeout,
        )
    else:
        print(f"  [INFO] No run_agent.sh found. Manual agent invocation needed.")
        print(f"  Task: {task}")


def _scenario_namespace(scenario: str) -> str:
    """Map scenario name to its Kubernetes namespace."""
    mapping = {
        "01-crashloop":                 "bench-crashloop",
        "02-oom-killed":                "bench-oom",
        "03-image-pull-error":          "bench-imagepull",
        "04-pending-unschedulable":     "bench-pending",
        "05-service-selector-mismatch": "bench-selector",
        "06-quota-exceeded":            "bench-quota",
        "07-missing-probes":            "bench-probes",
        "08-rbac-violation":            "bench-rbac",
        "09-node-affinity-impossible":  "bench-affinity",
        "10-configmap-missing":         "bench-configmap",
    }
    return mapping.get(scenario, f"bench-{scenario}")


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------

def run_benchmark(
    model: str,
    scenarios: list[str],
    cluster_parent: str,
    agent_timeout: int = 300,
    eval_wait: int = 30,
    teardown: bool = False,
    results_file: Path = RESULTS_FILE,
) -> list[dict]:
    run_id = str(uuid.uuid4())[:8]
    print(f"\nBenchmark run: {run_id}  model={model}  scenarios={len(scenarios)}")
    print(f"Cluster: {cluster_parent}")
    print("-" * 60)

    all_results = []

    for scenario in scenarios:
        scenario_dir = SCENARIOS_DIR / scenario
        if not scenario_dir.exists():
            print(f"\n[SKIP] {scenario} — directory not found")
            continue

        print(f"\n{'='*60}")
        print(f"Scenario: {scenario}")
        checker = CHECKERS.get(scenario)
        if not checker:
            print(f"  [SKIP] No checker registered for {scenario}")
            continue

        # 1. Deploy failing state
        print("  Deploying failing scenario...")
        if not apply_scenario(scenario_dir):
            continue

        # 2. Wait for broken state to stabilize
        print(f"  Waiting {eval_wait}s for state to stabilize...")
        time.sleep(eval_wait)

        # 3. Confirm it IS broken before letting agent run
        pre = checker()
        if pre.passed:
            print(f"  [WARN] Scenario is already passing before agent run: {pre.reason}")

        # 4. Run agent
        t0 = time.time()
        print(f"  Running agent ({model})...")
        if model == "kube-agents":
            run_kube_agents(scenario, cluster_parent, timeout=agent_timeout)
        else:
            print(f"  [INFO] Model '{model}' is not kube-agents — evaluate manually then press Enter")
            input("  Press Enter when agent has finished...")

        duration = time.time() - t0

        # 5. Evaluate
        result = checker()
        record = {
            "run_id": run_id,
            "scenario": scenario,
            "model": model,
            "attempt": 1,
            "passed": result.passed,
            "reason": result.reason,
            "duration_seconds": round(duration, 1),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.reason}")

        # 6. Append to results file
        with results_file.open("a") as f:
            f.write(json.dumps(record) + "\n")
        all_results.append(record)

        # 7. Optional teardown
        if teardown:
            print("  Tearing down...")
            teardown_scenario(scenario_dir)

    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="K8s DevOps benchmark runner")
    parser.add_argument("--model", default="kube-agents", help="Model/agent name to benchmark")
    parser.add_argument("--cluster", default="", help="GKE cluster parent: projects/P/locations/L/clusters/C")
    parser.add_argument("--scenarios", default="", help="Comma-separated scenario names (default: all)")
    parser.add_argument("--agent-timeout", type=int, default=300, help="Agent timeout per scenario (seconds)")
    parser.add_argument("--eval-wait", type=int, default=30, help="Seconds to wait after deploy before eval")
    parser.add_argument("--teardown", action="store_true", help="Delete namespaces after each scenario")
    parser.add_argument("--cleanup", action="store_true", help="Delete all benchmark namespaces and exit")
    parser.add_argument("--deploy-only", action="store_true", help="Deploy scenarios but don't run agent")
    parser.add_argument("--score-only", metavar="FILE", help="Score an existing results JSONL file")
    parser.add_argument("--results", default=str(RESULTS_FILE), help="Results JSONL file path")
    args = parser.parse_args()

    results_file = Path(args.results)

    if args.score_only:
        path = Path(args.score_only)
        results = load_results(path)
        scores = score(results)
        print_report(scores)
        return

    if args.cleanup:
        print("Cleaning up all benchmark namespaces...")
        cleanup_all()
        return

    # Resolve scenario list
    available = sorted(d.name for d in SCENARIOS_DIR.iterdir() if d.is_dir())
    if args.scenarios:
        requested = [s.strip() for s in args.scenarios.split(",")]
        scenarios = [s for s in available if any(s.startswith(r) for r in requested)]
    else:
        scenarios = available

    if not scenarios:
        print("No scenarios found. Run from repo root or check benchmark/scenarios/", file=sys.stderr)
        sys.exit(1)

    if args.deploy_only:
        print(f"Deploying {len(scenarios)} scenarios...")
        for scenario in scenarios:
            scenario_dir = SCENARIOS_DIR / scenario
            print(f"\n{scenario}")
            apply_scenario(scenario_dir)
        print("\nDone. Use --score-only to evaluate after agent runs.")
        return

    results = run_benchmark(
        model=args.model,
        scenarios=scenarios,
        cluster_parent=args.cluster,
        agent_timeout=args.agent_timeout,
        eval_wait=args.eval_wait,
        teardown=args.teardown,
        results_file=results_file,
    )

    scores = score(results)
    print_report(scores)


if __name__ == "__main__":
    main()
