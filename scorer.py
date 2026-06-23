import json
from datetime import datetime, timedelta

import anthropic

import config


_SCORING_PROMPT = """You are helping a vintage watch collector find listings that match their taste.

The collector loves these three reference watches:
{references}

{taste_section}

Score this listing:
Title: {title}
Description: {description}
Price: ${total_cad:.2f} CAD total
Source: {source}

Return JSON only — no markdown, no explanation, just the JSON object:
{{
  "taste_score": <integer 0-10>,
  "model_id": <"Marlin" | "Weekender" | "Expedition" | "Electric" | "Ironman" | "Easy Reader" | null>,
  "reason": "<one sentence in plain English explaining the score>"
}}

Scoring guide:
- 9-10: Closely matches references (70s/80s mechanical or electric, clean dial, original bracelet)
- 7-8: Strong vintage Timex, good condition signals
- 5-6: Decent vintage Timex but not an obvious taste match
- 3-4: Timex but wrong era or style
- 1-2: Poor match for this collector
- 0: Not a Timex or clearly wrong item"""


def score_with_ai(listing: dict, taste_description: str) -> dict:
    """Call Claude Haiku to score a single listing. Returns taste_score, model_id, reason."""
    references = "\n".join(
        f"- {w['title']}: {w['description']}" for w in config.REFERENCE_WATCHES
    )
    taste_section = (
        f"The collector also says: \"{taste_description}\"" if taste_description.strip() else ""
    )
    prompt = _SCORING_PROMPT.format(
        references=references,
        taste_section=taste_section,
        title=listing.get("title", ""),
        description=(listing.get("description", "") or "")[:500],
        total_cad=listing.get("total_cad", 0.0),
        source=listing.get("source", ""),
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    return json.loads(raw)


def compute_composite(taste_score: float, total_cad: float, listed_at: str) -> dict:
    """Compute value_score, freshness_score, and final_score."""
    value_score = max(0.0, (config.BUDGET_CAD - total_cad) / config.BUDGET_CAD * 10)

    try:
        listed_date = datetime.strptime(listed_at, "%Y-%m-%d")
    except (ValueError, TypeError):
        listed_date = datetime.utcnow() - timedelta(days=3)

    age_hours = (datetime.utcnow() - listed_date).total_seconds() / 3600
    freshness_score = 10 if age_hours < 24 else (7 if age_hours < 72 else 4)

    final_score = (taste_score * 0.6) + (value_score * 0.3) + (freshness_score * 0.1)

    return {
        "value_score": round(value_score, 2),
        "freshness_score": freshness_score,
        "final_score": round(final_score, 2),
    }


def score_and_store(conn, listing_id: str, taste_description: str) -> None:
    """Fetch listing from DB, score with AI, compute composite, save result."""
    from db import get_listing_by_id, save_score

    listing = get_listing_by_id(conn, listing_id)
    if not listing:
        return

    ai_result = score_with_ai(listing, taste_description)
    composite = compute_composite(
        taste_score=float(ai_result["taste_score"]),
        total_cad=listing.get("total_cad") or listing.get("price", 0.0),
        listed_at=listing.get("listed_at", ""),
    )

    save_score(conn, {
        "listing_id": listing_id,
        "taste_score": float(ai_result["taste_score"]),
        "value_score": composite["value_score"],
        "freshness_score": composite["freshness_score"],
        "final_score": composite["final_score"],
        "model_id": ai_result.get("model_id"),
        "reason": ai_result.get("reason", ""),
        "scored_at": datetime.utcnow().isoformat(),
    })
