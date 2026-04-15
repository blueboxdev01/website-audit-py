# Local SEO Audit Tool — Design Spec

**Date:** 2026-04-10
**Status:** Approved for implementation planning
**Scope:** v1 — prospecting CLI tool for local SEO audits

## Purpose

A command-line tool that generates a client-ready PDF audit report for a local business. The report shows where the business currently ranks in Google's local pack, how it compares to the top 3 ranked competitors across Google Business Profile (GBP) signals, and a prioritized list of recommendations to improve rank.

The tool is a sales and prospecting aid. It is run manually by the operator against target businesses. The resulting PDF is sent to the prospect as a value-first lead magnet to open a conversation about GBP setup or optimization services.

## Target use cases

1. **Business has a Google Business Profile.** Report shows current rank, gap vs. top 3, and concrete optimizations.
2. **Business has no Google Business Profile.** Report shows "no GBP found," surfaces what the top 3 competitors are doing in GBP, and frames GBP setup as the first recommended engagement.

## Non-goals (explicitly out of scope for v1)

- Email delivery of the report (deferred; revisit once audit quality is validated)
- Batch mode / CSV ingestion
- Scheduled re-audits
- Client-facing web form or lead-capture UI
- Multi-language support
- Keyword opportunity analysis beyond the single derived query
- Organic (non-local-pack) rank tracking

## Inputs

### Required
- `--company "<business name>"` — e.g., `"Sunny Days Daycare"`
- `--city "<city, state>"` — e.g., `"Newark, NJ"`

### Optional
- `--service "<service type>"` — required only when no GBP exists for the business. Used to build the target search query when auto-detection from GBP category is not possible.
- `--output <path>` — override the default report save location.
- `--no-cache` — force fresh API calls and ignore the local response cache.

## Data sources

### Primary: SerpApi (free tier)
- 100 free searches per month.
- Used for business resolution, local pack ranking, and place detail enrichment.
- Credentials stored in `.env` as `SERPAPI_KEY`.

### Secondary: Google Places API (New)
- Free within Google's $200/month credit, which comfortably covers test volume.
- Used only as a fallback when SerpApi does not surface a needed field.
- Credentials stored in `.env` as `GOOGLE_PLACES_API_KEY`.

### Provider abstraction
All SERP calls go through a single module (`tools/serp_provider.py`) that exposes a stable interface (`find_business`, `get_local_pack`, `get_place_details`). This is the seam for swapping to a paid provider (DataForSEO, paid SerpApi tier, ScaleSerp, etc.) at launch without rewriting the rest of the system.

## High-level flow

1. Operator runs `python tools/run_audit.py --company "<name>" --city "<city>"`.
2. Tool resolves the business via SerpApi and extracts the GBP primary category.
3. Tool builds the target search query as `<category> <city>`. If no GBP is found and `--service` is not supplied, the tool stops with a clear message.
4. Tool pulls the local pack for the target query. Captures the prospect's rank position and the top 3 ranked competitors.
5. Tool enriches the prospect and each top-3 competitor with full place details (photos, reviews, posts, categories, attributes, services).
6. Tool runs gap analysis (pure Python, no API calls) to score each signal and produce a prioritized recommendations list.
7. Tool renders the Jinja2 HTML template with all data and converts to PDF via WeasyPrint.
8. Tool prints the final PDF path. Report is saved to `.tmp/reports/<company-slug>-<YYYY-MM-DD>.pdf`.

## Architecture (WAT framework)

### Workflows

**`workflows/audit_local_seo.md`** — the operator-facing SOP. Documents objective, required inputs, tool execution order, expected outputs, known edge cases, and lessons learned as they accumulate.

### Tools

**`tools/run_audit.py`** — entry point and orchestrator.
- Parses CLI arguments.
- Calls `serp_provider`, `gbp_enricher`, `gap_analyzer`, `report_generator` in sequence.
- Handles fail-fast errors and prints the final PDF path on success.

**`tools/serp_provider.py`** — data-source abstraction.
- `find_business(company, city) -> BusinessResult | None`
- `get_local_pack(query, city) -> list[BusinessResult]`
- `get_place_details(place_id) -> PlaceDetails`
- Implements SerpApi today; future paid providers plug in behind the same interface.
- All raw responses are written to `.tmp/cache/<place_id_or_query_hash>.json` and reused for 24 hours unless `--no-cache` is set.

**`tools/gbp_enricher.py`** — cross-source field filler.
- Given a partial `PlaceDetails`, calls the Google Places API (New) to backfill any missing fields that SerpApi did not return.
- Only runs for fields that are blank; no unconditional second calls.

**`tools/gap_analyzer.py`** — pure-Python scoring layer.
- Input: prospect signals + top-3 competitor signals.
- Output: structured analysis object with per-signal scores, gaps, and a prioritized recommendations list.
- No I/O, no API calls. Deterministic and unit-testable.

**`tools/report_generator.py`** — PDF rendering.
- Takes the analysis object and raw signals.
- Renders `templates/report.html.j2` via Jinja2.
- Converts HTML to PDF via WeasyPrint.
- Saves to `.tmp/reports/<company-slug>-<YYYY-MM-DD>.pdf`.
- On failure, writes the rendered HTML next to the intended PDF path for debugging.

### Templates

**`templates/report.html.j2`** — HTML structure of the report, with Jinja2 placeholders for all dynamic data.

