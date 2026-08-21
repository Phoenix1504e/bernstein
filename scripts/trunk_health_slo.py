"""Compute the main-branch red-rate for the Trunk Health SLO gate.

Ports the inline shell logic from `.github/workflows/trunk-health-slo.yml`
into a testable Python script. Fixes the population sampling by querying
the CI workflow's own runs endpoint, excludes cancelled/skipped runs, and
enforces a minimum sample size before toggling the marker.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

MIN_SAMPLE_SIZE = 10


def fetch_ci_runs(repo: str, token: str, since: datetime) -> list[dict]:
    """Fetch CI workflow runs on main since the given timestamp."""
    # Query the workflow by file path (ci.yml) to avoid crowding by other workflows
    url = f"https://api.github.com/repos/{repo}/actions/workflows/ci.yml/runs?branch=main&per_page=100"
    req = Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
    
    runs: list[dict] = []
    with urlopen(req) as resp:
        data = json.load(resp)
    
    for run in data.get("workflow_runs", []):
        created_at_str = run.get("created_at", "")
        if not created_at_str:
            continue
        # Parse ISO 8601 (e.g., "2026-08-20T12:34:56Z")
        dt = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if dt < since:
            continue
        
        conclusion = run.get("conclusion")
        # Exclude cancelled and skipped from both numerator and denominator
        if conclusion in ("cancelled", "skipped"):
            continue
            
        runs.append(run)
        
    return runs


def score_runs(runs: list[dict]) -> tuple[int, int, int]:
    """Score the runs, returning (total, red, red_pct)."""
    # Exclude cancelled and skipped from both numerator and denominator
    valid_runs = [r for r in runs if r.get("conclusion") not in ("cancelled", "skipped")]
    total = len(valid_runs)
    red = sum(1 for r in valid_runs if r.get("conclusion") in ("failure", "timed_out"))
    red_pct = (red * 100) // total if total > 0 else 0
    return total, red, red_pct

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--threshold-pct", type=int, default=5)
    parser.add_argument("--lookback-hours", type=int, default=24)
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(hours=args.lookback_hours)
    runs = fetch_ci_runs(args.repo, args.token, since)
    total, red, red_pct = score_runs(runs)

    insufficient = total < MIN_SAMPLE_SIZE
    unstable = (not insufficient) and (red_pct >= args.threshold_pct)

    # Output for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    output_lines = [
        f"total={total}",
        f"red={red}",
        f"red_pct={red_pct}",
        f"unstable={str(unstable).lower()}",
        f"insufficient_sample={str(insufficient).lower()}",
    ]

    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write("\n".join(output_lines) + "\n")
    else:
        print("\n".join(output_lines))


if __name__ == "__main__":
    main()
