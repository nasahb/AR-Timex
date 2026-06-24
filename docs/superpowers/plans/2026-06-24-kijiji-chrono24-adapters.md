# Kijiji RSS Adapter + Chrono24 ScraperAPI Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Kijiji as a Canada-specific RSS source and fix Chrono24 by routing requests through ScraperAPI's Cloudflare-bypass proxy.

**Architecture:** Each new/fixed adapter follows the existing pattern — a `fetch_listings(query, max_results)` function returning a list of dicts with a fixed shape. ScraperAPI wraps the existing Chrono24 HTML fetch transparently; the HTML parser is unchanged. Kijiji uses `feedparser` (already a dependency) to parse the RSS feed; price and image are extracted from the description HTML blob.

**Tech Stack:** Python 3, `feedparser`, `beautifulsoup4`, `requests`, ScraperAPI free tier (1,000 req/month), SQLite migrations.

## Global Constraints

- All adapters return `[]` on any failure — never raise to the caller.
- `fetch_listings` signature: `(query: str, max_results: int = 50) -> list`
- All listing dicts must contain: `id`, `source`, `title`, `price`, `shipping`, `shipping_confirmed`, `seller_country`, `url`, `image_url`, `image_urls`, `description`, `listed_at`, `synced_at`, `is_new`, `raw`.
- `image_urls` is a JSON-encoded list string (e.g. `'["https://..."]'` or `'[]'`).
- Prices are in CAD. Chrono24 prices are USD — multiply by 1.38.
- Run the full test suite with `pytest` before each commit. All tests must pass.
- Do not push to remote.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `adapters/chrono24.py` | Modify | Add ScraperAPI proxy branch in fetch |
| `adapters/kijiji.py` | Create | RSS adapter — parse feed, extract price + image |
| `config.py` | Modify | Add `SCRAPERAPI_KEY` env var |
| `db.py` | Modify | Add `kijiji_enabled` migration + update `save_preferences` |
| `sync.py` | Modify | Import kijiji, add `kijiji_enabled` toggle |
| `app.py` | Modify | Add Kijiji checkbox, wire `kijiji_enabled` to save |
| `tests/test_adapters.py` | Modify | Add Kijiji tests + ScraperAPI path test for Chrono24 |
| `tests/test_db.py` | Modify | Update `test_save_preferences` to include `kijiji_enabled` |

---

## Task 1: ScraperAPI config + Chrono24 fix

**Files:**
- Modify: `config.py`
- Modify: `adapters/chrono24.py`
- Modify: `tests/test_adapters.py`

**Interfaces:**
- Produces: `adapters.chrono24.fetch_listings(query: str, max_results: int) -> list[dict]` — same signature as before; now routes through ScraperAPI when `config.SCRAPERAPI_KEY` is set.

