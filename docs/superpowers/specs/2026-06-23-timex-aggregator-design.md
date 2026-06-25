# Timex Watch Aggregator — Design Spec
**Date:** 2026-06-23  
**Status:** Approved

---

## 1. Problem

A vintage Timex collector currently finds good listings by manually checking multiple marketplaces, relying on memory to recall preferences, and hoping nothing slips by. The tool solves three pain points: multi-site fragmentation, preference memory, and fear of missing something.

---

## 2. Architecture

Four layers, each with a single job:

```
Streamlit UI
     ↓
Scoring Engine (Claude Haiku 4.5 via Anthropic API)
     ↓
SQLite Database
     ↓
Marketplace Adapters (eBay, Etsy, Chrono24)
```

Data flows one direction: adapters fetch → database stores → scoring engine evaluates → UI displays. The layers communicate through the database; no layer calls another directly.

---

## 3. Marketplace Layer

Three adapters for MVP. Adding a 4th later means writing one new file — nothing else changes.

| Marketplace | Method | Reason |
|---|---|---|
| eBay | RSS feed scraper (feedparser) | No API approval required; RSS is reliable, no auth needed; official API swap-in when approved |
| Etsy | HTML scraper (requests + BeautifulSoup) | API approval pending; best-effort scrape, degrades to empty list gracefully |
| Chrono24 | HTML scraper (requests + BeautifulSoup) | No public API; collector-focused source explicitly named in brief |

Every adapter exposes one function: `fetch_listings(query, max_results)`. It returns a list of listing dicts in a standard format:

```python
{
  "id": "ebay-123456789",       # source-prefixed, globally unique
  "source": "ebay",
  "title": "Timex Marlin 1972 Mechanical",
  "price": 28.00,               # item price in CAD
  "shipping": 9.00,             # None if unknown
  "shipping_confirmed": True,   # False if estimated
  "seller_country": "US",       # "CA", "US", or other ISO code
  "url": "https://...",
  "image_url": "https://...",
  "description": "...",
  "listed_at": "2026-06-22",
  "raw": {...}                  # original API/scrape payload, kept for debugging
}
```

---

## 4. Scoring Engine

Two phases: hard filters (fast, no AI), then AI scoring (only listings that pass filters).

### Phase 1 — Hard Filters

Applied in order. A listing is excluded if any filter fails.

**Budget filter:**
- If `shipping` is known: `total = price + shipping`
- If `shipping` is unknown and seller is US: estimate `$12 CAD`, set `shipping_confirmed = False`
- If `shipping` is unknown and seller is non-US/non-CA: flag as "customs may apply," include in feed but mark clearly
- Exclude if `total > $50 CAD` (confirmed only; unconfirmed-shipping listings stay in feed with flag)

**Condition filter:**
Keyword matching against the listing title and description (no AI — fast and free):
- `excluded` if any of these phrases appear: "for parts," "not working," "broken movement," "cracked case," "as-is not working," "parts only"
- `kept` if the above phrases are absent — this includes "needs battery," "crown stiff," "running slow," cosmetic wear, and no mention of condition
- We err on the side of keeping ambiguous listings; the AI scorer will naturally rank them lower if the description signals problems

**Active listing filter:**
Skip sold, expired, or draft listings.

### Phase 2 — AI Scoring

Every listing that clears Phase 1 is scored by Claude Haiku 4.5. New listings only — already-scored listings are not re-scored unless explicitly refreshed.

**Taste profile seed:**
At startup, the system fetches and stores the three reference watches from the brief:
- `https://www.ebay.ca/itm/377073705816`
- `https://www.ebay.ca/itm/117111976291`
- `https://www.etsy.com/ca/listing/4469739360`

These are passed to Claude as concrete examples of "interesting." The user can also add a plain-English description in the sidebar (additive, not a replacement).

**Scoring prompt returns:**
```json
{
  "taste_score": 8,
  "model_id": "Marlin",
  "reason": "Classic Marlin dial with original bracelet — closely matches your 70s mechanical references"
}
```

- `taste_score`: 0–10, how well the listing matches the taste profile
- `model_id`: Timex line if identifiable (Marlin, Weekender, Expedition, Electric, etc.), else null
- `reason`: one sentence explaining the score in plain English

**Composite score:**
```
value_score = (50 - total_cost) / 50 * 10        # headroom below budget
freshness_score = 10 if listed < 24h ago else 7 if < 72h else 4

final_score = (taste_score × 0.6) + (value_score × 0.3) + (freshness_score × 0.1)
```

**Purchase candidate threshold:** `final_score ≥ 7.5`

---

## 5. Database Schema (SQLite)

Five tables:

**listings** — one row per listing, deduplicated by `id`
```sql
id TEXT PRIMARY KEY,
source TEXT,
title TEXT,
price REAL,
shipping REAL,
shipping_confirmed INTEGER,  -- 0 or 1
total_cad REAL,
seller_country TEXT,
url TEXT,
image_url TEXT,
description TEXT,
listed_at TEXT,
synced_at TEXT,
is_new INTEGER               -- 1 until user opens the app and sees it
```

**scores** — one row per scored listing
```sql
listing_id TEXT PRIMARY KEY,
taste_score REAL,
value_score REAL,
freshness_score REAL,
final_score REAL,
model_id TEXT,
reason TEXT,
scored_at TEXT
```

