import json
import re
from datetime import datetime
from urllib.parse import urlencode

import requests

import config

_BASE = "https://www.chrono24.com"
_SEARCH_URL = f"{_BASE}/search/index.htm"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-CA,en;q=0.9",
}


def _extract_id(url: str) -> str:
    match = re.search(r"--id(\d+)\.htm", url)
    return match.group(1) if match else url.split("/")[-1]


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Fetch Chrono24 listings from JSON-LD structured data embedded in search page."""
    target_url = f"{_SEARCH_URL}?{urlencode({'query': query, 'dosearch': 'true'})}"
    try:
        if config.SCRAPERAPI_KEY:
            resp = requests.get(
                "http://api.scraperapi.com/",
                params={"api_key": config.SCRAPERAPI_KEY, "url": target_url, "premium": "true"},
                timeout=60,
            )
        else:
            resp = requests.get(target_url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    try:
        ld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        offers = []
        for block in ld_blocks:
            data = json.loads(block.strip())
            for node in data.get("@graph", []):
                if node.get("@type") == "AggregateOffer":
                    offers = node.get("offers", [])
                    break
            if offers:
                break
    except Exception:
        return []

    results = []
    for offer in offers[:max_results]:
        try:
            url = offer.get("url", "")
            listing_id = _extract_id(url)
            price_usd = float(offer.get("price", 0) or 0)
            price_cad = round(price_usd * 1.38, 2)

            images = offer.get("image", [])
            if isinstance(images, list):
                all_imgs = [img.get("contentUrl", "") for img in images if img.get("contentUrl")]
            else:
                all_imgs = []
            image_url = all_imgs[0] if all_imgs else ""

            results.append({
                "id": f"chrono24-{listing_id}",
                "source": "chrono24",
                "title": offer.get("name", ""),
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
                "raw": {"listing_id": listing_id, "title": offer.get("name", "")},
            })
        except Exception:
            continue

    return results
