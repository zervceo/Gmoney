# Gmoney

Automated sales tracking for **ZERV**, pulling straight from Shopify. No manual logging — a scheduled GitHub Action syncs orders, updates a running CSV, regenerates a dashboard, and posts a weekly summary as a GitHub Issue.

## What's in here

- `data/sales.csv` — every order, one row each, appended automatically.
- `data/summary.json` — rolled-up totals (all-time, last 7 days, last 30 days, by month, top products).
- `docs/index.html` — a dashboard page (served via GitHub Pages) showing revenue charts and recent orders.
- `scripts/sync_sales.py` — pulls new orders from the Shopify Admin API and updates `data/`.
- `scripts/generate_dashboard.py` — rebuilds `docs/index.html` from `data/`.
- `scripts/weekly_report.py` — opens a GitHub Issue summarizing the past 7 days.
- `.github/workflows/sync-sales.yml` — runs the sync + dashboard rebuild every 6 hours (and on demand).
- `.github/workflows/weekly-report.yml` — runs every Monday and posts the weekly summary issue.
- `.github/ISSUE_TEMPLATE/sales-goal.yml` — a form for logging a sales goal as an Issue, so you can track progress toward it.

## One-time setup

### 1. Create a Shopify Admin API token

In your Shopify admin: **Settings → Apps and sales channels → Develop apps → Create an app**. Name it something like "Gmoney sync". Under **Configuration → Admin API integration**, grant the `read_orders` scope. Install the app, then copy the **Admin API access token** shown (starts with `shpat_`) — Shopify only shows it once.

### 2. Add repo secrets

In this repo on GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Name | Value |
|---|---|
| `SHOPIFY_STORE_DOMAIN` | your store's `*.myshopify.com` domain |
| `SHOPIFY_ADMIN_TOKEN` | the `shpat_...` token from step 1 |

`GITHUB_TOKEN` used by the workflows is provided automatically by GitHub Actions — nothing to add there.

### 3. Enable GitHub Pages for the dashboard

**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / folder: `/docs`**. Save. Your dashboard will be live at `https://<your-username>.github.io/Gmoney/` within a minute or two of the next sync.

### 4. Kick off the first sync

Once the secrets are set, go to **Actions → Sync Shopify sales → Run workflow** to trigger it manually the first time (otherwise it'll just wait for its next 6-hour schedule). It'll pull orders from the last 90 days, populate `data/sales.csv` and `data/summary.json`, and rebuild the dashboard.

## Tracking goals

Open a new Issue using the **Sales Goal** template to set a target (e.g. "$10,000 in a month") with a deadline. Check back against `docs/index.html` or `data/summary.json` to see how you're tracking.

## Notes

- The sync script only looks back 90 days per run to keep things fast; since it appends and skips duplicates, running it repeatedly is always safe.
- If you ever need to pull further back than 90 days (e.g. first-ever backfill covering older history), widen the `since` window in `scripts/sync_sales.py` for a one-off manual run.
