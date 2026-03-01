#!/usr/bin/env python3
"""
GitHub issue triage script for signal-brief.

Creates labels, milestones, and applies them to open issues.

Usage:
    export GITHUB_TOKEN=<your_personal_access_token>
    python scripts/github_triage.py

Requires 'repo' scope on the token.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

REPO = "adrianchung/signal-brief"
BASE_URL = f"https://api.github.com/repos/{REPO}"

# Labels to create (name -> color, description)
LABELS = {
    "enhancement": ("#a2eeef", "New feature or improvement"),
    "bug": ("#d73a4a", "Something isn't working"),
    "dx": ("#f9d0c4", "Developer experience — setup, tooling, tests, docs"),
    "infrastructure": ("#e4e669", "Deployment, containers, CI/CD"),
    "quick-win": ("#0075ca", "Small effort, high impact — ship first"),
}

# Milestones to create (title -> description)
MILESTONES = {
    "v1 — core value": "Minimum feature set for a fully working, useful signal brief service",
    "backlog": "Good ideas for after v1 ships",
}

# Issue assignments: issue_number -> {labels, milestone}
ISSUE_TRIAGE = {
    1:  {"labels": ["enhancement", "quick-win"], "milestone": "v1 — core value"},
    2:  {"labels": ["enhancement", "quick-win"], "milestone": "v1 — core value"},
    3:  {"labels": ["enhancement"],              "milestone": "v1 — core value"},
    4:  {"labels": ["enhancement"],              "milestone": "v1 — core value"},
    5:  {"labels": ["enhancement"],              "milestone": "v1 — core value"},
    6:  {"labels": ["enhancement"],              "milestone": "backlog"},
    7:  {"labels": ["enhancement"],              "milestone": "backlog"},
    8:  {"labels": ["enhancement"],              "milestone": "backlog"},
    9:  {"labels": ["enhancement"],              "milestone": "backlog"},
    10: {"labels": ["infrastructure"],           "milestone": "v1 — core value"},
    11: {"labels": ["dx"],                       "milestone": "v1 — core value"},
    13: {"labels": ["dx"],                       "milestone": "backlog"},
    14: {"labels": ["dx"],                       "milestone": "backlog"},
    15: {"labels": ["dx"],                       "milestone": "backlog"},
}


def api(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()) if resp.read.__self__.length != 0 else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        if e.code == 422:  # Unprocessable — resource already exists
            return {"already_exists": True, "detail": body_text}
        print(f"HTTP {e.code} {method} {url}: {body_text}", file=sys.stderr)
        raise


def ensure_labels() -> dict[str, str]:
    """Create missing labels. Returns name -> node_id map."""
    print("=== Labels ===")
    existing = {l["name"]: l for l in api("GET", "/labels?per_page=100")}
    result = {}
    for name, (color, description) in LABELS.items():
        if name in existing:
            print(f"  [ok] {name}")
            result[name] = existing[name]["name"]
        else:
            api("POST", "/labels", {"name": name, "color": color.lstrip("#"), "description": description})
            print(f"  [+]  {name}")
            result[name] = name
        time.sleep(0.1)
    return result


def ensure_milestones() -> dict[str, int]:
    """Create missing milestones. Returns title -> number map."""
    print("\n=== Milestones ===")
    existing = {m["title"]: m["number"] for m in api("GET", "/milestones?state=all&per_page=50")}
    result = {}
    for title, description in MILESTONES.items():
        if title in existing:
            print(f"  [ok] {title}")
            result[title] = existing[title]
        else:
            m = api("POST", "/milestones", {"title": title, "description": description})
            print(f"  [+]  {title}")
            result[title] = m["number"]
        time.sleep(0.1)
    return result


def triage_issues(milestone_map: dict[str, int]) -> None:
    print("\n=== Issues ===")
    for issue_num, config in sorted(ISSUE_TRIAGE.items()):
        labels = config["labels"]
        milestone_title = config["milestone"]
        milestone_num = milestone_map[milestone_title]
        api("PATCH", f"/issues/{issue_num}", {
            "labels": labels,
            "milestone": milestone_num,
        })
        label_str = ", ".join(labels)
        print(f"  #{issue_num:>2}  [{label_str}]  →  {milestone_title}")
        time.sleep(0.15)


def main() -> None:
    print(f"Triaging issues for {REPO}\n")
    ensure_labels()
    milestone_map = ensure_milestones()
    triage_issues(milestone_map)
    print("\nDone.")


if __name__ == "__main__":
    main()
