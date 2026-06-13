"""
Create a GKE Autopilot cluster via the Custom GKE MCP Server
(for use in environments where gcloud CLI is unavailable).

Usage:
    python benchmark/setup/create_cluster_mcp.py --project my-project --region us-central1
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-central1", help="GCP region")
    parser.add_argument("--cluster", default="kube-benchmark", help="Cluster name")
    args = parser.parse_args()

    parent = f"projects/{args.project}/locations/{args.region}"
    cluster_parent = f"{parent}/clusters/{args.cluster}"

    cluster_config = {
        "name": args.cluster,
        "autopilot": {"enabled": True},
        "releaseChannel": {"channel": "RAPID"},
        "resourceLabels": {"benchmark": "true"},
    }

    print(f"Creating GKE Autopilot cluster via MCP:")
    print(f"  Parent : {parent}")
    print(f"  Cluster: {args.cluster}")
    print(f"  Config : {json.dumps(cluster_config, indent=2)}")
    print()
    print("NOTE: Call mcp__Custom_GKE_MCP_Server__create_cluster with:")
    print(f'  parent="{parent}"')
    print(f'  cluster=\'{json.dumps(cluster_config)}\'')
    print()
    print(f"Cluster parent for runner.py: {cluster_parent}")


if __name__ == "__main__":
    main()
