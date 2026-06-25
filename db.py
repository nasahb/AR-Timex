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
    # Migrations for columns added after initial schema
    migrations = [
        "ALTER TABLE preferences ADD COLUMN search_query TEXT DEFAULT 'timex vintage'",
        "ALTER TABLE preferences ADD COLUMN budget_cad REAL DEFAULT 50.0",
        "ALTER TABLE preferences ADD COLUMN movement_pref TEXT DEFAULT 'Any'",
        "ALTER TABLE preferences ADD COLUMN era_prefs TEXT DEFAULT '[]'",
        "ALTER TABLE preferences ADD COLUMN model_prefs TEXT DEFAULT '[]'",
        "ALTER TABLE preferences ADD COLUMN size_pref TEXT DEFAULT 'Any'",
        "ALTER TABLE preferences ADD COLUMN exclude_nonworking INTEGER DEFAULT 1",
        "ALTER TABLE preferences ADD COLUMN exclude_forparts INTEGER DEFAULT 1",
        "ALTER TABLE preferences ADD COLUMN hide_international INTEGER DEFAULT 0",
        "ALTER TABLE listings ADD COLUMN image_urls TEXT DEFAULT '[]'",
        "ALTER TABLE listings ADD COLUMN ai_summary TEXT",
        "ALTER TABLE listings ADD COLUMN detected_movement TEXT",
        "ALTER TABLE listings ADD COLUMN detected_era TEXT",
        "ALTER TABLE listings ADD COLUMN detected_model TEXT",
        "ALTER TABLE listings ADD COLUMN detected_size TEXT",
        "UPDATE listings SET detected_size = NULL WHERE detected_size IN ('Full-size', 'Petite', 'Unisex')",
        "ALTER TABLE preferences ADD COLUMN kijiji_enabled INTEGER DEFAULT 1",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass
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


def update_image_urls(conn: sqlite3.Connection, listing_id: str, urls_json: str) -> None:
    conn.execute("UPDATE listings SET image_urls=? WHERE id=?", (urls_json, listing_id))
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
           chrono24_enabled = :chrono24_enabled,
           kijiji_enabled = :kijiji_enabled,
           search_query = :search_query,
           budget_cad = :budget_cad,
           movement_pref = :movement_pref,
           size_pref = :size_pref,
           era_prefs = :era_prefs,
           model_prefs = :model_prefs,
           exclude_nonworking = :exclude_nonworking,
           exclude_forparts = :exclude_forparts
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


def get_unenriched_ids(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT id FROM listings WHERE ai_summary IS NULL AND detected_size IS NULL"
    ).fetchall()
    return [r["id"] for r in rows]


def save_enrichment(conn: sqlite3.Connection, listing_id: str, result: dict) -> None:
    conn.execute(
        """UPDATE listings SET
           ai_summary = ?, detected_movement = ?, detected_era = ?, detected_model = ?, detected_size = ?
           WHERE id = ?""",
        (
            result.get("summary"),
            result.get("movement"),
            result.get("era"),
            result.get("model"),
            result.get("size"),
            listing_id,
        ),
    )
    conn.commit()


def get_unscored_ids(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """SELECT id FROM listings
           WHERE ai_summary IS NOT NULL
             AND id NOT IN (SELECT listing_id FROM scores)"""
    ).fetchall()
    return [r["id"] for r in rows]


def get_listing_by_id(conn: sqlite3.Connection, listing_id: str):
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return dict(row) if row else None


def get_feed_listings(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """SELECT l.*,
                  CASE WHEN f.listing_id IS NOT NULL THEN 1 ELSE 0 END as is_favourite
           FROM listings l
           LEFT JOIN favourites f ON l.id = f.listing_id
           WHERE l.id NOT IN (SELECT listing_id FROM dismissed)
           ORDER BY l.listed_at DESC, l.synced_at DESC"""
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


def get_source_counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """SELECT source, COUNT(*) as cnt FROM listings
           WHERE id NOT IN (SELECT listing_id FROM dismissed)
           GROUP BY source"""
    ).fetchall()
    return {r["source"]: r["cnt"] for r in rows}


def get_last_synced(conn: sqlite3.Connection):
    row = conn.execute("SELECT last_synced FROM preferences WHERE id = 1").fetchone()
    return row["last_synced"] if row else None


def set_last_synced(conn: sqlite3.Connection, ts: str) -> None:
    conn.execute("UPDATE preferences SET last_synced = ? WHERE id = 1", (ts,))
    conn.commit()
