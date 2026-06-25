# Timex Watch Finder

## Build Plan

### What I'm building

A personal vintage Timex aggregator. It pulls listings from eBay, Etsy, Chrono24, and Kijiji, filters out junk automatically, and uses Claude AI to enrich each listing with a structured summary and key attributes (model, movement, era). Results surface in a Streamlit UI where I can browse, filter, save, and act on good finds quickly.

### Why

Vintage Timex hunting is a timing problem. Good listings — correct dial condition, right model, reasonable price — appear and sell within hours across four different marketplaces. Checking all of them manually every day means either missing things or spending time I don't want to spend. The collector has three specific reference watches that define "interesting" (a 1972 Marlin, a second Marlin variant, a 1960s Electric). The taste is defined; what's missing is automation.

### How

**Phase 1 — Data layer.** Four marketplace adapters (`adapters/`) each expose one function: `fetch_listings(query, max_results)`. eBay uses the official Browse API with OAuth credentials. Etsy and Chrono24 use HTML scraping (no public API available). Kijiji is stubbed pending a viable fetch path. All adapters return listings in a standard dict format so the rest of the system doesn't care which marketplace a listing came from.

**Phase 2 — Filtering.** A fast keyword pass (`filters.py`) cuts obvious junk — broken watches, parts lots, over-budget listings — before any AI is involved. This runs in milliseconds and eliminates 30–40% of listings, keeping API costs low.

**Phase 3 — Storage.** Listings that pass the filter are written to SQLite (`db.py`). `INSERT OR IGNORE` means deduplication is free — a listing seen twice just doesn't insert the second time.

**Phase 4 — AI enrichment.** `enricher.py` sends each new listing to Claude Haiku to produce: a 4–6 sentence editorial summary covering condition, movement, dial, strap, and any red flags; and structured fields for movement type, era, model, and size. This runs concurrently (8 workers) after each sync so it doesn't block the UI.

**Phase 5 — UI.** Streamlit (`app.py`) renders a feed of enriched listings with sidebar filters (price, source, movement, era, model), pagination, a card modal with the AI summary, and a shortlist. The visual design is intentionally editorial — Newsreader serif for display, Geist for UI chrome, near-black on near-white.

**Sync schedule.** APScheduler runs a background sync every 30 minutes. The UI also exposes a manual "Sync now" button in the top nav.

Full design rationale lives in [`docs/superpowers/specs/2026-06-23-timex-aggregator-design.md`](docs/superpowers/specs/2026-06-23-timex-aggregator-design.md). The implementation plan is in [`docs/superpowers/plans/2026-06-23-timex-aggregator.md`](docs/superpowers/plans/2026-06-23-timex-aggregator.md).

---

## What it does

- Fetches listings from **eBay, Etsy, Chrono24, and Kijiji** on a 30-minute schedule
- Cuts obvious junk in a fast keyword pass before any AI is involved
- Uses **Claude Haiku** to enrich each listing with a summary and structured attributes
- Surfaces results in a clean **Streamlit UI** with sidebar filters, pagination, and a shortlist
- Lets you save listings to a shortlist and come back to them later

## Architecture

```
adapters/       eBay (Browse API), Etsy (scraper), Chrono24 (JSON-LD), Kijiji (stub)
filters.py      Hard filters — keyword blocklist, price ceiling, shipping logic
enricher.py     AI enrichment — editorial summary, movement, era, model detection
sync.py         Orchestration — fetch → filter → store → enrich (8 concurrent workers)
db.py           SQLite — listings, favourites, enrichment data, preferences
app.py          Streamlit UI — feed, shortlist, sidebar filters, listing modal
seed.py         One-time DB seed from a JSON file
```

## How enrichment works

Each listing that passes the filter gets sent to **Claude Haiku** with its title, description, and price. Claude returns:

- **Summary** — 4–6 sentences covering movement, case, dial, strap, condition, and any red flags
- **Movement** — Mechanical / Automatic / Quartz / Electric
- **Era** — 1950s through 1990s+
- **Model** — Marlin, Viscount, Electric, Weekender, etc.
- **Size** — Men's / Women's (only when explicitly stated in the listing)

Enrichment runs concurrently after each sync using a thread pool. The UI shows the summary and detected attributes directly on the card.

## Marketplace methods

| Source | Method | Notes |
|---|---|---|
| eBay | Browse API (OAuth) | Official API, EBAY_CA marketplace, watches category |
| Etsy | HTML scraper | No public API; degrades gracefully to empty list |
| Chrono24 | JSON-LD scraper | Parses structured data embedded in search page |
| Kijiji | Stub | Dropped RSS support; returns `[]` until viable fetch path found |

## Tradeoffs

- **Etsy and Chrono24 use scrapers, not official APIs.** No public API available for either. The adapter pattern means swapping to official APIs later is a one-file change.
- **No authentication.** This runs locally for one user. Multi-user support would require a backend and sessions — out of scope.
- **USD → CAD conversion uses a fixed rate (1.38).** Good enough for a $50 CAD budget threshold; a live rate API would be the v2 upgrade.
- **Kijiji is stubbed out.** Kijiji dropped RSS support and serves JS-rendered HTML with no viable free fetch path.

## Running locally

```bash
# 1. Clone
git clone https://github.com/nasahb/AR-Timex
cd AR-Timex

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys
cp .env.example .env
# Edit .env and add your keys (see table below)

# 4. Run
streamlit run app.py
```

The app auto-syncs on first load. Use the **Sync now** button in the top nav to trigger a manual fetch at any time.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude Haiku for AI enrichment |
| `EBAY_APP_ID` | Yes | eBay Browse API authentication |
| `EBAY_APP_SECRET` | Yes | eBay Browse API authentication |
| `SCRAPERAPI_KEY` | No | Proxy for Chrono24 — improves reliability |

## What I'd build next

1. **Taste-based ranking** — use the shortlisted listings to infer what the collector prefers and surface similar finds higher
2. **Price trend by model** — a Marlin usually at $45 selling for $20 is a much better find than a Marlin at $45
3. **Desktop notification** when a new listing appears — the app has to be open to know about new finds
4. **Depop and WatchPatrol adapters** — same interface, one new file each
5. **Thumbs up/down feedback loop** — let saves and dismissals feed back into ranking over time
