import sqlite3
from datetime import datetime


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            price REAL,
            shipping REAL,
            shipping_confirmed INTEGER,
            total_cad REAL,
            seller_country TEXT,
            url TEXT,
            image_url TEXT,
            description TEXT,
            listed_at TEXT,
            synced_at TEXT,
            is_new INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS scores (
            listing_id TEXT PRIMARY KEY,
            taste_score REAL,
            value_score REAL,
            freshness_score REAL,
            final_score REAL,
            model_id TEXT,
            reason TEXT,
            scored_at TEXT
        );

        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY DEFAULT 1,
            taste_description TEXT DEFAULT '',
            threshold REAL DEFAULT 7.5,
            ebay_enabled INTEGER DEFAULT 1,
            etsy_enabled INTEGER DEFAULT 1,
            chrono24_enabled INTEGER DEFAULT 1,
            last_synced TEXT
        );

        CREATE TABLE IF NOT EXISTS dismissed (
            listing_id TEXT PRIMARY KEY,
            dismissed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS favourites (
            listing_id TEXT PRIMARY KEY,
            favourited_at TEXT
        );

        INSERT OR IGNORE INTO preferences (id) VALUES (1);
    """)
    conn.commit()


def save_listing(conn: sqlite3.Connection, listing: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO listings
           (id, source, title, price, shipping, shipping_confirmed, total_cad,
            seller_country, url, image_url, description, listed_at, synced_at, is_new)
           VALUES (:id, :source, :title, :price, :shipping, :shipping_confirmed, :total_cad,
                   :seller_country, :url, :image_url, :description, :listed_at, :synced_at, :is_new)""",
        listing,
    )
    conn.commit()


def get_new_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE is_new = 1 AND id NOT IN (SELECT listing_id FROM dismissed)"
    ).fetchone()
    return row[0]


def mark_seen(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE listings SET is_new = 0")
    conn.commit()


def get_preferences(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM preferences WHERE id = 1").fetchone()
    return dict(row)


def save_preferences(conn: sqlite3.Connection, prefs: dict) -> None:
    conn.execute(
        """UPDATE preferences SET
           taste_description = :taste_description,
           threshold = :threshold,
           ebay_enabled = :ebay_enabled,
           etsy_enabled = :etsy_enabled,
           chrono24_enabled = :chrono24_enabled
           WHERE id = 1""",
        prefs,
    )
    conn.commit()


def save_score(conn: sqlite3.Connection, score: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO scores
           (listing_id, taste_score, value_score, freshness_score, final_score, model_id, reason, scored_at)
           VALUES (:listing_id, :taste_score, :value_score, :freshness_score, :final_score, :model_id, :reason, :scored_at)""",
        score,
    )
    conn.commit()


def get_unscored_ids(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT id FROM listings WHERE id NOT IN (SELECT listing_id FROM scores)"
    ).fetchall()
    return [r["id"] for r in rows]


def get_listing_by_id(conn: sqlite3.Connection, listing_id: str):
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return dict(row) if row else None


def get_feed_listings(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """SELECT l.*, s.taste_score, s.value_score, s.freshness_score,
                  s.final_score, s.model_id, s.reason,
                  CASE WHEN f.listing_id IS NOT NULL THEN 1 ELSE 0 END as is_favourite
           FROM listings l
           LEFT JOIN scores s ON l.id = s.listing_id
           LEFT JOIN favourites f ON l.id = f.listing_id
           WHERE l.id NOT IN (SELECT listing_id FROM dismissed)
           ORDER BY COALESCE(s.final_score, 0) DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def dismiss_listing(conn: sqlite3.Connection, listing_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO dismissed (listing_id, dismissed_at) VALUES (?, ?)",
        (listing_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


def toggle_favourite(conn: sqlite3.Connection, listing_id: str) -> bool:
    exists = conn.execute(
        "SELECT 1 FROM favourites WHERE listing_id = ?", (listing_id,)
    ).fetchone()
    if exists:
        conn.execute("DELETE FROM favourites WHERE listing_id = ?", (listing_id,))
        conn.commit()
        return False
    conn.execute(
        "INSERT INTO favourites (listing_id, favourited_at) VALUES (?, ?)",
        (listing_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    return True


def get_favourites(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """SELECT l.*, s.taste_score, s.value_score, s.freshness_score,
                  s.final_score, s.model_id, s.reason, f.favourited_at,
                  1 as is_favourite
           FROM listings l
           JOIN favourites f ON l.id = f.listing_id
           LEFT JOIN scores s ON l.id = s.listing_id
           ORDER BY f.favourited_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_last_synced(conn: sqlite3.Connection):
    row = conn.execute("SELECT last_synced FROM preferences WHERE id = 1").fetchone()
    return row["last_synced"] if row else None


def set_last_synced(conn: sqlite3.Connection, ts: str) -> None:
    conn.execute("UPDATE preferences SET last_synced = ? WHERE id = 1", (ts,))
    conn.commit()
