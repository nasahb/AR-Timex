import base64
import json
import time
from datetime import datetime

import requests

import config

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
_WATCH_CATEGORY = "281"

_token_cache = {"value": None, "expires_at": 0}


def _get_token() -> str:
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expires_at"]:
        return _token_cache["value"]

    credentials = base64.b64encode(
        f"{config.EBAY_APP_ID}:{config.EBAY_APP_SECRET}".encode()
    ).decode()

    resp = requests.post(
        _TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 60
    return _token_cache["value"]


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Fetch watch listings from eBay Canada via Browse API."""
    try:
        token = _get_token()
    except Exception:
        return []

    try:
        resp = requests.get(
            _SEARCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA",
            },
            params={
                "q": query,
                "limit": min(max_results, 200),
                "category_ids": _WATCH_CATEGORY,
                "sort": "newlyListed",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results = []
    for item in data.get("itemSummaries", []):
        item_id = item.get("itemId", "")
        # eBay item IDs come as "v1|123456789012|0" — extract the numeric part
        numeric_id = item_id.split("|")[1] if "|" in item_id else item_id

        price = float(item.get("price", {}).get("value", 0))

        shipping = None
        shipping_confirmed = False
        for opt in item.get("shippingOptions", []):
            cost = opt.get("shippingCost", {})
            if cost.get("value") is not None:
                shipping = float(cost["value"])
                shipping_confirmed = True
                break

        primary_image = item.get("image", {}).get("imageUrl", "")
        extra_images = [img.get("imageUrl", "") for img in item.get("additionalImages", [])]
        all_images = [u for u in [primary_image] + extra_images if u]

        results.append({
            "id": f"ebay-{numeric_id}",
            "source": "ebay",
            "title": item.get("title", ""),
            "price": price,
            "shipping": shipping,
            "shipping_confirmed": shipping_confirmed,
            "seller_country": item.get("itemLocation", {}).get("country", ""),
            "url": item.get("itemWebUrl", ""),
            "image_url": primary_image,
            "image_urls": json.dumps(all_images),
            "description": item.get("shortDescription", "")[:500],
            "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
            "synced_at": datetime.utcnow().isoformat(),
            "is_new": 1,
            "raw": json.dumps(item),
        })

    return results
