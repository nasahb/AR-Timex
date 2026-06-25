# Timex Watch Aggregator — Implementation Record
**Date:** 2026-06-23 | **Last updated:** 2026-06-24

What was originally planned, what changed during implementation, and why.

---

## What was planned

- eBay via RSS feed (feedparser, no auth)
- Etsy via HTML scraper (BeautifulSoup)
- Chrono24 via HTML scraper (BeautifulSoup)
- Claude Haiku for AI **scoring** — composite taste/value/freshness score per listing
- APScheduler for background sync every 30 minutes
- "Purchase Candidates" section — listings above a score threshold
- Side-by-side comparison view for shortlisted listings

## What changed and why

**eBay → official Browse API instead of RSS**
The RSS feed returned limited fields (no shipping, no structured price, no image gallery). The eBay Browse API gives structured data, proper CAD pricing via the EBAY_CA marketplace, confirmed shipping costs, and multiple images per listing. Required OAuth credentials but worth the tradeoff.

**Etsy → parse.bot API instead of HTML scraper**
Etsy's HTML structure is heavily JS-rendered, making BeautifulSoup scraping unreliable. parse.bot provides a stable scraper API that returns structured listing data. Requires a PARSE_API_KEY.

**Chrono24 → JSON-LD parser instead of HTML scraper**
Chrono24 embeds structured application/ld+json data in their search page. Parsing this directly is more reliable than scraping the rendered HTML layout, which changes frequently.

**Kijiji → stubbed out**
Kijiji dropped RSS support and serves JS-rendered pages with no viable free fetch path. Adapter exists and returns [].

**Scoring engine → AI enrichment**
The original plan had Claude produce a taste score (0–10) plus composite ranking. During implementation this was replaced with AI enrichment: Claude produces a factual editorial summary and extracts structured attributes (movement, era, model, size). Reasons:
- Enrichment is more durable — the summary is useful regardless of the collector's current taste
- A static taste profile based on three reference watches produced inconsistent scores
- Enrichment data improves filter precision (era pills, model pills work off detected fields)

**APScheduler → manual sync only**
Background scheduling was not wired up in the current build. Sync is triggered via the "Sync now" button in the top nav. APScheduler is removed as a dependency.

**Purchase Candidates + comparison view → not built**
Without a scoring engine there is no threshold to gate a "Candidates" section. The feed is a single filtered list controlled by the sidebar. The comparison view was deprioritised in favour of a shortlist with full-detail cards.

---

## File map (as built)

| File | Responsibility |
|---|---|
| config.py | Env vars and constants |
| db.py | SQLite schema + all CRUD functions |
| filters.py | Hard filters — shipping logic, keyword blocklist, budget |
| enricher.py | Claude Haiku enrichment — summary, movement, era, model, size |
| adapters/ebay.py | eBay Browse API (OAuth) |
| adapters/etsy.py | Etsy via parse.bot API |
| adapters/chrono24.py | Chrono24 JSON-LD scraper |
| adapters/kijiji.py | Stub — returns [] |
| sync.py | Orchestration: fetch → filter → store → enrich (8 concurrent workers) |
| app.py | Streamlit UI — nav, sidebar, feed, shortlist, modals |
| seed.py | One-time DB seed from a JSON fixture file |
| tests/test_adapters.py | Adapter output shape tests (HTTP mocked) |
| requirements.txt | Python dependencies |
| .env.example | Template for required env vars |
| README.md | Product brief and setup instructions |
