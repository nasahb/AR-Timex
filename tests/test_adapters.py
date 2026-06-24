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

CHRONO24_HTML = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"AggregateOffer","offers":[
  {"@type":"Offer","availability":"http://schema.org/InStock",
   "image":[{"@type":"ImageObject","contentUrl":"https://img.chrono24.com/images/uhren/123456.jpg"}],
   "name":"Timex Marlin Vintage 1970s","price":"35",
   "url":"https://www.chrono24.com/timex/marlin--id123456.htm"}
]}]}
</script>
</head><body></body></html>"""


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


def test_chrono24_uses_scraperapi_when_key_set():
    mock_resp = MagicMock()
    mock_resp.text = CHRONO24_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("adapters.chrono24.config.SCRAPERAPI_KEY", "test-key"), \
         patch("adapters.chrono24.requests.get", return_value=mock_resp) as mock_get:
        results = c24_fetch("timex", max_results=10)

    call_url = mock_get.call_args[0][0]
    assert call_url == "http://api.scraperapi.com/"
    assert mock_get.call_args[1]["params"]["api_key"] == "test-key"
    assert len(results) == 1

# ── Kijiji ────────────────────────────────────────────────────────────────

from adapters.kijiji import fetch_listings as kijiji_fetch

KIJIJI_DESCRIPTION = """
<table>
<tr>
  <td><a href="/v-watches/canada/timex-marlin/1234567890">
    <img src="https://i.ebayimg.com/00/s/abc.jpg" />
  </a></td>
  <td>Price: $45.00<br/>Vintage Timex Marlin in good condition.</td>
</tr>
</table>
"""


def test_kijiji_fetch_returns_standard_shape():
    entry = MagicMock()
    entry.title = "Vintage Timex Marlin"
    entry.link = "https://www.kijiji.ca/v-watches/canada/timex-marlin/1234567890"
    entry.published_parsed = None
    entry.get.side_effect = lambda k, d="": {
        "title": "Vintage Timex Marlin",
        "link": "https://www.kijiji.ca/v-watches/canada/timex-marlin/1234567890",
        "summary": KIJIJI_DESCRIPTION,
    }.get(k, d)

    mock_feed = MagicMock()
    mock_feed.entries = [entry]

    with patch("adapters.kijiji.feedparser.parse", return_value=mock_feed):
        results = kijiji_fetch("timex vintage", max_results=10)

    assert len(results) == 1
    listing = results[0]
    assert listing["id"] == "kijiji-1234567890"
    assert listing["source"] == "kijiji"
    assert listing["price"] == 45.0
    assert listing["seller_country"] == "CA"
    assert "kijiji.ca" in listing["url"]
    assert listing["image_url"] == "https://i.ebayimg.com/00/s/abc.jpg"
    assert '"https://i.ebayimg.com/00/s/abc.jpg"' in listing["image_urls"]
    assert listing["raw"].get("title") == "Vintage Timex Marlin"


def test_kijiji_fetch_empty_on_feedparser_failure():
    with patch("adapters.kijiji.feedparser.parse", side_effect=Exception("network error")):
        results = kijiji_fetch("timex vintage", max_results=10)
    assert results == []


def test_kijiji_fetch_skips_malformed_entries():
    entry_bad = MagicMock()
    entry_bad.get.side_effect = Exception("boom")

    mock_feed = MagicMock()
    mock_feed.entries = [entry_bad]

    with patch("adapters.kijiji.feedparser.parse", return_value=mock_feed):
        results = kijiji_fetch("timex", max_results=10)

    assert results == []
