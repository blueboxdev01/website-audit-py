# Workflow: Local SEO Audit

**Objective:** Generate a client-ready PDF audit report for a local business, showing their current Google local-pack rank, a comparison against the top 3 competitors, and prioritized recommendations.

## Required inputs

- Business name (as displayed on their GBP or website)
- City and state (e.g. `Newark, NJ`)

## Optional inputs

- `--service "<service type>"` — only needed when the business has no GBP
- `--output <path>` — override default save location
- `--no-cache` — force fresh API calls

## Setup (one-time)

1. Copy `.env.example` to `.env` and fill in `SERPAPI_KEY`. Get a free key at https://serpapi.com (100 searches/month on the free tier).
2. (Optional) Add `GOOGLE_PLACES_API_KEY` if you want the Places API fallback for missing fields.
3. Install dependencies: `pip install -r requirements.txt`
4. Install Playwright browser: `playwright install chromium`

## Running an audit

```bash
python tools/run_audit.py --company "Sunny Days Daycare" --city "Newark, NJ"
```

The report saves to `.tmp/reports/<company-slug>-<YYYY-MM-DD>.pdf`.

## Auditing a business with no GBP

```bash
python tools/run_audit.py \
  --company "Greenfield Daycare" \
  --city "Newark, NJ" \
  --service "daycare"
```

The tool will fail cleanly if the business has no GBP and `--service` is not provided. The error message will tell you what to do.

## API budget

Each audit consumes roughly **6 SerpApi calls**:
- 1 for business resolution
- 1 for the local pack
- 4 for place details (prospect + top 3 competitors)

On the free tier (100 calls/month), that's about 16 audits per month before hitting the limit. Cached responses are reused for 24 hours, so re-running the same audit doesn't burn additional credits.

## Known edge cases

- **Business not found** → re-run with `--service` to do a "no GBP" audit
- **Business not in top 20** → report still generates; the ranking section says "Not currently ranking"
- **Fewer than 3 competitors in local pack** → report uses what's available, noted in the methodology
- **SerpApi out of credits** → tool fails fast. Wait for the monthly reset or upgrade

## Lessons learned

(Empty for now. Add entries here as you run real audits and discover things.)
