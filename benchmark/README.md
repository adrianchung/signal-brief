# K8s DevOps Benchmark

A set of deliberately broken Kubernetes scenarios for benchmarking AI agents
against real-world GKE DevOps failures. Designed to test and score the
[kube-agents](https://github.com/gke-labs/kube-agents) framework.

## Scenario Inventory

| # | Name | Difficulty | Skills Tested |
|---|------|-----------|---------------|
| 01 | CrashLoopBackOff container | Easy | gke-reliability, gke-observability |
| 02 | OOMKilled — memory limit too low | Easy | gke-workload-scaling, gke-reliability |
| 03 | ImagePullBackOff — bad image ref | Easy | gke-observability |
| 04 | Pending/Unschedulable — CPU overrequest | Easy | gke-workload-scaling |
| 05 | Service selector mismatch | Medium | gke-networking-edge, gke-observability |
| 06 | Namespace quota exceeded | Medium | gke-workload-scaling, gke-cost-analysis |
| 07 | Missing health probes + HPA | Medium | gke-reliability, gke-productionize |
| 08 | RBAC violation — no pod list permission | Hard | gke-workload-security |
| 09 | Impossible node affinity + taint | Hard | gke-reliability, gke-workload-scaling |
| 10 | Missing ConfigMap + Secret | Hard | gke-reliability, gke-observability |

## Quick Start

### 1. Cluster setup

**With gcloud CLI:**
```bash
export GCP_PROJECT=your-project-id
bash benchmark/setup/install.sh
```

**With GKE MCP Server (no gcloud):**
```bash
python benchmark/setup/create_cluster_mcp.py --project your-project-id
# Then use the Claude Code MCP tools to create the cluster as instructed
```

After the cluster exists, configure kubectl:
```bash
gcloud container clusters get-credentials kube-benchmark \
  --project=your-project-id --region=us-central1
```

### 2. Deploy all failing scenarios

```bash
python benchmark/runner.py --deploy-only
```

This creates 10 namespaces (`bench-crashloop`, `bench-oom`, etc.) each with
a deliberately broken workload.

### 3. Run the kube-agents benchmark

```bash
python benchmark/runner.py \
  --model kube-agents \
  --cluster "projects/YOUR_PROJECT/locations/us-central1/clusters/kube-benchmark"
```

Or run a single scenario:
```bash
python benchmark/runner.py --model kube-agents --scenarios 01,05,08
```

### 4. Compare a baseline model

```bash
# Deploy scenarios then manually run your baseline model, then:
python benchmark/runner.py --model baseline --scenarios 01,02,03
# (prompts you to run agent manually for each scenario)
```

### 5. Score results

```bash
python benchmark/runner.py --score-only benchmark/results.jsonl
```

### 6. Clean up

```bash
python benchmark/runner.py --cleanup
```

---

## How Scoring Works

Each scenario is evaluated by a checker in `benchmark/eval/check_scenario.py`
that runs `kubectl` commands to verify the workload reached a healthy state.

Results are appended to `benchmark/results.jsonl` (one JSON object per run).
The scorer (`eval/score_results.py`) groups by model and reports:

- **Overall pass rate** (n/10)
- **By difficulty** (easy / medium / hard)
- **By skill area** (gke-reliability, gke-networking-edge, etc.)
- **Per-scenario** pass/fail with reason

---

## What "Default Model" Struggles With

A baseline LLM without cluster tool access or iterative reasoning will struggle
with scenarios 05–10, which require:

- Reading live cluster state across multiple resources
- Making a connection between symptom (pod not running) and root cause (selector mismatch, missing ConfigMap, RBAC, etc.)
- Applying a targeted fix and verifying it took effect
- Iterating when the first fix doesn't work

Scenarios 01–04 are deliberately easy enough for a simple prompt → command flow.

---

## kube-agents Integration

The `kube-agents-config/` directory contains:

- `SETTINGS.md` — operator agent cluster config (update with your project/cluster)
- `run_agent.sh` — invokes the Claude Code operator agent for one scenario
- `kube-agents/` — cloned from https://github.com/gke-labs/kube-agents (after install)

The runner calls `run_agent.sh` per scenario when `--model kube-agents` is set.

---

## Scenario Directory Layout

```
benchmark/
├── README.md               ← this file
├── runner.py               ← main benchmark runner
├── results.jsonl           ← benchmark results (appended per run)
├── scenarios/
│   ├── 01-crashloop/
│   │   ├── setup.yaml      ← deploys the broken state
│   │   └── README.md       ← problem description + expected fix
│   ├── 02-oom-killed/
│   │   └── ...
│   └── ...
├── eval/
│   ├── check_scenario.py   ← per-scenario pass/fail checkers
│   └── score_results.py    ← scoring + reporting
├── setup/
│   ├── install.sh          ← cluster + kube-agents setup (gcloud)
│   └── create_cluster_mcp.py ← MCP-based cluster creation helper
└── kube-agents-config/
    ├── SETTINGS.md         ← operator agent config
    └── run_agent.sh        ← agent invocation script
```
