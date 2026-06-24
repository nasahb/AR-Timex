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
