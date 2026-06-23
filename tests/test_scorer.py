from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from scorer import compute_composite, score_with_ai


def test_composite_high_value_fresh():
    listed_at = datetime.utcnow().strftime("%Y-%m-%d")
    result = compute_composite(taste_score=8.0, total_cad=20.0, listed_at=listed_at)
    # value_score = (50 - 20) / 50 * 10 = 6.0
    # freshness_score = 10 (< 24h)
    # final = 8*0.6 + 6*0.3 + 10*0.1 = 4.8 + 1.8 + 1.0 = 7.6
    assert abs(result["value_score"] - 6.0) < 0.01
    assert result["freshness_score"] == 10
    assert abs(result["final_score"] - 7.6) < 0.01


def test_composite_moderate_value_older():
    listed_3_days_ago = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    result = compute_composite(taste_score=5.0, total_cad=40.0, listed_at=listed_3_days_ago)
    # value_score = (50 - 40) / 50 * 10 = 2.0
    # freshness_score = 4 (> 72h)
    # final = 5*0.6 + 2*0.3 + 4*0.1 = 3.0 + 0.6 + 0.4 = 4.0
    assert abs(result["value_score"] - 2.0) < 0.01
    assert result["freshness_score"] == 4
    assert abs(result["final_score"] - 4.0) < 0.01


def test_composite_freshness_medium():
    listed_2_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    result = compute_composite(taste_score=7.0, total_cad=30.0, listed_at=listed_2_days_ago)
    assert result["freshness_score"] == 7


def test_composite_value_clamped_at_zero():
    listed_at = datetime.utcnow().strftime("%Y-%m-%d")
    result = compute_composite(taste_score=9.0, total_cad=80.0, listed_at=listed_at)
    assert result["value_score"] == 0.0


def test_score_with_ai_returns_expected_shape():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"taste_score": 8, "model_id": "Marlin", "reason": "Classic 70s Marlin."}')]

    listing = {
        "title": "Timex Marlin 1972",
        "description": "Clean original dial.",
        "price": 28.0,
        "shipping": 9.0,
        "total_cad": 37.0,
        "source": "ebay",
    }

    with patch("scorer.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response
        result = score_with_ai(listing, taste_description="I love 70s Marlins")

    assert result["taste_score"] == 8
    assert result["model_id"] == "Marlin"
    assert "70s Marlin" in result["reason"]
