import pytest
import sqlite3
from unittest.mock import patch
from datetime import datetime

from db import init_db, get_feed_listings
from sync import run_sync


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    init_db(connection)
    yield connection
    connection.close()


FAKE_LISTING = {
    "id": "ebay-test-001",
    "source": "ebay",
    "title": "Timex Marlin 1972",
    "price": 28.0,
    "shipping": 9.0,
    "shipping_confirmed": True,
    "seller_country": "US",
    "url": "https://www.ebay.ca/itm/test",
    "image_url": "https://i.ebayimg.com/test.jpg",
    "description": "Clean Timex Marlin mechanical.",
    "listed_at": datetime.utcnow().strftime("%Y-%m-%d"),
    "synced_at": datetime.utcnow().isoformat(),
    "is_new": 1,
}


def test_run_sync_saves_new_listings(conn):
    with patch("sync.ebay.fetch_listings", return_value=[FAKE_LISTING]), \
         patch("sync.etsy.fetch_listings", return_value=[]), \
         patch("sync.chrono24.fetch_listings", return_value=[]), \
         patch("sync.score_and_store"):
        count = run_sync(conn)

    assert count == 1
    assert len(get_feed_listings(conn)) == 1


def test_run_sync_deduplicates(conn):
    with patch("sync.ebay.fetch_listings", return_value=[FAKE_LISTING]), \
         patch("sync.etsy.fetch_listings", return_value=[]), \
         patch("sync.chrono24.fetch_listings", return_value=[]), \
         patch("sync.score_and_store"):
        run_sync(conn)
        count = run_sync(conn)  # second sync, same listing

    assert count == 0
    assert len(get_feed_listings(conn)) == 1
