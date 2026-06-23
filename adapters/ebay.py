import re
from datetime import datetime

import feedparser


_RSS_URL = "https://www.ebay.ca/sch/i.html?_nkw={query}&_rss=1&_sacat=0&LH_ItemCondition=3000"


def fetch_listings(query: str, max_results: int = 50) -> list:
    """Fetch vintage Timex listings from eBay Canada via RSS — no auth required."""
    url = _RSS_URL.format(query=query.replace(" ", "+"))
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    results = []
    for entry in feed.entries[:max_results]:
        title_raw = entry.get("title", "")
        link = entry.get("link", "")

        id_match = re.search(r"/itm/(\d+)", link)
        item_id = id_match.group(1) if id_match else re.sub(r"\W+", "-", link)

        price_match = re.search(r"\$\s*([\d,]+\.?\d*)", title_raw)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

        title = re.sub(r"\s*[-–]\s*\$[\d,\.]+\s*$", "", title_raw).strip()

        image_url = ""
        thumbnails = getattr(entry, "media_thumbnail", None)
        if thumbnails:
            image_url = thumbnails[0].get("url", "")

        results.append({
            "id": f"ebay-{item_id}",
            "source": "ebay",
            "title": title,
            "price": price,
            "shipping": None,
            "shipping_confirmed": False,
            "seller_country": "",
            "url": link,
            "image_url": image_url,
            "description": entry.get("summary", "")[:500],
            "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
            "synced_at": datetime.utcnow().isoformat(),
            "is_new": 1,
            "raw": dict(entry),
        })

    return results
