#!/usr/bin/env bash
# One-shot setup for the k8s DevOps benchmark environment.
# Run from the repo root: bash benchmark/setup/install.sh
#
# Requirements:
#   - gcloud CLI authenticated (gcloud auth login / application-default)
#   - GCP_PROJECT env var set (or pass as first argument)
#   - GKE_REGION env var set (default: us-central1)

set -euo pipefail

GCP_PROJECT="${1:-${GCP_PROJECT:-}}"
GKE_REGION="${GKE_REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-kube-benchmark}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BENCH_DIR="$REPO_ROOT/benchmark"
KUBE_AGENTS_DIR="$BENCH_DIR/kube-agents-config/kube-agents"

if [[ -z "$GCP_PROJECT" ]]; then
  echo "Usage: GCP_PROJECT=my-project bash benchmark/setup/install.sh"
  echo "   or: bash benchmark/setup/install.sh my-project"
  exit 1
fi

CLUSTER_PARENT="projects/${GCP_PROJECT}/locations/${GKE_REGION}/clusters/${CLUSTER_NAME}"
echo "=== K8s DevOps Benchmark Setup ==="
echo "  Project : $GCP_PROJECT"
echo "  Region  : $GKE_REGION"
echo "  Cluster : $CLUSTER_NAME"
echo "  Parent  : $CLUSTER_PARENT"
echo ""

# 1. Clone kube-agents
if [[ ! -d "$KUBE_AGENTS_DIR" ]]; then
  echo "[1/4] Cloning kube-agents..."
  git clone https://github.com/gke-labs/kube-agents.git "$KUBE_AGENTS_DIR"
else
  echo "[1/4] kube-agents already cloned at $KUBE_AGENTS_DIR"
  git -C "$KUBE_AGENTS_DIR" pull --ff-only 2>/dev/null || true
fi

# 2. Create GKE Autopilot cluster
echo "[2/4] Creating GKE Autopilot cluster (this takes ~5 minutes)..."
if gcloud container clusters describe "$CLUSTER_NAME" \
  --project="$GCP_PROJECT" --region="$GKE_REGION" &>/dev/null; then
  echo "  Cluster already exists — skipping creation"
else
  gcloud container clusters create-auto "$CLUSTER_NAME" \
    --project="$GCP_PROJECT" \
    --region="$GKE_REGION" \
    --release-channel=rapid
  echo "  Cluster created"
fi

# 3. Configure kubectl
echo "[3/4] Configuring kubectl..."
gcloud container clusters get-credentials "$CLUSTER_NAME" \
  --project="$GCP_PROJECT" \
  --region="$GKE_REGION"
kubectl cluster-info

# 4. Update SETTINGS.md with real cluster parent
echo "[4/4] Writing cluster config..."
sed -i "s|projects/YOUR_PROJECT/locations/YOUR_REGION/clusters/kube-benchmark|${CLUSTER_PARENT}|g" \
  "$BENCH_DIR/kube-agents-config/SETTINGS.md"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  Deploy failing scenarios:"
echo "    python benchmark/runner.py --deploy-only"
echo ""
echo "  Run kube-agents benchmark:"
echo "    python benchmark/runner.py --model kube-agents --cluster '${CLUSTER_PARENT}'"
echo ""
echo "  Score results:"
echo "    python benchmark/runner.py --score-only benchmark/results.jsonl"
