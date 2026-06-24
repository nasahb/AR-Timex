# Design: Kijiji RSS Adapter + Chrono24 ScraperAPI Fix

**Date:** 2026-06-24  
**Scope:** Add Kijiji as a new source; fix Chrono24 Cloudflare blocking via ScraperAPI proxy.

---

## Context

eBay works well via official API. Etsy (Parse.bot) returns few results and burns credits. Chrono24 is blocked by Cloudflare. This spec adds Kijiji (free, Canada-specific, RSS) and fixes Chrono24 (ScraperAPI proxy, 1,000 free req/month).

---

## Kijiji RSS Adapter

### How it works
Kijiji exposes public RSS feeds — no auth, no API key, no scraping friction. Feed URL:

```
https://www.kijiji.ca/b-watches/canada/timex/k0c771l0.rss
```

Category 771 = Watches, `l0` = all Canada. The `query` parameter is interpolated into the URL path (spaces → `+` or `-`).

### Parsing
Use `feedparser` (already in requirements). Each entry has:
- `entry.title` → listing title
- `entry.link` → listing URL
- `entry.description` → HTML blob containing price and one image
- `entry.published` → listing date

**Price:** Extract from description HTML with regex: first `$XX.XX` or `$X,XXX` pattern. Already in CAD — no conversion.

**Image:** Parse the `<img src="...">` from the description HTML. One image per listing; store as both `image_url` and a single-item `image_urls` JSON array.

**Listing ID:** Derive from the URL's numeric segment (e.g., `/v-watches/.../1234567890` → `kijiji-1234567890`).

### Output contract
Same dict shape as all other adapters:
```python
{
    "id": "kijiji-<numeric_id>",
    "source": "kijiji",
    "title": str,
    "price": float,          # CAD
    "shipping": None,        # not in RSS
    "shipping_confirmed": False,
    "seller_country": "CA",
    "url": str,
    "image_url": str,        # primary only
    "image_urls": "[]" | "[url]",
    "description": str,      # stripped text from description HTML
    "listed_at": "YYYY-MM-DD",
    "synced_at": ISO str,
    "is_new": 1,
    "raw": {},
}
```

---

## Chrono24 ScraperAPI Fix

### Problem
Chrono24 returns a Cloudflare challenge page to plain `requests.get` calls. The existing BeautifulSoup HTML parsing is correct — the fetching is what fails.

### Fix
ScraperAPI acts as a proxy that handles Cloudflare bypass. Free tier: 1,000 requests/month.

API call format:
```
GET http://api.scraperapi.com/
    ?api_key=<SCRAPERAPI_KEY>
    &url=<target_url>
```

No `render=True` initially (costs 5 credits vs 1). If images or content are missing after testing, we can enable rendering.

**Graceful degradation:** If `SCRAPERAPI_KEY` is empty, fall back to direct request (existing behaviour). This preserves local dev without a key.

### Image note
Chrono24 listings use lazy-load: `data-src` / `data-lazy-src` attributes on `<img>` tags are set in raw HTML before JS runs. ScraperAPI without rendering should deliver these. Expect 1–3 images per listing.

---

## Configuration

### New env var
```
SCRAPERAPI_KEY=<from scraperapi.com free account>
```

### `config.py` addition
```python
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")
```

---

## Database

### New migration in `db.py`
```sql
ALTER TABLE preferences ADD COLUMN kijiji_enabled INTEGER DEFAULT 1;
```

### `save_preferences` update
Add `kijiji_enabled` to the UPDATE statement. The Kijiji toggle must be persisted the same way as `ebay_enabled` etc.

---

## Files Changed

| File | Change |
|---|---|
| `adapters/kijiji.py` | New adapter (RSS + feedparser) |
| `adapters/chrono24.py` | Swap fetch to ScraperAPI proxy with fallback |
| `config.py` | Add `SCRAPERAPI_KEY` |
| `db.py` | Add `kijiji_enabled` migration; add to `save_preferences` |
| `sync.py` | Import kijiji; add `kijiji_enabled` toggle block |
| `app.py` | Add Kijiji checkbox; add `kijiji_enabled` to `save_preferences` call |

---

## Error Handling

- All adapters already return `[]` on any exception — keep this pattern.
- Kijiji: if RSS URL returns non-200 or feedparser fails, return `[]`.
- Chrono24: if ScraperAPI returns Cloudflare HTML (no articles found), return `[]` silently.
- Neither source raises to the caller.

---

## What's Not in Scope

- Etsy is not changed (separate decision).
- No pagination — single RSS page (~25 listings) for Kijiji is acceptable for MVP.
- No Kijiji location filtering (Canada-wide is correct for now).
