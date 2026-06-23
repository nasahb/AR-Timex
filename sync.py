import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import adapters.ebay as ebay
import adapters.etsy as etsy
import adapters.chrono24 as chrono24
import config
from db import get_preferences, get_unscored_ids, set_last_synced
from filters import apply_shipping_logic, passes_hard_filters
from scorer import score_and_store

logger = logging.getLogger(__name__)

SEARCH_QUERY = "timex vintage"


def run_sync(conn) -> int:
    """Fetch, filter, score, and store new listings. Returns count of new listings saved."""
    prefs = get_preferences(conn)
    taste_description = prefs.get("taste_description", "")

    all_listings = []
    if prefs.get("ebay_enabled", 1):
        all_listings.extend(ebay.fetch_listings(SEARCH_QUERY, max_results=50))
    if prefs.get("etsy_enabled", 1):
        all_listings.extend(etsy.fetch_listings(SEARCH_QUERY, max_results=50))
    if prefs.get("chrono24_enabled", 1):
        all_listings.extend(chrono24.fetch_listings(SEARCH_QUERY, max_results=50))

    new_count = 0
    for listing in all_listings:
        listing = apply_shipping_logic(listing)
        passed, reason = passes_hard_filters(listing)
        if not passed:
            logger.debug("Filtered out %s: %s", listing.get("id"), reason)
            continue
        cursor = conn.execute(
            """INSERT OR IGNORE INTO listings
               (id, source, title, price, shipping, shipping_confirmed, total_cad,
                seller_country, url, image_url, description, listed_at, synced_at, is_new)
               VALUES (:id, :source, :title, :price, :shipping, :shipping_confirmed, :total_cad,
                       :seller_country, :url, :image_url, :description, :listed_at, :synced_at, :is_new)""",
            listing,
        )
        conn.commit()
        if cursor.rowcount > 0:
            new_count += 1

    # Score anything not yet scored
    for listing_id in get_unscored_ids(conn):
        try:
            score_and_store(conn, listing_id, taste_description)
        except Exception as e:
            logger.warning("Failed to score %s: %s", listing_id, e)

    set_last_synced(conn, datetime.utcnow().isoformat())
    return new_count


def start_background_sync(conn) -> BackgroundScheduler:
    """Start a background scheduler that runs run_sync every 30 minutes."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_sync,
        "interval",
        minutes=config.SYNC_INTERVAL_MINUTES,
        args=[conn],
        id="timex_sync",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
