#!/usr/bin/env python3
"""
Creates a GitHub Issue summarizing the last 7 days of ZERV sales, using
data/sales.csv and data/summary.json (which sync_sales.py should have
already refreshed earlier in the same workflow run).

Uses the workflow's built-in GITHUB_TOKEN (auto-provided by GitHub Actions)
so no extra secret is needed for this step.

Required environment variables (all provided automatically inside a
GitHub Actions job, except GITHUB_TOKEN which needs `issues: write`
permission granted in the workflow file):
  GITHUB_TOKEN
  GITHUB_REPOSITORY   e.g. "zervceo/Gmoney"
"""
import csv
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "sales.csv")
SUMMARY_PATH = os.path.join(REPO_ROOT, "data", "summary.json")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_week_rows():
    if not os.path.exists(CSV_PATH):
        return []
    since = datetime.now(timezone.utc) - timedelta(days=7)
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if _parse(r["created_at"]) >= since]


def load_summary():
    if not os.path.exists(SUMMARY_PATH):
        return {}
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_body(week_rows, summary):
    d7 = summary.get("last_7_days", {"orders": 0, "revenue": 0})
    all_time = summary.get("all_time", {"orders": 0, "revenue": 0, "currency": "USD"})
    currency = all_time.get("currency", "USD")

    lines = [
        f"**Orders this week:** {d7.get('orders', 0)}",
        f"**Revenue this week:** ${d7.get('revenue', 0):,.2f} {currency}",
        f"**All-time revenue:** ${all_time.get('revenue', 0):,.2f} {currency} across {all_time.get('orders', 0)} orders",
        "",
        "### Orders",
        "",
        "| Order | Date | Customer | Total | Status |",
        "|---|---|---|---|---|",
    ]
    if week_rows:
        for r in sorted(week_rows, key=lambda r: r["created_at"], reverse=True):
            lines.append(
                f"| {r['order_name']} | {r['created_at'][:10]} | {r['customer']} | "
                f"${float(r['total_price'] or 0):,.2f} | {r['financial_status']} |"
            )
    else:
        lines.append("| _no orders this week_ | | | | |")

    lines += [
        "",
        "---",
        "_Posted automatically by the weekly-report workflow._",
    ]
    return "\n".join(lines)


def create_issue(title, body):
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
    payload = json.dumps({"title": title, "body": body, "labels": ["weekly-report"]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print(f"Created issue #{result.get('number')}: {result.get('html_url')}")


def main():
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("GITHUB_TOKEN / GITHUB_REPOSITORY not set — are we in Actions?")
        return

    week_rows = load_week_rows()
    summary = load_summary()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"Weekly sales report — {today}"
    body = build_body(week_rows, summary)
    create_issue(title, body)


if __name__ == "__main__":
    main()