**`templates/report.css`** — separate stylesheet. Design changes touch this file only, not the template logic.

### Config

**`.env`** — `SERPAPI_KEY`, `GOOGLE_PLACES_API_KEY`. No secrets anywhere else.

## Data flow and API budget

Per audit:

| Step | API | Calls |
|------|-----|-------|
| Resolve business | SerpApi Google Maps (search) | 1 |
| Pull local pack | SerpApi Google Maps (search) | 1 |
| Enrich 4 businesses (prospect + top 3) | SerpApi Google Maps (place details) | up to 4 |
| Backfill missing fields | Google Places API (New) | 0 in most cases, up to 4 if needed |
| Gap analysis | none | 0 |
| PDF render | none | 0 |

**Total: ~6 SerpApi calls per audit.** On the 100 calls/month free tier, that supports roughly 16 full audits per month. Sufficient for the test phase. A paid tier is expected before launch.

## Gap analysis signals

The analyzer scores the prospect against the top 3 competitors across the following dimensions. All of these drive the recommendations section of the report.

1. **Profile completeness** — presence of name, address, phone, hours, website, description.
2. **Category coverage** — primary and secondary category alignment vs. competitors.
3. **Photos** — count, freshness, variety (interior, exterior, team, products).
4. **Reviews** — total count, average rating, response rate, recency.
5. **Posts and updates** — presence and recency of GBP posts.
6. **Q&A** — whether the owner has answered questions.
7. **Services and products** — itemized service list presence.
8. **Attributes** — accessibility, amenities, payment methods, hours-of-operation completeness.
9. **NAP consistency** — business name, address, and phone match between GBP and the business website.
10. **Local pack rank** — current position for the target query.

For each signal, the analyzer computes a gap score (prospect vs. top-3 average and top-3 best) and assigns an impact weight. Signals with the largest gap-weight product surface at the top of the recommendations list.

## PDF report structure (client-facing)

The PDF contains exactly these sections, in this order:

1. **Cover page** — business name, city, audit date, title ("Local SEO Audit Report").
2. **Executive summary** — one page with the 3–5 biggest findings and the headline recommendation.
3. **Current local pack ranking** — where the business shows for the target query, or "Not ranking in top 20" if absent.
4. **GBP status** — existence, claimed state, completeness, missing fields.
5. **Competitor comparison** — side-by-side table of the prospect vs. the top 3 competitors across all signals.
6. **Gap analysis** — visual or bulleted breakdown of where the prospect falls behind.
7. **Prioritized recommendations** — ranked by impact; quick wins first, larger projects below.
8. **Next steps / call to action** — engagement pitch.

Internal analysis (scoring detail, raw signal dumps, methodology notes) stays out of the client PDF and lives only in the intermediate data files under `.tmp/`.

## Error handling and edge cases

1. **Business not found.** Tool exits with a clear message instructing the operator to re-run with `--service` to proceed with a "no GBP" audit.
2. **Business found but not in the local pack top 20.** Report still generates; the ranking section says "Not ranking in top 20" and recommendations lean on GBP foundations.
3. **Fewer than 3 competitors returned.** Report uses the available competitors and notes the reduced sample in the methodology footer.
4. **SerpApi rate-limited or out of credits.** Tool fails fast with a clear message. No partial reports are produced.
5. **Places API fallback fails.** Tool continues. Missing fields appear in the report as "Data unavailable."
6. **PDF render fails.** Tool writes the rendered HTML next to the intended PDF path so the template can be debugged without re-hitting any API.

## Caching

- Raw API responses are stored in `.tmp/cache/` keyed by place_id or query hash.
- Default cache lifetime: 24 hours.
- `--no-cache` forces fresh calls.
- Cache is regeneration-safe: deleting `.tmp/cache/` never breaks anything.

## Testing approach

- **Manual validation.** Before iterating, run the tool against at least three known businesses: one with a strong GBP, one with a weak GBP, one with no GBP. Verify the report against reality.
- **Fixture-based unit tests.** Raw API responses from validated runs are committed under `fixtures/` and used to unit-test `gap_analyzer.py` and `report_generator.py` without hitting live APIs.
- **Smoke-test loop.** Once fixtures are in place, template and scoring changes can be iterated on in seconds.

## File structure

```
website-audit/
├── .env                      # API keys (gitignored)
├── .tmp/
│   ├── cache/                # Raw API responses, keyed by place_id/query hash
│   └── reports/              # Generated PDFs
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-10-local-seo-audit-tool-design.md
├── fixtures/                 # Committed API response snapshots for tests
├── templates/
│   ├── report.html.j2
│   └── report.css
├── tools/
│   ├── run_audit.py          # Orchestrator / entry point
│   ├── serp_provider.py      # SerpApi wrapper + provider abstraction
│   ├── gbp_enricher.py       # Places API fallback for missing fields
│   ├── gap_analyzer.py       # Pure Python scoring
│   └── report_generator.py   # Jinja2 + WeasyPrint
├── workflows/
│   └── audit_local_seo.md
└── CLAUDE.md
```

## Open questions for implementation planning

- Exact scoring weights for each gap signal. These will be tuned empirically during the first few manual validation runs.
- Visual design of the PDF (color palette, typography, table layout). Initial version targets clean and professional; iteration happens after the first real audit is reviewed.
- Whether to expose a `--dry-run` flag that uses fixtures only. Likely yes, but not blocking v1.
