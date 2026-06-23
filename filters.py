import config


def apply_shipping_logic(listing: dict) -> dict:
    """Fill in total_cad and set customs_warning based on seller country and shipping."""
    result = dict(listing)
    price = result.get("price") or 0.0
    shipping = result.get("shipping")
    country = result.get("seller_country", "")

    result["customs_warning"] = False

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
        # International — flag customs, don't estimate shipping
        result["customs_warning"] = True
        shipping_cost = shipping if shipping is not None else 0.0
        result["total_cad"] = price + shipping_cost

    return result


def passes_hard_filters(listing: dict) -> tuple:
    """Return (True, '') if listing passes all filters, (False, reason) if not."""
    total = listing.get("total_cad", 0.0)
    confirmed = listing.get("shipping_confirmed", True)

    # Budget: only cut listings with confirmed totals over $50 CAD
    if confirmed and total > config.BUDGET_CAD:
        return False, f"Over budget: ${total:.2f} CAD (limit ${config.BUDGET_CAD})"

    # Condition: keyword match on title + description
    text = (listing.get("title", "") + " " + listing.get("description", "")).lower()
    for phrase in config.EXCLUDED_PHRASES:
        if phrase in text:
            return False, f"Condition: excluded phrase '{phrase}' found"

    return True, ""