**preferences** — single row, updated by sidebar
```sql
taste_description TEXT,
threshold REAL,              -- default 7.5
ebay_enabled INTEGER,
etsy_enabled INTEGER,
chrono24_enabled INTEGER
```

**dismissed** — listings the user has marked "not interested"
```sql
listing_id TEXT PRIMARY KEY,
dismissed_at TEXT
```

**favourites** — listings the user has starred
```sql
listing_id TEXT PRIMARY KEY,
favourited_at TEXT
```

---

## 6. UI

Single-page Streamlit app. Two regions: always-on sidebar and main content area.

### Sidebar

- **Taste description**: free-text field, optional, saved to preferences
- **Reference watches**: three thumbnail images from the brief (fetched at startup)
- **Sources**: toggle per marketplace (eBay, Etsy, Chrono24)
- **Score threshold**: slider, default 7.5
- **Favourites**: count of starred listings with a "View Favourites" link that switches the main view
- **Refresh Now**: triggers an immediate sync

### Top bar

```
Last synced: 14 minutes ago  |  🆕 8 new since your last visit
```

New count is the number of listings where `is_new = 1`. On app load, all `is_new = 1` listings are immediately marked `is_new = 0` — so the count reflects what was new since the *previous* session, not the current one.

### Main feed

**Section 1 — Purchase Candidates**
Listings where `final_score ≥ threshold`, not dismissed, sorted by score descending.

Each card shows:
- Watch photo
- Title + Timex model line if identified
- Price breakdown: `$28 + $9 est. = $37 CAD`
- Seller country badge: `CA` (green) for Canadian sellers; `⚠️ customs may apply` for non-US/CA international
- `NEW` badge if `is_new = 1`
- AI reason: *"Classic Marlin dial with original bracelet — closely matches your 70s references"*
- Score badge (green)
- `★ Favourite` toggle → stars the listing, writes to favourites table; clicking again un-favourites
- `View Listing` button → opens URL in new tab
- `Not Interested` → writes to dismissed table, removes from feed

**Divider:** `— All Listings · 62 total —`

**Section 2 — All Listings**
All non-dismissed listings, same card format but dimmer styling. Includes sub-threshold listings with their scores and reasons visible. Sorted by score descending.

### Dismissed listings
Not shown anywhere in the feed. Could be surfaced in a future "Hidden" view.

### Favourites view

Activated by clicking "View Favourites" in the sidebar. Replaces the main feed with:

- All starred listings, sorted by `favourited_at` descending (most recently starred first)
- Same card format as the main feed
- Checkbox on each card for comparison selection
- "Compare X listings" button appears once 2 or more are checked (max 4)

**Comparison view:**
Clicking "Compare" renders a side-by-side column layout, one column per listing, each showing:
- Photo
- Title and model line
- Total price
- Score + reason
- Source and seller country
- `View Listing` link

Comparison is read-only — no actions (no starring, no dismissing) to keep it focused. Clicking "Back to Favourites" returns to the favourites list with prior checkbox state cleared.

---

## 7. Background Sync

APScheduler runs a sync every 30 minutes while the app is open.

Each sync:
1. Fetch listings from all enabled sources
2. Deduplicate against database by `id` — skip known listings
3. Run Phase 1 hard filters
4. Score new listings via Claude API
5. Write to database; set `is_new = 1`
6. Update `last_synced` timestamp

Manual refresh (Refresh Now button) triggers the same sync immediately, regardless of schedule.

---

## 8. Shipping & Country Logic

| Seller country | Shipping known? | Behavior |
|---|---|---|
| Canada (CA) | Yes | Use stated price. Show `CA` badge. |
| Canada (CA) | No | Assume free or cheap; flag as est. Show `CA` badge. |
| United States (US) | Yes | Use stated price. |
| United States (US) | No | Estimate $12 CAD. Show "est." label. |
| International | Yes | Use stated price. Show `⚠️ customs may apply`. |
| International | No | Show `⚠️ customs may apply`. Do not estimate. |

---

## 9. Tech Stack

| Component | Tool | Cost |
|---|---|---|
| UI framework | Streamlit | Free, open source |
| Database | SQLite | Free, built into Python |
| AI scoring | Claude Haiku 4.5 (Anthropic API) | ~$0.01–0.05 per 100 listings |
| Scheduler | APScheduler | Free, open source |
| eBay data | RSS feed (feedparser) | Free, no auth; swap to Browse API when approved |
| Etsy data | HTML scraper (requests + BS4) | Free; swap to Open API v3 when approved |
| Chrono24 data | HTML scraper (requests + BS4) | Free, open source |

---

## 10. What's Out of Scope (MVP)

- Additional marketplaces beyond eBay, Etsy, Chrono24 (adapter pattern makes this easy to add)
- Email or push notifications for new listings
- Price history / sold comps
- User accounts or multi-user support
- Mobile layout
- Production hosting (runs locally)

---

## 11. What's Next (v2 Candidates)

- Add Depop, WatchPatrol, Timex ReWound adapters
- "Customs may apply" listings: attempt to estimate duties using HS code for watches
- Rating system: thumbs up/down on listings to refine taste scoring over time
- Notify on new candidates (email or desktop notification)
- Price trend for known models (Marlin, Weekender) vs. recent comps
