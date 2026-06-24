# Kijiji removed RSS support and serves JS-rendered HTML — this adapter returns []
# until a viable fetch method is found.
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
    # Kijiji requires JS rendering — no viable free fetch path currently
    return []
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
                "raw": {k: entry.get(k, "") for k in ("title", "link", "summary", "published")},
            })
        except Exception:
            continue

    return results
