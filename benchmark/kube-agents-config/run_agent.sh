#!/usr/bin/env bash
# Invoke the kube-agents operator against a single benchmark scenario.
# Called by benchmark/runner.py with: scenario namespace cluster_parent task

set -euo pipefail

SCENARIO="${1:-}"
NAMESPACE="${2:-}"
CLUSTER_PARENT="${3:-}"
TASK="${4:-Diagnose and fix the Kubernetes issue in the namespace.}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBE_AGENTS_DIR="${SCRIPT_DIR}/kube-agents"

if [[ ! -d "$KUBE_AGENTS_DIR" ]]; then
  echo "[ERROR] kube-agents not cloned. Run: benchmark/setup/install.sh first"
  exit 1
fi

echo "=== Running kube-agents operator ==="
echo "  Scenario : $SCENARIO"
echo "  Namespace: $NAMESPACE"
echo "  Cluster  : $CLUSTER_PARENT"
echo ""

# Write the task into the operator's memory so it knows what to work on
MEMORY_DIR="$KUBE_AGENTS_DIR/agents/operator/memory"
mkdir -p "$MEMORY_DIR"
cat > "$MEMORY_DIR/current-task.md" <<EOF
# Current Benchmark Task

**Scenario**: $SCENARIO
**Namespace**: $NAMESPACE
**Cluster**: $CLUSTER_PARENT

## Task

$TASK

## Instructions

1. Use kubectl and GKE MCP tools to inspect the namespace
2. Diagnose the root cause of the failure
3. Apply the minimum fix
4. Verify the workload is healthy
5. Write a brief summary of what you fixed to memory/task-result.md
EOF

# Update SETTINGS.md with the cluster
sed -i "s|projects/YOUR_PROJECT/locations/YOUR_REGION/clusters/kube-benchmark|${CLUSTER_PARENT}|g" \
  "$SCRIPT_DIR/SETTINGS.md" 2>/dev/null || true

# Run claude-code with the operator agent workspace
# The kube-agents operator agent workspace is at agents/operator/
claude --print \
  --system-prompt "$(cat "$KUBE_AGENTS_DIR/agents/operator/SOUL.md")" \
  --allowedTools "mcp__Custom_GKE_MCP_Server__*,Bash" \
  "$(cat "$MEMORY_DIR/current-task.md")" \
  2>&1

echo "=== Agent run complete ==="
