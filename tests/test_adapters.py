from unittest.mock import patch, MagicMock
from adapters.ebay import fetch_listings as ebay_fetch


def test_ebay_fetch_returns_standard_shape():
    with patch("adapters.ebay.feedparser.parse") as mock_parse:
        entry = MagicMock()
        entry.title = "Timex Marlin 1972 Mechanical Hand-Wind - $28.00"
        entry.link = "https://www.ebay.ca/itm/377073705816"
        entry.get.side_effect = lambda k, d="": {
            "title": entry.title,
            "link": entry.link,
            "summary": "Clean original dial.",
        }.get(k, d)
        entry.media_thumbnail = [{"url": "https://i.ebayimg.com/images/g/xxx/s-l140.jpg"}]
        mock_parse.return_value = MagicMock(entries=[entry])

        results = ebay_fetch("timex marlin", max_results=10)

    assert len(results) == 1
    listing = results[0]
    assert listing["id"] == "ebay-377073705816"
    assert listing["source"] == "ebay"
    assert listing["price"] == 28.0
    assert "ebay" in listing["url"]
    assert listing["image_url"].startswith("https://")
    assert "raw" in listing


def test_ebay_fetch_no_results():
    with patch("adapters.ebay.feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[])
        results = ebay_fetch("timex marlin", max_results=10)
    assert results == []


# ── Etsy ──────────────────────────────────────────────────────────────────

from adapters.etsy import fetch_listings as etsy_fetch

ETSY_HTML = """<html><body>
<div data-listing-id="4469739360"
     data-listing-price="45.00"
     data-listing-title="Vintage Timex Electric Watch 1960s">
  <a href="https://www.etsy.com/ca/listing/4469739360/vintage-timex">Link</a>
  <img src="https://i.etsystatic.com/4469739360-thumb.jpg" />
</div>
</body></html>"""


def test_etsy_fetch_returns_list():
    mock_resp = MagicMock()
    mock_resp.text = ETSY_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("adapters.etsy.requests.get", return_value=mock_resp):
        results = etsy_fetch("timex", max_results=10)

    assert isinstance(results, list)
    for listing in results:
        assert listing["source"] == "etsy"
        assert "id" in listing
        assert "raw" in listing


# ── Chrono24 ──────────────────────────────────────────────────────────────

from adapters.chrono24 import fetch_listings as c24_fetch

CHRONO24_HTML = """
<html><body>
<article class="article-item-container" data-listing-id="123456">
  <a class="js-article-item-container" href="/timex/marlin--id123456.htm">
    <div class="article-title">Timex Marlin Vintage 1970s</div>
    <div class="price">$ 35</div>
    <img src="https://cdn.chrono24.com/images/uhren/123456.jpg" />
  </a>
</article>
</body></html>
"""


def test_chrono24_fetch_returns_standard_shape_or_empty():
    mock_resp = MagicMock()
    mock_resp.text = CHRONO24_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("adapters.chrono24.requests.get", return_value=mock_resp):
        results = c24_fetch("timex", max_results=10)

    assert isinstance(results, list)
    for listing in results:
        assert "id" in listing
        assert listing["source"] == "chrono24"
        assert "raw" in listing
