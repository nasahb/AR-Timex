import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PARSE_API_KEY = os.getenv("PARSE_API_KEY", "")
EBAY_APP_ID = os.getenv("EBAY_APP_ID", "")
EBAY_APP_SECRET = os.getenv("EBAY_APP_SECRET", "")
DB_PATH = os.getenv("DB_PATH", "timex.db")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")

BUDGET_CAD = 50.0
US_SHIPPING_ESTIMATE_CAD = 12.0
