import json
import re
from datetime import datetime

import requests


def _hires(url: str) -> str:
    if not url:
        return url
    return re.sub(r'il_\d+x[Nn\d]+\.', 'il_1588xN.', url)

import config

_SCRAPER_ID = "3b1c0fe9-5232-41f9-81c3-d8346c37039c"
_BASE_URL = f"https://api.parse.bot/scraper/{_SCRAPER_ID}"


def fetch_listings(query: str, max_results: int = 50) -> list:
    if not config.PARSE_API_KEY:
        return []

    try:
        resp = requests.post(
            f"{_BASE_URL}/search_listings",
            headers={"X-API-Key": config.PARSE_API_KEY},
            json={"query": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results = []
    for item in (data.get("data") or {}).get("items", [])[:max_results]:
        lid = item.get("listing_id", "")
        try:
            price_usd = float(str(item.get("price") or 0).replace(",", ""))
        except (ValueError, TypeError):
            price_usd = 0.0
        price_cad = round(price_usd * 1.38, 2)

        # Try to collect all available images from the API response
        raw_imgs = item.get("images") or item.get("additional_images") or []
        if isinstance(raw_imgs, list) and raw_imgs:
            all_imgs = [_hires(u) for u in raw_imgs if isinstance(u, str) and u]
        else:
            all_imgs = []
        primary_img = _hires(item.get("image", ""))
        if primary_img and primary_img not in all_imgs:
            all_imgs.insert(0, primary_img)

        results.append({
            "id": f"etsy-{lid}",
            "source": "etsy",
            "title": item.get("name", ""),
            "price": price_cad,
            "shipping": None,
            "shipping_confirmed": False,
            "seller_country": "",
            "url": item.get("url", ""),
            "image_url": primary_img,
            "image_urls": json.dumps(all_imgs),
            "description": item.get("description") or "",
            "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
            "synced_at": datetime.utcnow().isoformat(),
            "is_new": 1,
            "raw": item,
        })

    return results
