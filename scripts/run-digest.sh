#!/usr/bin/env bash
# Trigger the digest workflow on GitHub Actions and stream the result.
#
# Usage:
#   ./scripts/run-digest.sh              # use default provider (gemini)
#   ./scripts/run-digest.sh gemini
#   ./scripts/run-digest.sh claude

set -euo pipefail

REPO="adrianchung/signal-brief"
WORKFLOW="digest.yml"
PROVIDER="${1:-gemini}"

if [[ "$PROVIDER" != "gemini" && "$PROVIDER" != "claude" ]]; then
  echo "Error: provider must be 'gemini' or 'claude'" >&2
  exit 1
fi

echo "→ Triggering digest workflow (provider: $PROVIDER)..."
gh workflow run "$WORKFLOW" --repo "$REPO" --field "provider=$PROVIDER"

echo "→ Waiting for run to register..."
sleep 5

RUN_ID=$(gh run list \
  --repo "$REPO" \
  --workflow "$WORKFLOW" \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')

echo "→ Run ID: $RUN_ID"
echo "→ View at: https://github.com/$REPO/actions/runs/$RUN_ID"
echo ""

gh run watch "$RUN_ID" --repo "$REPO" --exit-status
