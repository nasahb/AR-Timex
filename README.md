# Timex Watch Finder

A vintage Timex aggregator built to solve a real problem: good listings across multiple marketplaces sell fast and finding them manually takes too long. The taste profile is anchored to three reference watches from the brief — a 1972 Marlin, a second Marlin, and a 1960s Electric — so the AI has something concrete to score against.

## What it does

- Fetches listings from **eBay, Etsy, Chrono24, and Kijiji** on a configurable schedule (default: every 30 minutes)
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
