import re
import config

_NONWORKING_PHRASES = [
    "not working", "broken movement", "cracked case", "as-is not working",
    "not running", "doesn't run", "does not run", "non-working", "no works",
]
_FORPARTS_PHRASES = [
    "for parts", "parts only", "parts/repair", "parts or repair",
    "parts & repair", "for repair", "repair only", "as-is for parts",
    "parts repair",
]
# Matches "dial only", "movement only", "case only", "hands only", etc.
_PARTS_COMPONENT_RE = re.compile(
    r'\b(dial|movement|case|crystal|hand|hands|crown|stem|bezel|mainspring|'
    r'gear|spring|parts\s+lot|donor)\s+(only|for\s+parts|lot)\b',
    re.IGNORECASE,
)
_QUERY_STOPWORDS = {"vintage", "watch", "watches", "old", "antique", "rare", "used", "lot", "set"}


def apply_shipping_logic(listing: dict) -> dict:
    result = dict(listing)
    price = result.get("price") or 0.0
    shipping = result.get("shipping")
    country = result.get("seller_country", "")

    if country == "CA":
        shipping_cost = shipping if shipping is not None else 0.0
        result["total_cad"] = price + shipping_cost
        if shipping is None:
            result["shipping_confirmed"] = False

    elif country == "US":
        if shipping is not None:
            result["total_cad"] = price + shipping
        else:
            result["total_cad"] = price + config.US_SHIPPING_ESTIMATE_CAD
            result["shipping_confirmed"] = False

    else:
        shipping_cost = shipping if shipping is not None else 0.0
        result["total_cad"] = price + shipping_cost

    return result


def passes_hard_filters(listing: dict, prefs: dict = None) -> tuple:
    if prefs is None:
        prefs = {}

    budget = prefs.get("budget_cad") or config.BUDGET_CAD
    total = listing.get("total_cad", 0.0)
    if total > budget:
        return False, f"Over budget: ${total:.2f} CAD (limit ${budget:.0f})"

    text = (listing.get("title", "") + " " + listing.get("description", "")).lower()

    if prefs.get("exclude_nonworking", 1):
        for phrase in _NONWORKING_PHRASES:
            if phrase in text:
                return False, f"Condition: '{phrase}'"

    if prefs.get("exclude_forparts", 1):
        for phrase in _FORPARTS_PHRASES:
            if phrase in text:
                return False, f"Condition: '{phrase}'"
        m = _PARTS_COMPONENT_RE.search(text)
        if m:
            return False, f"Component listing: '{m.group(0)}'"

    # Require at least one significant word from the search query to appear in the title
    search_query = (prefs.get("search_query") or "").lower()
    keywords = [w for w in search_query.split() if w not in _QUERY_STOPWORDS and len(w) > 2]
    title = listing.get("title", "").lower()
    if keywords and not any(kw in title for kw in keywords):
        return False, f"Title missing query keyword (expected one of: {', '.join(keywords)})"

    return True, ""
