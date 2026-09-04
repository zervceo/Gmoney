#!/usr/bin/env python3
"""
Pulls orders from the Shopify Admin GraphQL API and appends any new ones to
data/sales.csv, then recomputes data/summary.json.

Required environment variables:
  SHOPIFY_STORE_DOMAIN   e.g. "zerv-surf.myshopify.com"
  SHOPIFY_ADMIN_TOKEN    Admin API access token from a custom app
                         (needs the read_orders scope)

Safe to run repeatedly: it tracks the last synced order by date and will
only append orders newer than what's already in sales.csv.
"""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "sales.csv")
SUMMARY_PATH = os.path.join(REPO_ROOT, "data", "summary.json")

STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()
ADMIN_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
API_VERSION = "2025-01"

ORDERS_QUERY = """
query Orders($cursor: String, $query: String) {
  orders(first: 50, after: $cursor, sortKey: CREATED_AT, query: $query) {
    pageInfo { hasNextPage endCursor }
    edges {
      cursor
      node {
        id
        name
        createdAt
        displayFinancialStatus
        customer { displayName }
        currentTotalPriceSet { shopMoney { amount currencyCode } }
        lineItems(first: 5) { edges { node { title quantity } } }
      }
    }
  }
}
"""


def gql(query, variables):
    url = f"https://{STORE_DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": ADMIN_TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "errors" in payload:
        raise RuntimeError(f"Shopify GraphQL error: {payload['errors']}")
    return payload["data"]


def load_existing_order_ids():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return {row["order_id"] for row in csv.DictReader(f)}


def fetch_new_orders(existing_ids):
    """Fetch orders newest-first-ish via pagination, stop once we hit an
    order we've already recorded (orders only grow, so this bounds the walk)."""
    new_rows = []
    cursor = None
    # Shopify search query: only pull orders from the last 90 days to keep
    # each run cheap; a full backfill can be done by widening this window.
    since = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    search_query = f"created_at:>={since}"

    while True:
        data = gql(ORDERS_QUERY, {"cursor": cursor, "query": search_query})
        orders = data["orders"]
        for edge in orders["edges"]:
            node = edge["node"]
            order_id = node["id"]
            if order_id in existing_ids:
                continue
            money = node["currentTotalPriceSet"]["shopMoney"]
            items = node.get("lineItems", {}).get("edges", [])
            top_items = "; ".join(
                f'{i["node"]["title"]} x{i["node"]["quantity"]}' for i in items
            )
            new_rows.append(
                {
                    "order_id": order_id,
                    "order_name": node["name"],
                    "created_at": node["createdAt"],
                    "customer": (node.get("customer") or {}).get("displayName", "Guest"),
                    "financial_status": node.get("displayFinancialStatus", ""),
                    "currency": money["currencyCode"],
                    "total_price": money["amount"],
                    "line_item_count": len(items),
                    "top_line_items": top_items,
                }
            )
        if not orders["pageInfo"]["hasNextPage"]:
            break
        cursor = orders["pageInfo"]["endCursor"]
    return new_rows


def append_rows(rows):
    if not rows:
        return
    fieldnames = [
        "order_id",
        "order_name",
        "created_at",
        "customer",
        "financial_status",
        "currency",
        "total_price",
        "line_item_count",
        "top_line_items",
    ]
    file_exists = os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def recompute_summary():
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    all_time_orders = len(all_rows)
    all_time_revenue = sum(float(r["total_price"] or 0) for r in all_rows)
    currency = all_rows[0]["currency"] if all_rows else "USD"

    last7 = [r for r in all_rows if _parse(r["created_at"]) >= d7]
    last30 = [r for r in all_rows if _parse(r["created_at"]) >= d30]

    by_month = {}
    product_counts = {}
    for r in all_rows:
        dt = _parse(r["created_at"])
        key = dt.strftime("%Y-%m")
        month = by_month.setdefault(key, {"orders": 0, "revenue": 0.0})
        month["orders"] += 1
        month["revenue"] += float(r["total_price"] or 0)
        for item in (r.get("top_line_items") or "").split(";"):
            item = item.strip()
            if not item:
                continue
            title = item.rsplit(" x", 1)[0].strip()
            product_counts[title] = product_counts.get(title, 0) + 1

    top_products = sorted(product_counts.items(), key=lambda kv: -kv[1])[:10]

    summary = {
        "last_synced_at": now.isoformat(),
        "all_time": {
            "orders": all_time_orders,
            "revenue": round(all_time_revenue, 2),
            "currency": currency,
        },
        "last_7_days": {
            "orders": len(last7),
            "revenue": round(sum(float(r["total_price"] or 0) for r in last7), 2),
        },
        "last_30_days": {
            "orders": len(last30),
            "revenue": round(sum(float(r["total_price"] or 0) for r in last30), 2),
        },
        "by_month": {k: {"orders": v["orders"], "revenue": round(v["revenue"], 2)} for k, v in sorted(by_month.items())},
        "top_products": [{"title": t, "orders": c} for t, c in top_products],
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main():
    if not STORE_DOMAIN or not ADMIN_TOKEN:
        print(
            "SHOPIFY_STORE_DOMAIN and/or SHOPIFY_ADMIN_TOKEN are not set — "
            "add them as repo secrets. Skipping sync.",
            file=sys.stderr,
        )
        sys.exit(0)

    existing_ids = load_existing_order_ids()
    new_rows = fetch_new_orders(existing_ids)
    append_rows(new_rows)
    recompute_summary()
    print(f"Synced {len(new_rows)} new order(s).")


if __name__ == "__main__":
    main()
