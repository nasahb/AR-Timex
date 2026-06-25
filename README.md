# Timex Watch Finder

## Build Plan

### What I'm building

A personal vintage Timex aggregator. It pulls listings from eBay, Etsy, Chrono24, and Kijiji, filters out the junk automatically, and uses Claude AI to score each remaining listing against a defined taste profile. Results surface in a Streamlit UI where I can browse, filter, save, and act on good finds quickly.

### Why

Vintage Timex hunting is a timing problem. Good listings — correct dial condition, right model, reasonable price — appear and sell within hours across four different marketplaces. Checking all of them manually every day means either missing things or spending time I don't want to spend. The collector has three specific reference watches that define "interesting" (a 1972 Marlin, a second Marlin variant, a 1960s Electric). The taste is defined; what's missing is automation.

### How

**Phase 1 — Data layer.** Four marketplace adapters (`adapters/`) each expose one function: `fetch_listings(query, max_results)`. eBay uses RSS (no auth needed), Etsy and Chrono24 use HTML scraping, Kijiji is stubbed pending a viable fetch path. All adapters return listings in a standard dict format so the rest of the system doesn't care which marketplace a listing came from.

**Phase 2 — Filtering.** A fast keyword pass (`filters.py`) cuts obvious junk — broken watches, parts lots, over-budget listings — before any AI is involved. This runs in milliseconds and eliminates 30–40% of listings, keeping Claude costs low.

**Phase 3 — Scoring.** `scorer.py` sends surviving listings to Claude Haiku with the taste profile as context. It returns a composite score: 60% taste match, 30% value, 10% freshness. Haiku was chosen over Sonnet/Opus because the task is classification, not reasoning — throughput matters more than depth. Cost: ~$0.01–0.05 per 100 listings.

**Phase 4 — Enrichment.** `enricher.py` runs per-listing AI enrichment: model detection, a one-line editorial summary, and structured data extraction. This runs concurrently (8 workers) after each sync.

**Phase 5 — Storage.** SQLite (`db.py`) stores listings, scores, favourites, and user preferences. Chosen for simplicity — no server, no migrations, works locally.

**Phase 6 — UI.** Streamlit (`app.py`) renders a feed of scored listings with sidebar filters (price, source, condition), pagination, a card modal, and a shortlist. The visual design is intentionally editorial — Newsreader serif for display, Geist for UI chrome, near-black on near-white.

**Sync schedule.** APScheduler runs a background sync every 30 minutes. The UI also exposes a manual "Sync now" button.

Full design rationale lives in [`docs/superpowers/specs/2026-06-23-timex-aggregator-design.md`](docs/superpowers/specs/2026-06-23-timex-aggregator-design.md). The implementation plan is in [`docs/superpowers/plans/2026-06-23-timex-aggregator.md`](docs/superpowers/plans/2026-06-23-timex-aggregator.md).

---

## What it does

- Fetches listings from **eBay, Etsy, Chrono24, and Kijiji** on a 30-minute schedule
- Cuts obvious junk in a fast keyword pass before any AI is involved
- Uses **Claude Haiku** to score every remaining listing on taste, value, and freshness
- Surfaces results in a clean **Streamlit UI** with sidebar filters, pagination, and a shortlist
- Lets you save listings to a shortlist and come back to them later

## Architecture

```
adapters/       eBay (RSS), Etsy (scraper), Chrono24 (JSON-LD), Kijiji (stub)
filters.py      Hard filters — keyword blocklist, price ceiling, shipping logic
scorer.py       Composite score: 60% taste (Claude), 30% value, 10% freshness
enricher.py     Per-listing AI enrichment — model detection, summary, structured data
sync.py         Orchestration — fetch → filter → score → deduplicate → store
db.py           SQLite — listings, favourites, scores, preferences
app.py          Streamlit UI — feed, shortlist, sidebar filters, modal
seed.py         One-time DB seed from a JSON file
```

## Scoring design

**Two-phase filtering keeps costs low.** The first pass is pure keyword matching — "for parts," "not working," "watch lot," etc. No AI, takes milliseconds, cuts 30–40% of listings immediately. Claude only sees what survives that filter.

**Claude Haiku, not Sonnet or Opus.** The task is "does this match those three reference watches" — throughput matters more than reasoning depth. Cost is roughly $0.01–0.05 per 100 listings.

**Composite score: 60% taste / 30% value / 10% freshness.** Taste is the hardest thing to automate and the actual problem being solved. Value and freshness add signal without overriding a genuinely good match at a fair price.

**Shipping is handled automatically.** Canadian sellers get a green badge. US sellers without listed shipping get a $12 CAD estimate. International sellers get a customs warning. Users never have to think about it.

## Tradeoffs

- **eBay and Etsy use scrapers, not official APIs.** Both require approval that takes days. The adapter pattern means swapping to official APIs later is a one-file change per marketplace.
- **Chrono24 parses JSON-LD structured data** embedded in their search page. Works with the current structure; degrades gracefully to an empty list if it changes.
- **Kijiji is stubbed out.** Kijiji dropped RSS support and serves JS-rendered HTML with no viable free fetch path. The adapter returns `[]` until a solution is found.
- **No authentication.** This runs locally for one user. Multi-user support would require a backend and sessions — out of scope.
- **USD → CAD conversion uses a fixed rate (1.38).** Good enough for a $50 CAD budget threshold; a live rate API would be the v2 upgrade.

## Running locally

```bash
# 1. Clone
git clone https://github.com/nasahb/AR-Timex
cd AR-Timex

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys
cp .env.example .env
# Edit .env — minimum required: ANTHROPIC_API_KEY
# Optional: SCRAPERAPI_KEY (improves Chrono24 reliability)

# 4. Run
streamlit run app.py
```

The app auto-syncs on first load. Use the **Sync now** button in the top nav to trigger a manual fetch.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude Haiku for scoring and enrichment |
| `SCRAPERAPI_KEY` | No | Proxy for Chrono24 — improves reliability |

## What I'd build next

1. **Thumbs up/down feedback** to let the taste model learn over time — right now the profile is static
2. **Price trend by model** — a Marlin usually at $45 selling for $20 is a much better find than a Marlin at $45
3. **Desktop notification** when a new purchase candidate appears — the app has to be open to know about new listings
4. **Depop and WatchPatrol adapters** — same interface, one new file each
5. **Official eBay and Etsy APIs** — swap the scrapers once approved, nothing else changes
