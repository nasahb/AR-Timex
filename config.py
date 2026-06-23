import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", "timex.db")

BUDGET_CAD = 50.0
US_SHIPPING_ESTIMATE_CAD = 12.0
SCORE_THRESHOLD = 7.5
SYNC_INTERVAL_MINUTES = 30

# Three reference watches from the brief — seeed the AI's taste profile.
REFERENCE_WATCHES = [
    {
        "url": "https://www.ebay.ca/itm/377073705816",
        "title": "Timex Marlin 1972 Mechanical Hand-Wind",
        "description": "Clean 1970s Timex Marlin with hand-wind mechanical movement, original dial, original bracelet. Classic example of the collector-favorite 70s Marlin.",
    },
    {
        "url": "https://www.ebay.ca/itm/117111976291",
        "title": "Timex Marlin Vintage Mechanical",
        "description": "Vintage Timex Marlin in good condition. Mechanical movement, original dial, presented on original bracelet.",
    },
    {
        "url": "https://www.etsy.com/ca/listing/4469739360",
        "title": "Vintage Timex Electric Watch",
        "description": "1960s/70s Timex Electric with original movement, clean case. Timex Electric models are a rare and desirable part of the vintage Timex lineup.",
    },
]

EXCLUDED_PHRASES = [
    "for parts",
    "not working",
    "broken movement",
    "cracked case",
    "as-is not working",
    "parts only",
]
