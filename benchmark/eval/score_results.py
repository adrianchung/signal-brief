"""
Benchmark scoring — reads a JSONL results file and prints a report.

Each line in the results file is a JSON object:
{
  "run_id": str,
  "scenario": str,
  "model": str,
  "attempt": int,
  "passed": bool,
  "reason": str,
  "duration_seconds": float,
  "timestamp": str
}
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


DIFFICULTY = {
    "01-crashloop":                 "easy",
    "02-oom-killed":                "easy",
    "03-image-pull-error":          "easy",
    "04-pending-unschedulable":     "easy",
    "05-service-selector-mismatch": "medium",
    "06-quota-exceeded":            "medium",
    "07-missing-probes":            "medium",
    "08-rbac-violation":            "hard",
    "09-node-affinity-impossible":  "hard",
    "10-configmap-missing":         "hard",
}

SKILLS_TESTED = {
    "01-crashloop":                 ["gke-reliability", "gke-observability"],
    "02-oom-killed":                ["gke-workload-scaling", "gke-reliability"],
    "03-image-pull-error":          ["gke-observability"],
    "04-pending-unschedulable":     ["gke-workload-scaling", "gke-reliability"],
    "05-service-selector-mismatch": ["gke-networking-edge", "gke-observability"],
    "06-quota-exceeded":            ["gke-workload-scaling", "gke-cost-analysis"],
    "07-missing-probes":            ["gke-reliability", "gke-productionize"],
    "08-rbac-violation":            ["gke-workload-security", "review-security-k8s-rbac"],
    "09-node-affinity-impossible":  ["gke-reliability", "gke-workload-scaling"],
    "10-configmap-missing":         ["gke-reliability", "gke-observability"],
}


def load_results(path: Path) -> list[dict]:
    results = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def score(results: list[dict]) -> dict:
    by_model: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "passed": 0, "by_difficulty": defaultdict(lambda: {"total": 0, "passed": 0}),
        "by_skill": defaultdict(lambda: {"total": 0, "passed": 0}),
        "scenarios": {},
    })

    # Take the best attempt per (model, scenario)
    best: dict[tuple, dict] = {}
    for r in results:
        key = (r["model"], r["scenario"])
        if key not in best or (r["passed"] and not best[key]["passed"]):
            best[key] = r

    for (model, scenario), r in best.items():
        m = by_model[model]
        m["total"] += 1
        if r["passed"]:
            m["passed"] += 1

        diff = DIFFICULTY.get(scenario, "unknown")
        m["by_difficulty"][diff]["total"] += 1
        if r["passed"]:
            m["by_difficulty"][diff]["passed"] += 1

        for skill in SKILLS_TESTED.get(scenario, []):
            m["by_skill"][skill]["total"] += 1
            if r["passed"]:
                m["by_skill"][skill]["passed"] += 1

        m["scenarios"][scenario] = {"passed": r["passed"], "reason": r["reason"]}

    return dict(by_model)


def print_report(scores: dict) -> None:
    print("\n" + "=" * 70)
    print("  K8s DevOps Benchmark — Results")
    print("=" * 70)

    for model, data in sorted(scores.items()):
        pct = data["passed"] / data["total"] * 100 if data["total"] else 0
        print(f"\nModel: {model}")
        print(f"  Overall: {data['passed']}/{data['total']} ({pct:.0f}%)")

        print("  By difficulty:")
        for diff in ("easy", "medium", "hard"):
            d = data["by_difficulty"].get(diff, {"total": 0, "passed": 0})
            if d["total"]:
                dp = d["passed"] / d["total"] * 100
                print(f"    {diff:6s}: {d['passed']}/{d['total']} ({dp:.0f}%)")

        print("  By skill:")
        for skill, sd in sorted(data["by_skill"].items()):
            sp = sd["passed"] / sd["total"] * 100 if sd["total"] else 0
            print(f"    {skill:40s}: {sd['passed']}/{sd['total']} ({sp:.0f}%)")

        print("  Scenarios:")
        for scenario in sorted(data["scenarios"]):
            s = data["scenarios"][scenario]
            icon = "✓" if s["passed"] else "✗"
            print(f"    {icon} {scenario}: {s['reason'][:60]}")

    print()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("benchmark/results.jsonl")
    if not path.exists():
        print(f"Results file not found: {path}", file=sys.stderr)
        sys.exit(1)
    results = load_results(path)
    scores = score(results)
    print_report(scores)
