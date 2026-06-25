"""
Seed the database with realistic sample Timex listings for demo purposes.
Called automatically on first run when the database is empty.
Listings use real eBay/Etsy search URLs so "View Listing" links work.
"""
from datetime import datetime, timedelta


def _days_ago(n):
    return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")


SAMPLE_LISTINGS = [
    {
        "id": "ebay-seed-001",
        "source": "ebay",
        "title": "Timex Marlin 1972 Mechanical Hand-Wind Watch — Original Dial",
        "price": 28.0,
        "shipping": 9.0,
        "shipping_confirmed": True,
        "total_cad": 37.0,
        "seller_country": "US",
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+marlin+1972+mechanical",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "Beautiful 1972 Timex Marlin with original hand-wind mechanical movement. Original silver dial in excellent condition. Runs strong. Original bracelet included.",
        "listed_at": _days_ago(1),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
    {
        "id": "ebay-seed-002",
        "source": "ebay",
        "title": "Vintage Timex Marlin Automatic — 1970s Clean Condition",
        "price": 35.0,
        "shipping": 0.0,
        "shipping_confirmed": True,
        "total_cad": 35.0,
        "seller_country": "CA",
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+marlin+automatic+vintage",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "1970s Timex Marlin automatic. Dial is clean with original hands. Movement keeps good time. Selling as-is but in great shape. Ships from Toronto.",
        "listed_at": _days_ago(0),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
    {
        "id": "etsy-seed-003",
        "source": "etsy",
        "title": "Vintage Timex Electric 1960s — Restored, Working",
        "price": 42.0,
        "shipping": None,
        "shipping_confirmed": False,
        "total_cad": 42.0,
        "seller_country": "",
        "customs_warning": False,
        "url": "https://www.etsy.com/ca/search?q=timex+electric+vintage+1960s",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "Gorgeous 1960s Timex Electric in fully restored working condition. Original movement, clean case and dial. A rare find in this condition.",
        "listed_at": _days_ago(2),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
    {
        "id": "ebay-seed-004",
        "source": "ebay",
        "title": "Timex Marlin 1968 Hand-Wind — Silver Dial, Runs Well",
        "price": 22.0,
        "shipping": 12.0,
        "shipping_confirmed": True,
        "total_cad": 34.0,
        "seller_country": "US",
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+marlin+1968",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "1968 Timex Marlin hand-wind. Silver dial with original indices. Movement cleaned and running. Some light wear on case consistent with age. A solid everyday vintage piece.",
        "listed_at": _days_ago(0),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
    {
        "id": "chrono24-seed-005",
        "source": "chrono24",
        "title": "Timex Marlin 34mm Manual Wind — All Original",
        "price": 45.0,
        "shipping": None,
        "shipping_confirmed": False,
        "total_cad": 45.0,
        "seller_country": "",
        "customs_warning": False,
        "url": "https://www.chrono24.com/timex/index.htm",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "Timex Marlin 34mm in all-original condition. Manual wind mechanical movement. Dial has aged beautifully. Original bracelet.",
        "listed_at": _days_ago(3),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
    {
        "id": "ebay-seed-006",
        "source": "ebay",
        "title": "Timex Weekender 38mm — Quartz, Field Watch Style",
        "price": 18.0,
        "shipping": 7.0,
        "shipping_confirmed": True,
        "total_cad": 25.0,
        "seller_country": "US",
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+weekender+field",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "Timex Weekender 38mm field watch style. Quartz movement, NATO strap. Clean dial, working perfectly. Great everyday beater.",
        "listed_at": _days_ago(5),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 0,
    },
    {
        "id": "ebay-seed-007",
        "source": "ebay",
        "title": "Timex Expedition Chronograph — Indiglo, Rubber Strap",
        "price": 20.0,
        "shipping": 6.0,
        "shipping_confirmed": True,
        "total_cad": 26.0,
        "seller_country": "CA",
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+expedition+chronograph",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "Timex Expedition chronograph with Indiglo. Sports watch, rubber strap. Quartz movement running perfectly. Ships from Montreal.",
        "listed_at": _days_ago(7),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 0,
    },
    {
        "id": "ebay-seed-008",
        "source": "ebay",
        "title": "Timex Marlin Mechanical 1975 — Dial Has Patina, Running",
        "price": 15.0,
        "shipping": None,
        "shipping_confirmed": False,
        "total_cad": 27.0,
        "seller_country": "US",
        "customs_warning": False,
        "url": "https://www.ebay.ca/sch/i.html?_nkw=timex+marlin+1975+patina",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Timex_Marlin.jpg/320px-Timex_Marlin.jpg",
        "description": "1975 Timex Marlin mechanical. Dial has some patina and light spotting — adds character. Movement running well. Good project watch or honest daily wearer.",
        "listed_at": _days_ago(1),
        "synced_at": datetime.utcnow().isoformat(),
        "is_new": 1,
    },
]

SAMPLE_SCORES = [
    {"listing_id": "ebay-seed-001", "taste_score": 9.0, "value_score": 5.2, "freshness_score": 7, "final_score": 7.52, "model_id": "Marlin", "reason": "Exactly matches the 70s Marlin reference watches — original dial, hand-wind mechanical, clean condition."},
    {"listing_id": "ebay-seed-002", "taste_score": 8.5, "value_score": 5.0, "freshness_score": 10, "final_score": 7.6, "model_id": "Marlin", "reason": "Canadian seller, automatic Marlin in clean shape — strong taste match and ships locally."},
    {"listing_id": "etsy-seed-003", "taste_score": 8.0, "value_score": 3.2, "freshness_score": 7, "final_score": 6.26, "model_id": "Electric", "reason": "Timex Electric closely matches the Etsy reference watch — rare model in restored working condition."},
    {"listing_id": "ebay-seed-004", "taste_score": 8.5, "value_score": 5.6, "freshness_score": 10, "final_score": 7.76, "model_id": "Marlin", "reason": "1968 Marlin at $34 total is excellent value — matches the reference watches closely in era and style."},
    {"listing_id": "chrono24-seed-005", "taste_score": 8.0, "value_score": 2.0, "freshness_score": 4, "final_score": 5.6, "model_id": "Marlin", "reason": "All-original Marlin is a great taste match but priced near the top of budget and listed 3 days ago."},
    {"listing_id": "ebay-seed-006", "taste_score": 4.0, "value_score": 8.0, "freshness_score": 4, "final_score": 5.2, "model_id": "Weekender", "reason": "Weekender is a different era and style from the mechanical Marlin references — decent watch but not the target."},
    {"listing_id": "ebay-seed-007", "taste_score": 3.0, "value_score": 7.6, "freshness_score": 4, "final_score": 4.12, "model_id": "Expedition", "reason": "Sports Expedition is far from the 70s mechanical Marlin taste profile — wrong era and style."},
    {"listing_id": "ebay-seed-008", "taste_score": 7.5, "value_score": 6.6, "freshness_score": 7, "final_score": 7.18, "model_id": "Marlin", "reason": "1975 Marlin at $27 with honest patina — strong value and good taste match, dial wear keeps it from top tier."},
]


def seed_sample_data(conn) -> int:
    """Insert sample listings and scores if the DB is empty. Returns count added."""
    existing = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    if existing > 0:
        return 0

    now = datetime.utcnow().isoformat()
    for listing in SAMPLE_LISTINGS:
        listing.setdefault("customs_warning", False)
        conn.execute(
            """INSERT OR IGNORE INTO listings
               (id, source, title, price, shipping, shipping_confirmed, total_cad,
                seller_country, url, image_url, description, listed_at, synced_at, is_new)
               VALUES (:id, :source, :title, :price, :shipping, :shipping_confirmed, :total_cad,
                       :seller_country, :url, :image_url, :description, :listed_at, :synced_at, :is_new)""",
            listing,
        )

    for score in SAMPLE_SCORES:
        conn.execute(
            """INSERT OR REPLACE INTO scores
               (listing_id, taste_score, value_score, freshness_score, final_score, model_id, reason, scored_at)
               VALUES (:listing_id, :taste_score, :value_score, :freshness_score, :final_score, :model_id, :reason, :scored_at)""",
            {**score, "scored_at": now},
        )

    conn.commit()
    return len(SAMPLE_LISTINGS)
