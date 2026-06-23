from filters import apply_shipping_logic, passes_hard_filters


def _listing(**overrides):
    base = {
        "id": "ebay-1",
        "source": "ebay",
        "title": "Timex Marlin 1972",
        "price": 28.0,
        "shipping": 9.0,
        "shipping_confirmed": True,
        "seller_country": "US",
        "description": "Clean vintage Timex in good working order.",
        "listed_at": "2026-06-22",
    }
    return {**base, **overrides}


def test_confirmed_shipping_sets_total():
    result = apply_shipping_logic(_listing(price=28.0, shipping=9.0, shipping_confirmed=True))
    assert result["total_cad"] == 37.0
    assert result.get("customs_warning") is None or result.get("customs_warning") is False


def test_unknown_shipping_us_estimates_12():
    result = apply_shipping_logic(_listing(price=28.0, shipping=None, shipping_confirmed=False, seller_country="US"))
    assert result["total_cad"] == 40.0
    assert result["shipping_confirmed"] is False


def test_unknown_shipping_ca_sets_zero():
    result = apply_shipping_logic(_listing(price=28.0, shipping=None, shipping_confirmed=False, seller_country="CA"))
    assert result["total_cad"] == 28.0


def test_international_unknown_shipping_sets_customs_warning():
    result = apply_shipping_logic(_listing(price=28.0, shipping=None, shipping_confirmed=False, seller_country="DE"))
    assert result["customs_warning"] is True
    assert result["total_cad"] == 28.0


def test_international_known_shipping_sets_customs_warning():
    result = apply_shipping_logic(_listing(price=20.0, shipping=15.0, shipping_confirmed=True, seller_country="DE"))
    assert result["customs_warning"] is True
    assert result["total_cad"] == 35.0


def test_good_listing_passes():
    listing = apply_shipping_logic(_listing())
    passed, reason = passes_hard_filters(listing)
    assert passed is True
    assert reason == ""


def test_over_budget_confirmed_fails():
    listing = apply_shipping_logic(_listing(price=45.0, shipping=10.0, shipping_confirmed=True))
    passed, reason = passes_hard_filters(listing)
    assert passed is False
    assert "budget" in reason.lower()


def test_over_budget_unconfirmed_passes():
    listing = apply_shipping_logic(_listing(price=45.0, shipping=None, shipping_confirmed=False, seller_country="US"))
    passed, reason = passes_hard_filters(listing)
    assert passed is True


def test_excluded_phrase_in_title_fails():
    listing = apply_shipping_logic(_listing(title="Timex Marlin for parts"))
    passed, reason = passes_hard_filters(listing)
    assert passed is False
    assert "condition" in reason.lower()


def test_excluded_phrase_in_description_fails():
    listing = apply_shipping_logic(_listing(description="Not working, sold as-is not working"))
    passed, reason = passes_hard_filters(listing)
    assert passed is False


def test_needs_battery_passes():
    listing = apply_shipping_logic(_listing(description="Needs battery. Looks great otherwise."))
    passed, reason = passes_hard_filters(listing)
    assert passed is True


def test_crown_stiff_passes():
    listing = apply_shipping_logic(_listing(description="Crown is a bit stiff but movement runs."))
    passed, reason = passes_hard_filters(listing)
    assert passed is True