**Pre-requisite:** Sign up at [scraperapi.com](https://www.scraperapi.com) (free, no credit card). Copy your API key. Add it to your `.env` file:
```
SCRAPERAPI_KEY=your_key_here
```

- [ ] **Step 1: Write the failing test for ScraperAPI routing**

Add to `tests/test_adapters.py` after the existing `test_chrono24_fetch_returns_standard_shape_or_empty` test:

```python
def test_chrono24_uses_scraperapi_when_key_set():
    mock_resp = MagicMock()
    mock_resp.text = CHRONO24_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("adapters.chrono24.config.SCRAPERAPI_KEY", "test-key"), \
         patch("adapters.chrono24.requests.get", return_value=mock_resp) as mock_get:
        results = c24_fetch("timex", max_results=10)

    call_url = mock_get.call_args[0][0]
    assert call_url == "http://api.scraperapi.com/"
    assert mock_get.call_args[1]["params"]["api_key"] == "test-key"
    assert len(results) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_adapters.py::test_chrono24_uses_scraperapi_when_key_set -v
```

Expected: FAIL — `AssertionError` because current code calls Chrono24 directly, not ScraperAPI.

- [ ] **Step 3: Add SCRAPERAPI_KEY to config.py**

In `config.py`, after line 10 (`EBAY_APP_SECRET = ...`), add:

```python
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")
```

- [ ] **Step 4: Update chrono24.py to use ScraperAPI**

Replace the entire contents of `adapters/chrono24.py` with:

```python
import json
from datetime import datetime
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import config

_BASE = "https://www.chrono24.com"
_SEARCH_URL = f"{_BASE}/search/index.htm"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-CA,en;q=0.9",
}


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Scrape Chrono24 via ScraperAPI if key is configured, direct request otherwise."""
    target_url = f"{_SEARCH_URL}?{urlencode({'query': query, 'dosearch': 'true'})}"
    try:
        if config.SCRAPERAPI_KEY:
            resp = requests.get(
                "http://api.scraperapi.com/",
                params={"api_key": config.SCRAPERAPI_KEY, "url": target_url},
                timeout=30,
            )
        else:
            resp = requests.get(target_url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.article-item-container")[:max_results]
    except Exception:
        return []

    results = []
    for article in articles:
        try:
            listing_id = article.get("data-listing-id", "")
            link = article.select_one("a[href]")
            href = link["href"] if link else ""
            url = f"{_BASE}{href}" if href.startswith("/") else href

            title_el = article.select_one(".article-title")
            title = title_el.get_text(strip=True) if title_el else ""

            price_el = article.select_one(".price")
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price_digits = "".join(c for c in price_text if c.isdigit() or c == ".")
            price_usd = float(price_digits) if price_digits else 0.0
            price_cad = round(price_usd * 1.38, 2)

            all_imgs = []
            for img_el in article.select("img"):
                src = img_el.get("data-src") or img_el.get("data-lazy-src") or img_el.get("src") or ""
                if src and src not in all_imgs:
                    all_imgs.append(src)
            image_url = all_imgs[0] if all_imgs else ""

            results.append({
                "id": f"chrono24-{listing_id}",
                "source": "chrono24",
                "title": title,
                "price": price_cad,
                "shipping": None,
                "shipping_confirmed": False,
                "seller_country": "",
                "url": url,
                "image_url": image_url,
                "image_urls": json.dumps(all_imgs),
                "description": "",
                "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
                "synced_at": datetime.utcnow().isoformat(),
                "is_new": 1,
                "raw": {"listing_id": listing_id, "title": title},
            })
        except Exception:
            continue

    return results
```

- [ ] **Step 5: Run all Chrono24 tests**

```bash
pytest tests/test_adapters.py -k chrono24 -v
```

Expected: all 2 Chrono24 tests PASS.

- [ ] **Step 6: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add config.py adapters/chrono24.py tests/test_adapters.py
git commit -m "feat: route Chrono24 through ScraperAPI for Cloudflare bypass"
```

---

## Task 2: Kijiji RSS adapter

**Files:**
- Create: `adapters/kijiji.py`
- Modify: `tests/test_adapters.py`

**Interfaces:**
- Produces: `adapters.kijiji.fetch_listings(query: str, max_results: int) -> list[dict]` — standard listing dict shape, prices in CAD (already), `seller_country = "CA"`, one image max.

- [ ] **Step 1: Write failing tests for Kijiji adapter**

Add to the bottom of `tests/test_adapters.py`:

```python
# ── Kijiji ────────────────────────────────────────────────────────────────

from adapters.kijiji import fetch_listings as kijiji_fetch

KIJIJI_DESCRIPTION = """
<table>
<tr>
  <td><a href="/v-watches/canada/timex-marlin/1234567890">
    <img src="https://i.ebayimg.com/00/s/abc.jpg" />
  </a></td>
  <td>Price: $45.00<br/>Vintage Timex Marlin in good condition.</td>
</tr>
</table>
"""


def test_kijiji_fetch_returns_standard_shape():
    entry = MagicMock()
    entry.title = "Vintage Timex Marlin"
    entry.link = "https://www.kijiji.ca/v-watches/canada/timex-marlin/1234567890"
    entry.published_parsed = None
    entry.get.side_effect = lambda k, d="": {
        "title": "Vintage Timex Marlin",
        "link": "https://www.kijiji.ca/v-watches/canada/timex-marlin/1234567890",
        "summary": KIJIJI_DESCRIPTION,
    }.get(k, d)

    mock_feed = MagicMock()
    mock_feed.entries = [entry]

    with patch("adapters.kijiji.feedparser.parse", return_value=mock_feed):
        results = kijiji_fetch("timex vintage", max_results=10)

    assert len(results) == 1
    listing = results[0]
    assert listing["id"] == "kijiji-1234567890"
    assert listing["source"] == "kijiji"
    assert listing["price"] == 45.0
    assert listing["seller_country"] == "CA"
    assert "kijiji.ca" in listing["url"]
    assert listing["image_url"] == "https://i.ebayimg.com/00/s/abc.jpg"
    assert '"https://i.ebayimg.com/00/s/abc.jpg"' in listing["image_urls"]
    assert "raw" in listing


def test_kijiji_fetch_empty_on_feedparser_failure():
    with patch("adapters.kijiji.feedparser.parse", side_effect=Exception("network error")):
        results = kijiji_fetch("timex vintage", max_results=10)
    assert results == []


def test_kijiji_fetch_skips_malformed_entries():
    entry_bad = MagicMock()
    entry_bad.get.side_effect = Exception("boom")

    mock_feed = MagicMock()
    mock_feed.entries = [entry_bad]

    with patch("adapters.kijiji.feedparser.parse", return_value=mock_feed):
        results = kijiji_fetch("timex", max_results=10)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_adapters.py -k kijiji -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.kijiji'`.

- [ ] **Step 3: Create adapters/kijiji.py**

```python
import json
import re
from datetime import datetime
from time import strftime

import feedparser
from bs4 import BeautifulSoup

_RSS_URL = "https://www.kijiji.ca/b-watches/canada/{query}/k0c771l0.rss"


def _slugify(query: str) -> str:
    return re.sub(r'\s+', '-', query.strip().lower())


def _extract_price(html: str) -> float:
    match = re.search(r'\$([\d,]+(?:\.\d{2})?)', html)
    return float(match.group(1).replace(',', '')) if match else 0.0


def _extract_image(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    return img.get("src", "") if img else ""


def _extract_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)[:500]


def _extract_id(url: str) -> str:
    match = re.search(r'/(\d+)(?:\?|$)', url)
    return match.group(1) if match else url.split("/")[-1]


def fetch_listings(query: str, max_results: int = 50) -> list:
    url = _RSS_URL.format(query=_slugify(query))
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    results = []
    for entry in feed.entries[:max_results]:
        try:
            link = entry.get("link", "")
            description_html = entry.get("summary", "") or entry.get("description", "")
            price = _extract_price(description_html)
            image_url = _extract_image(description_html)
            listing_id = _extract_id(link)

            if hasattr(entry, "published_parsed") and entry.published_parsed:
                listed_at = strftime("%Y-%m-%d", entry.published_parsed)
            else:
                listed_at = datetime.utcnow().strftime("%Y-%m-%d")

            results.append({
                "id": f"kijiji-{listing_id}",
                "source": "kijiji",
                "title": entry.get("title", ""),
                "price": price,
                "shipping": None,
                "shipping_confirmed": False,
                "seller_country": "CA",
                "url": link,
                "image_url": image_url,
                "image_urls": json.dumps([image_url]) if image_url else "[]",
                "description": _extract_text(description_html),
                "listed_at": listed_at,
                "synced_at": datetime.utcnow().isoformat(),
                "is_new": 1,
                "raw": {},
            })
        except Exception:
            continue

    return results
```

- [ ] **Step 4: Run Kijiji tests**

```bash
pytest tests/test_adapters.py -k kijiji -v
```

Expected: all 3 Kijiji tests PASS.

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add adapters/kijiji.py tests/test_adapters.py
git commit -m "feat: add Kijiji RSS adapter"
```

---

## Task 3: DB migration + sync wiring

**Files:**
- Modify: `db.py:42-49` (preferences table schema + migrations list)
- Modify: `db.py:126-143` (`save_preferences` function)
- Modify: `sync.py`
- Modify: `tests/test_db.py:65-69` (`test_save_preferences`)

**Interfaces:**
- Consumes: `adapters.kijiji.fetch_listings` (from Task 2)
- Produces: `db.save_preferences` accepts `kijiji_enabled` key; `preferences` table has `kijiji_enabled INTEGER DEFAULT 1`; `sync.run_sync` calls kijiji adapter.

- [ ] **Step 1: Update test_save_preferences to include kijiji_enabled**

In `tests/test_db.py`, replace the `test_save_preferences` function (lines 65–69):

```python
def test_save_preferences(conn):
    save_preferences(conn, {
        "taste_description": "I love Marlins",
        "threshold": 8.0,
        "ebay_enabled": 1,
        "etsy_enabled": 0,
        "chrono24_enabled": 1,
        "kijiji_enabled": 1,
        "search_query": "timex vintage",
        "budget_cad": 50.0,
        "movement_pref": "Any",
        "size_pref": "Any",
        "era_prefs": "[]",
        "model_prefs": "[]",
        "exclude_nonworking": 1,
        "exclude_forparts": 1,
    })
    prefs = get_preferences(conn)
    assert prefs["taste_description"] == "I love Marlins"
    assert prefs["threshold"] == 8.0
    assert prefs["kijiji_enabled"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_db.py::test_save_preferences -v
```

Expected: FAIL — SQLite error about missing `kijiji_enabled` binding or column.

- [ ] **Step 3: Add kijiji_enabled migration in db.py**

In `db.py`, add one line to the `migrations` list (after the last `ALTER TABLE listings` entry, around line 80):

```python
"ALTER TABLE preferences ADD COLUMN kijiji_enabled INTEGER DEFAULT 1",
```

- [ ] **Step 4: Add kijiji_enabled to save_preferences in db.py**

Replace the `save_preferences` function body with:

```python
def save_preferences(conn: sqlite3.Connection, prefs: dict) -> None:
    conn.execute(
        """UPDATE preferences SET
           taste_description = :taste_description,
           threshold = :threshold,
           ebay_enabled = :ebay_enabled,
           etsy_enabled = :etsy_enabled,
           chrono24_enabled = :chrono24_enabled,
           kijiji_enabled = :kijiji_enabled,
           search_query = :search_query,
           budget_cad = :budget_cad,
           movement_pref = :movement_pref,
           size_pref = :size_pref,
           era_prefs = :era_prefs,
           model_prefs = :model_prefs,
           exclude_nonworking = :exclude_nonworking,
           exclude_forparts = :exclude_forparts
           WHERE id = 1""",
        prefs,
    )
    conn.commit()
```

- [ ] **Step 5: Run db test to verify it passes**

```bash
pytest tests/test_db.py::test_save_preferences -v
```

Expected: PASS.

- [ ] **Step 6: Wire Kijiji into sync.py**

In `sync.py`, add the import after the existing adapter imports (around line 6):

```python
import adapters.kijiji as kijiji
```

Then in `run_sync`, after the `chrono24_enabled` block (around line 33), add:

```python
    if prefs.get("kijiji_enabled", 1) and len(all_listings) < FETCH_CAP:
        all_listings.extend(kijiji.fetch_listings(search_query, max_results=FETCH_CAP - len(all_listings)))
```

- [ ] **Step 7: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add db.py sync.py tests/test_db.py
git commit -m "feat: wire Kijiji into sync engine and add kijiji_enabled preference"
```

---

## Task 4: UI toggle for Kijiji

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `db.save_preferences` with `kijiji_enabled` key (from Task 3)
- Produces: Kijiji checkbox in sidebar Sources section; persisted to preferences.

- [ ] **Step 1: Add Kijiji checkbox in app.py**

In `app.py`, after the Chrono24 checkbox block (around line 727):

```python
        if "sb_kijiji" not in st.session_state:
            st.session_state["sb_kijiji"] = bool(prefs.get("kijiji_enabled", 1))
        kijiji_on = st.checkbox("Kijiji", key="sb_kijiji")
```

- [ ] **Step 2: Add kijiji_enabled to save_preferences call in app.py**

In the `save_preferences(conn, {...})` call (around line 738), add `"kijiji_enabled": int(kijiji_on),` after `"chrono24_enabled": int(c24_on),`:

```python
        save_preferences(conn, {
            "taste_description": taste,
            "threshold": prefs.get("threshold", config.SCORE_THRESHOLD),
            "ebay_enabled": int(ebay_on),
            "etsy_enabled": int(etsy_on),
            "chrono24_enabled": int(c24_on),
            "kijiji_enabled": int(kijiji_on),
            "search_query": search_query,
            "budget_cad": float(budget_cad),
            "movement_pref": json.dumps(movement_pref) if isinstance(movement_pref, list) else (movement_pref or "Any"),
            "size_pref": size_pref,
            "era_prefs": json.dumps(era_prefs),
            "model_prefs": json.dumps(model_prefs),
            "exclude_nonworking": 1,
            "exclude_forparts": 1,
        })
```

- [ ] **Step 3: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add Kijiji source toggle to sidebar"
```

---

## Done

After all four tasks: run a manual sync in the UI (`Sync now`). You should see listings appearing from `kijiji` and (if `SCRAPERAPI_KEY` is set) `chrono24` sources in the feed. Check the source counts at the bottom of the sidebar.
