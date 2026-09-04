#!/usr/bin/env python3
"""
Renders docs/index.html from data/sales.csv and data/summary.json.
Pure stdlib — no dependencies beyond what sync_sales.py already needs.
Run this after sync_sales.py. GitHub Pages (configured to serve /docs)
picks up the result automatically once it's committed.
"""
import csv
import json
import os
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "sales.csv")
SUMMARY_PATH = os.path.join(REPO_ROOT, "data", "summary.json")
OUT_PATH = os.path.join(REPO_ROOT, "docs", "index.html")


def load_summary():
    if not os.path.exists(SUMMARY_PATH):
        return {}
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_recent_orders(limit=15):
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]


def money(amount, currency="USD"):
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render(summary, recent):
    all_time = summary.get("all_time", {"orders": 0, "revenue": 0, "currency": "USD"})
    d7 = summary.get("last_7_days", {"orders": 0, "revenue": 0})
    d30 = summary.get("last_30_days", {"orders": 0, "revenue": 0})
    by_month = summary.get("by_month", {})
    top_products = summary.get("top_products", [])
    last_synced = summary.get("last_synced_at")
    currency = all_time.get("currency", "USD")

    synced_label = (
        datetime.fromisoformat(last_synced).strftime("%b %d, %Y %H:%M UTC")
        if last_synced
        else "never — waiting on first sync"
    )

    rows_html = "".join(
        f"<tr><td>{esc(r['order_name'])}</td><td>{esc(r['created_at'][:10])}</td>"
        f"<td>{esc(r['customer'])}</td><td>{money(r['total_price'], r['currency'])}</td>"
        f"<td>{esc(r['financial_status'])}</td></tr>"
        for r in recent
    ) or '<tr><td colspan="5">No orders synced yet.</td></tr>'

    months_sorted = sorted(by_month.items())
    chart_labels = json.dumps([m for m, _ in months_sorted])
    chart_values = json.dumps([v["revenue"] for _, v in months_sorted])

    top_products_html = "".join(
        f"<tr><td>{esc(p['title'])}</td><td>{p['orders']}</td></tr>" for p in top_products
    ) or '<tr><td colspan="2">No product data yet.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ZERV — Gmoney Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#0b0c10; color:#eaeaea; margin:0; padding:2rem; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .sub {{ color:#9aa0a6; margin-top:0; }}
  .cards {{ display:flex; gap:1rem; flex-wrap:wrap; margin:2rem 0; }}
  .card {{ background:#16181d; border:1px solid #2a2d34; border-radius:12px; padding:1.25rem 1.5rem; min-width:180px; }}
  .card .label {{ color:#9aa0a6; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.04em; }}
  .card .value {{ font-size:1.8rem; font-weight:700; margin-top:0.25rem; }}
  table {{ width:100%; border-collapse: collapse; margin-top:1rem; }}
  th, td {{ text-align:left; padding:0.5rem 0.75rem; border-bottom:1px solid #2a2d34; font-size:0.9rem; }}
  th {{ color:#9aa0a6; font-weight:600; }}
  .grid {{ display:grid; grid-template-columns: 2fr 1fr; gap:2rem; margin-top:2rem; }}
  @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  canvas {{ max-height: 320px; }}
  footer {{ margin-top:2rem; color:#6b7078; font-size:0.8rem; }}
</style>
</head>
<body>
<h1>ZERV — Sales Dashboard</h1>
<p class="sub">Last synced: {esc(synced_label)}</p>
<div class="cards">
  <div class="card"><div class="label">All-time revenue</div><div class="value">{money(all_time.get('revenue', 0), currency)}</div></div>
  <div class="card"><div class="label">All-time orders</div><div class="value">{all_time.get('orders', 0)}</div></div>
  <div class="card"><div class="label">Last 7 days</div><div class="value">{money(d7.get('revenue', 0), currency)}</div></div>
  <div class="card"><div class="label">Last 30 days</div><div class="value">{money(d30.get('revenue', 0), currency)}</div></div>
</div>
<div class="grid">
  <div>
    <h2>Revenue by month</h2>
    <canvas id="revenueChart"></canvas>
  </div>
  <div>
    <h2>Top products</h2>
    <table>
      <thead><tr><th>Product</th><th>Orders</th></tr></thead>
      <tbody>{top_products_html}</tbody>
    </table>
  </div>
</div>
<h2>Recent orders</h2>
<table>
  <thead><tr><th>Order</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<footer>Generated automatically by scripts/generate_dashboard.py</footer>
<script>
new Chart(document.getElementById('revenueChart'), {{
  type: 'bar',
  data: {{
    labels: {chart_labels},
    datasets: [{{ label: 'Revenue', data: {chart_values}, backgroundColor: '#3ddc97' }}]
  }},
  options: {{
    scales: {{
      y: {{ ticks: {{ color: '#9aa0a6' }}, grid: {{ color: '#2a2d34' }} }},
      x: {{ ticks: {{ color: '#9aa0a6' }}, grid: {{ display: false }} }}
    }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});
</script>
</body>
</html>
"""


def main():
    summary = load_summary()
    recent = load_recent_orders()
    html = render(summary, recent)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
