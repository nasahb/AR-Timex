from datetime import datetime

import requests
from bs4 import BeautifulSoup

_BASE = "https://www.chrono24.com"
_SEARCH_URL = f"{_BASE}/search/index.htm"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-CA,en;q=0.9",
}


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Scrape Chrono24 search results. Returns [] if scraping fails or structure changes."""
    try:
        resp = requests.get(
            _SEARCH_URL,
            headers=_HEADERS,
            params={"query": query, "dosearch": "true"},
            timeout=10,
        )
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

            img_el = article.select_one("img[src]")
            image_url = img_el["src"] if img_el else ""

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
                "description": "",
                "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
                "synced_at": datetime.utcnow().isoformat(),
                "is_new": 1,
                "raw": {"listing_id": listing_id, "title": title},
            })
        except Exception:
            continue

    return results
