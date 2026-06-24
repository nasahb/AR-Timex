from datetime import datetime
from db import (
    save_listing, get_new_count, mark_seen, get_preferences,
    save_preferences, save_score, get_unscored_ids, get_listing_by_id,
    get_feed_listings, dismiss_listing, toggle_favourite, get_favourites,
    get_last_synced, set_last_synced,
)

SAMPLE_LISTING = {
    "id": "ebay-100001",
    "source": "ebay",
    "title": "Timex Marlin 1972",
    "price": 28.0,
    "shipping": 9.0,
    "shipping_confirmed": True,
    "total_cad": 37.0,
    "seller_country": "US",
    "url": "https://www.ebay.ca/itm/100001",
    "image_url": "https://i.ebayimg.com/100001.jpg",
    "description": "Clean 1972 Timex Marlin mechanical.",
    "listed_at": "2026-06-22",
    "synced_at": datetime.utcnow().isoformat(),
    "is_new": 1,
}

SAMPLE_SCORE = {
    "listing_id": "ebay-100001",
    "taste_score": 8.0,
    "value_score": 2.6,
    "freshness_score": 7.0,
    "final_score": 6.71,
    "model_id": "Marlin",
    "reason": "Classic 70s Marlin, closely matches reference watches.",
    "scored_at": datetime.utcnow().isoformat(),
}


def test_save_and_retrieve_listing(conn):
    save_listing(conn, SAMPLE_LISTING)
    row = get_listing_by_id(conn, "ebay-100001")
    assert row["title"] == "Timex Marlin 1972"
    assert row["total_cad"] == 37.0


def test_deduplication(conn):
    save_listing(conn, SAMPLE_LISTING)
    save_listing(conn, SAMPLE_LISTING)
    rows = get_feed_listings(conn)
    assert len(rows) == 1


def test_new_count_and_mark_seen(conn):
    save_listing(conn, SAMPLE_LISTING)
    assert get_new_count(conn) == 1
    mark_seen(conn)
    assert get_new_count(conn) == 0


def test_preferences_default(conn):
    prefs = get_preferences(conn)
    assert prefs["threshold"] == 7.5
    assert prefs["ebay_enabled"] == 1


def test_save_preferences(conn):
    save_preferences(conn, {
        "taste_description": "I love Marlins",
        "threshold": 8.0,
        "ebay_enabled": 1,
        "etsy_enabled": 0,
        "chrono24_enabled": 1,
        "kijiji_enabled": 1,
        "search_query": "timex vintage",
        "budget_cad": 50.0,
        "movement_pref": "Any",
        "size_pref": "Any",
        "era_prefs": "[]",
        "model_prefs": "[]",
        "exclude_nonworking": 1,
        "exclude_forparts": 1,
    })
    prefs = get_preferences(conn)
    assert prefs["taste_description"] == "I love Marlins"
    assert prefs["threshold"] == 8.0
    assert prefs["kijiji_enabled"] == 1


def test_save_score_and_unscored(conn):
    save_listing(conn, SAMPLE_LISTING)
    assert "ebay-100001" in get_unscored_ids(conn)
    save_score(conn, SAMPLE_SCORE)
    assert "ebay-100001" not in get_unscored_ids(conn)


def test_dismiss_removes_from_feed(conn):
    save_listing(conn, SAMPLE_LISTING)
    save_score(conn, SAMPLE_SCORE)
    assert len(get_feed_listings(conn)) == 1
    dismiss_listing(conn, "ebay-100001")
    assert len(get_feed_listings(conn)) == 0


def test_toggle_favourite(conn):
    save_listing(conn, SAMPLE_LISTING)
    save_score(conn, SAMPLE_SCORE)
    assert toggle_favourite(conn, "ebay-100001") is True
    assert toggle_favourite(conn, "ebay-100001") is False
    assert toggle_favourite(conn, "ebay-100001") is True
    favs = get_favourites(conn)
    assert len(favs) == 1


def test_last_synced(conn):
    assert get_last_synced(conn) is None
    set_last_synced(conn, "2026-06-23T10:00:00")
    assert get_last_synced(conn) == "2026-06-23T10:00:00"
