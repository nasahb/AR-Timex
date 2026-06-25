import json
from datetime import datetime, timedelta

import anthropic

import config

_SCORING_PROMPT = """You are scoring how well a watch listing matches a collector's specific stated preferences.

SCORING RULES — follow these strictly:
1. The collector's written taste description is the ONLY thing that determines the score.
2. Reference watches are context only — do NOT score higher just because a listing resembles them.
3. If the collector specifies features (e.g. "silver band", "collab", "original dial"), the listing MUST show evidence of those features to score above 5. Absence of a stated preference = penalise hard.
4. Score 8–10 only if the listing explicitly matches most or all stated preferences.
5. Score 3–5 if the listing is a reasonable vintage Timex but doesn't satisfy the stated preferences.
6. Score 1–2 if the stated preferences are clearly absent.

Collector's taste (PRIMARY criterion):
{taste_section}

Reference watches for context only:
{references}

Listing snapshot:
{ai_summary}

Price: ${total_cad:.2f} CAD

Return JSON only — no markdown, no explanation:
{{
  "taste_score": <integer 0-10>,
  "reason": "<one sentence: name the specific preference(s) that match or are missing>"
}}"""


def _build_taste_section(prefs: dict) -> str:
    lines = []
    movement = prefs.get("movement_pref", "Any")
    if movement and movement != "Any":
        lines.append(f"- Movement: {movement} only")
    era_list = json.loads(prefs.get("era_prefs") or "[]")
    if era_list:
        lines.append(f"- Era: {', '.join(era_list)}")
    model_list = json.loads(prefs.get("model_prefs") or "[]")
    if model_list:
        lines.append(f"- Preferred models: {', '.join(model_list)}")
    taste = (prefs.get("taste_description") or "").strip()
    if taste:
        lines.append(f"- In their own words: \"{taste}\"")
    return "\n".join(lines) if lines else "No specific preferences — score on general vintage Timex quality."


def score_with_ai(listing: dict, prefs: dict) -> dict:
    ai_summary = (listing.get("ai_summary") or "").strip()
    if not ai_summary:
        # Fallback for listings not yet enriched
        ai_summary = f"{listing.get('title', '')}. {(listing.get('description', '') or '')[:300]}"

    references = "\n".join(
        f"- {w['title']}: {w['description']}" for w in config.REFERENCE_WATCHES
    )
    prompt = _SCORING_PROMPT.format(
        references=references,
        taste_section=_build_taste_section(prefs),
        ai_summary=ai_summary,
        total_cad=listing.get("total_cad", 0.0),
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    if not raw:
        raise ValueError("Empty response from AI scorer")
    return json.loads(raw)


def compute_composite(taste_score: float, listed_at: str) -> float:
    try:
        listed_date = datetime.strptime(listed_at, "%Y-%m-%d")
    except (ValueError, TypeError):
        listed_date = datetime.utcnow() - timedelta(days=3)
    age_hours = (datetime.utcnow() - listed_date).total_seconds() / 3600
    freshness = 10 if age_hours < 24 else (7 if age_hours < 72 else 4)
    return round(taste_score * 0.9 + freshness * 0.1, 2)


def score_and_store(conn, listing_id: str, prefs: dict) -> None:
    from db import get_listing_by_id, save_score
    listing = get_listing_by_id(conn, listing_id)
    if not listing:
        return
    ai_result = score_with_ai(listing, prefs)
    final_score = compute_composite(
        taste_score=float(ai_result["taste_score"]),
        listed_at=listing.get("listed_at", ""),
    )
    save_score(conn, {
        "listing_id": listing_id,
        "taste_score": float(ai_result["taste_score"]),
        "value_score": None,
        "freshness_score": None,
        "final_score": final_score,
        "model_id": listing.get("detected_model") or ai_result.get("model_id"),
        "reason": ai_result.get("reason", ""),
        "scored_at": datetime.utcnow().isoformat(),
    })
