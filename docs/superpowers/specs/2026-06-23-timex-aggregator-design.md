# Timex Watch Aggregator — Design Spec
**Date:** 2026-06-23 | **Last updated:** 2026-06-24
**Status:** Built

---

## 1. Problem

A vintage Timex collector currently finds good listings by manually checking multiple marketplaces, relying on memory to recall preferences, and hoping nothing slips by. The tool solves three pain points: multi-site fragmentation, preference memory, and fear of missing something.

---

## 2. Architecture

```
Streamlit UI (app.py)
        ↓
Sync engine (sync.py) → AI Enrichment (enricher.py)
        ↓
SQLite Database (db.py)
        ↓
Marketplace Adapters (adapters/)
```

Data flows one direction: adapters fetch → hard filters cut junk → database stores → enricher annotates → UI displays. Layers communicate through the database only.

---

## 3. Marketplace Layer

Four adapters, each exposing one function: `fetch_listings(query, max_results) -> list`.

| Marketplace | Method | Notes |
|---|---|---|
| eBay | Official Browse API (OAuth) | EBAY_CA marketplace, watches category, sorts by newly listed |
| Etsy | parse.bot scraper API | Requires `PARSE_API_KEY`; degrades gracefully to `[]` if absent |
| Chrono24 | JSON-LD scraper | Parses structured data embedded in search page; optional `SCRAPERAPI_KEY` improves reliability |
| Kijiji | Disabled (stub) | Dropped RSS support; adapter exists but returns `[]` and is excluded from syncs |

All adapters return a standard listing dict:

```python
{
  "id": "ebay-123456789",       # source-prefixed, globally unique
  "source": "ebay",
  "title": "Timex Marlin 1972 Mechanical",
  "price": 28.00,               # item price in CAD
  "shipping": 9.00,             # None if unknown
  "shipping_confirmed": True,
  "seller_country": "US",
  "url": "https://...",
  "image_url": "https://...",
  "image_urls": "[...]",        # JSON array of all available images
  "description": "...",
  "listed_at": "2026-06-22",
  "synced_at": "2026-06-22T14:30:00",
  "is_new": 1,
  "raw": {...}
}
```

---

## 4. Filtering

Hard filters run before any AI is involved. Fast, no API cost.

**Shipping logic** (`filters.py: apply_shipping_logic`):
- CA seller, shipping unknown → assume free, `total_cad = price`
- US seller, shipping unknown → estimate $12 CAD, `shipping_confirmed = False`
- Shipping known → `total_cad = price + shipping`

**Hard filter** (`filters.py: passes_hard_filters`):
- Over `budget_cad` (default $50 CAD) → rejected
- Title/description contains non-working phrases → rejected
- Title/description contains for-parts phrases or component-only patterns → rejected
- Title missing any significant word from the search query → rejected

---

## 5. AI Enrichment

Every listing that passes filters and hasn't been enriched yet is sent to **Claude Haiku** (`claude-haiku-4-5-20251001`). Enrichment runs concurrently (8 worker threads) after each sync.

Claude returns:

```json
{
  "summary": "4–6 sentence paragraph covering movement, case, dial, strap, condition, red flags",
  "movement": "Mechanical | Automatic | Quartz | Electric | null",
  "era": "1950s | 1960s | 1970s | 1980s | 1990s+ | null",
  "model": "Marlin | Viscount | Mercury | Electric | Weekender | ... | null",
  "size": "Men's | Women's | null"
}
```

Results are stored directly on the `listings` row (not a separate table).

---

## 6. Database Schema (SQLite)

**listings** — one row per listing
```sql
id, source, title, price, shipping, shipping_confirmed, total_cad,
seller_country, url, image_url, image_urls, description,
listed_at, synced_at, is_new,
ai_summary, detected_movement, detected_era, detected_model, detected_size
```

**preferences** — single row, updated by sidebar
```sql
taste_description, ebay_enabled, etsy_enabled, chrono24_enabled,
kijiji_enabled, search_query, budget_cad, movement_pref, size_pref,
era_prefs, model_prefs, exclude_nonworking, exclude_forparts,
hide_international, last_synced
```

**dismissed** — listings the user has hidden
```sql
listing_id TEXT PRIMARY KEY, dismissed_at TEXT
```

**favourites** — listings saved to shortlist
```sql
listing_id TEXT PRIMARY KEY, favourited_at TEXT
```

---

## 7. UI

Single-page Streamlit app. Fixed top nav (FEED / SHORTLIST / Sync now) + collapsible sidebar + main content.

### Sidebar filters
- Movement pills (Mechanical, Automatic, Quartz, Electric)
- Size pills (Men's, Women's)
- Era pills (1950s–1990s+)
- Model pills (Marlin, Viscount, Electric, Weekender, etc.)
- Taste description (free-text, optional)
- Budget slider
- Source checkboxes (eBay, Etsy, Chrono24)
- Search query text field

### Feed view
Paginated grid of compact cards (2 columns). Each card shows photo carousel, title, detected model chip, era chip, price, AI summary excerpt, source badge, and Save / Dismiss actions. Clicking a card opens a full modal with the complete AI summary and all images.

### Shortlist view
Full-width candidate cards for saved listings, sorted by most recently saved.

### Sync
Manual only — triggered via "Sync now" in the top nav. Fetch → filter → store → enrich runs sequentially; new listing count badge updates after sync.

---

## 8. Tech Stack

| Component | Tool |
|---|---|
| UI | Streamlit |
| Database | SQLite |
| AI enrichment | Claude Haiku 4.5 (Anthropic API) |
| eBay | eBay Browse API (OAuth) |
| Etsy | parse.bot scraper API |
| Chrono24 | JSON-LD scraper (requests) |
| Env config | python-dotenv |
| Tests | pytest |

---

## 9. What's Out of Scope (MVP)

- AI-based ranking / taste scoring (enrichment only — no composite score)
- Background / scheduled sync (manual only)
- Side-by-side comparison view
- Email or push notifications
- Price history / sold comps
- User accounts or multi-user support
- Kijiji (stubbed — no viable fetch path)
- Production hosting

---

## 10. What's Next (v2 Candidates)

- Taste-based ranking using shortlisted listings to infer preferences
- Scheduled background sync (APScheduler already in the design, not wired up)
- Desktop notification when new listings appear
- Price trend by model (Marlin at $20 vs. usual $45 is a signal)
- Depop and WatchPatrol adapters
- Thumbs up/down feedback to refine ranking over time
