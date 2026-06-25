import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import adapters.ebay as ebay
import adapters.etsy as etsy
import adapters.chrono24 as chrono24
import adapters.kijiji as kijiji
import config
from db import get_conn, get_preferences, get_unenriched_ids, set_last_synced, mark_seen
from enricher import enrich_and_store
from filters import apply_shipping_logic, passes_hard_filters

logger = logging.getLogger(__name__)

ENRICH_WORKERS = 8

def run_sync(conn) -> int:
    """Fetch, filter, score, and store new listings. Returns count of new listings saved."""
    # Clear previous new flags before fetching — new listings from THIS sync get is_new=1
    mark_seen(conn)
    prefs = get_preferences(conn)
    search_query = prefs.get("search_query") or "timex vintage"

    PER_SOURCE_CAP = 50

    all_listings = []
    if prefs.get("ebay_enabled", 1):
        all_listings.extend(ebay.fetch_listings(search_query, max_results=PER_SOURCE_CAP))
    if prefs.get("etsy_enabled", 1):
        all_listings.extend(etsy.fetch_listings(search_query, max_results=PER_SOURCE_CAP))
    if prefs.get("chrono24_enabled", 1):
        all_listings.extend(chrono24.fetch_listings(search_query, max_results=PER_SOURCE_CAP))
    if prefs.get("kijiji_enabled", 1):
        all_listings.extend(kijiji.fetch_listings(search_query, max_results=PER_SOURCE_CAP))

    new_count = 0
    for listing in all_listings:
        listing = apply_shipping_logic(listing)
        passed, reason = passes_hard_filters(listing, prefs)
        if not passed:
            logger.debug("Filtered out %s: %s", listing.get("id"), reason)
            continue
        listing.setdefault("image_urls", "[]")
        cursor = conn.execute(
            """INSERT OR IGNORE INTO listings
               (id, source, title, price, shipping, shipping_confirmed, total_cad,
                seller_country, url, image_url, image_urls, description, listed_at, synced_at, is_new)
               VALUES (:id, :source, :title, :price, :shipping, :shipping_confirmed, :total_cad,
                       :seller_country, :url, :image_url, :image_urls, :description, :listed_at, :synced_at, :is_new)""",
            listing,
        )
        conn.commit()
        if cursor.rowcount > 0:
            new_count += 1

    # Enrich listings concurrently — each worker gets its own DB connection
    ids_to_enrich = get_unenriched_ids(conn)
    if ids_to_enrich:
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
        if not db_path:
            set_last_synced(conn, datetime.utcnow().isoformat())
            return new_count

        def _enrich_one(listing_id):
            worker_conn = get_conn(db_path)
            try:
                enrich_and_store(worker_conn, listing_id)
            except Exception as e:
                logger.warning("Failed to enrich %s: %s", listing_id, e)
            finally:
                worker_conn.close()

        with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
            futures = {pool.submit(_enrich_one, lid): lid for lid in ids_to_enrich}
            for future in as_completed(futures):
                future.result()  # surface any uncaught exceptions to the logger

    set_last_synced(conn, datetime.utcnow().isoformat())
    return new_count


