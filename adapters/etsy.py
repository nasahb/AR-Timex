import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Scrape Etsy search results. Returns [] if JS rendering prevents parsing."""
    try:
        resp = requests.get(
            "https://www.etsy.com/ca/search",
            headers=_HEADERS,
            params={"q": query, "explicit": "1"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        return []

    results = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try JSON-LD structured data first — most reliable when present
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if data.get("@type") == "ItemList":
                    for el in data.get("itemListElement", [])[:max_results]:
                        item = el.get("item", {})
                        offer = (item.get("offers") or [{}])[0]
                        price_usd = float(offer.get("price", 0))
                        price_cad = round(price_usd * 1.38, 2)
                        url = item.get("url", "")
                        lid_match = re.search(r"/listing/(\d+)", url)
                        lid = lid_match.group(1) if lid_match else url
                        results.append({
                            "id": f"etsy-{lid}",
                            "source": "etsy",
                            "title": item.get("name", ""),
                            "price": price_cad,
                            "shipping": None,
                            "shipping_confirmed": False,
                            "seller_country": "",
                            "url": url,
                            "image_url": item.get("image", ""),
                            "description": item.get("description", "")[:500],
                            "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
                            "synced_at": datetime.utcnow().isoformat(),
                            "is_new": 1,
                            "raw": item,
                        })
                    if results:
                        return results
            except Exception:
                continue

        # Fallback: parse data attributes on listing containers
        for card in soup.select("[data-listing-id]")[:max_results]:
            try:
                lid = card.get("data-listing-id", "")
                title = card.get("data-listing-title", "") or card.get_text(strip=True)[:80]
                price_str = card.get("data-listing-price", "0")
                price_usd = float(re.sub(r"[^\d.]", "", price_str) or 0)
                price_cad = round(price_usd * 1.38, 2)
                link = card.select_one("a[href]")
                url = link["href"] if link else ""
                img = card.select_one("img[src]")
                image_url = img["src"] if img else ""
                results.append({
                    "id": f"etsy-{lid}",
                    "source": "etsy",
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
                    "raw": {"listing_id": lid},
                })
            except Exception:
                continue
    except Exception:
        pass

    return results
