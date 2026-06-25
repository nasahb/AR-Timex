import json
import anthropic
import config

_ENRICH_PROMPT = """You are cataloguing a vintage watch listing for a collector's database.

Read this listing carefully and produce a dense, factual snapshot. Only include details present in the listing — never invent. Be specific.

Title: {title}
Description: {description}
Price: ${total_cad:.2f} CAD (source: {source})

Return JSON only — no markdown, no explanation:
{{
  "summary": "<4-6 sentence paragraph covering: movement type and mechanism, case material and condition, dial colour/text style/indices/hands, strap or bracelet type and whether original or aftermarket, overall condition and originality, any special attributes (limited edition, collaboration, NOS, box and papers, rare variant), and any red flags (replaced parts, non-original hands or crown, cracked crystal, service marks, for-parts condition)>",
  "movement": <"Mechanical" | "Automatic" | "Quartz" | "Electric" | null>,
  "era": <"1950s" | "1960s" | "1970s" | "1980s" | "1990s+" | null>,
  "model": <"Marlin" | "Viscount" | "Mercury" | "Sprite" | "Sportster" | "Super Thin" | "21 Jewel" | "Electric" | "Weekender" | "Easy Reader" | "Expedition" | "Ironman" | null>,
  "size": <"Men's" if the listing explicitly uses words like mens, men's, gents, gentleman — "Women's" if it explicitly uses womens, women's, ladies, lady — null if neither is explicitly stated>
}}"""


def enrich_listing(listing: dict) -> dict:
    prompt = _ENRICH_PROMPT.format(
        title=listing.get("title", ""),
        description=(listing.get("description", "") or "")[:800],
        total_cad=listing.get("total_cad", 0.0),
        source=listing.get("source", ""),
    )
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(raw)


def suggest_taste(saves: list) -> dict:
    """Given a list of shortlisted listings, return suggested pill filters and keyword string."""
    from collections import Counter

    # ── Detected-field pills (no AI needed) ─────────────────────────────────
    movements = Counter(l["detected_movement"] for l in saves if l.get("detected_movement"))
    eras      = Counter(l["detected_era"]      for l in saves if l.get("detected_era"))
    models    = Counter(l["detected_model"]    for l in saves if l.get("detected_model"))

    # Suggest plurality winner — must appear more than once OR be the only signal
    def _plurality(counter):
        if not counter:
            return None
        top_val, top_count = counter.most_common(1)[0]
        # Require at least 2 matches, OR be the only value present with 1+ save
        if top_count >= 2 or len(counter) == 1:
            return top_val
        return None

    suggested_movement = _plurality(movements)
    # For multi-select: all values with ≥2 occurrences, or plurality if only 1 unique value
    suggested_eras  = [v for v, c in eras.most_common()   if c >= 2] or ([eras.most_common(1)[0][0]] if len(eras) == 1 else [])
    suggested_models = [v for v, c in models.most_common() if c >= 2] or ([models.most_common(1)[0][0]] if len(models) == 1 else [])

    # ── Keyword suggestion via Haiku ─────────────────────────────────────────
    summaries = [l["ai_summary"] for l in saves if l.get("ai_summary")]
    keyword_suggestion = ""
    if summaries:
        combined = "\n\n".join(f"Watch {i+1}: {s}" for i, s in enumerate(summaries))
        prompt = (
            "A collector has saved these vintage Timex watch listings to their shortlist:\n\n"
            f"{combined}\n\n"
            f"There are {len(summaries)} listings. Identify 2-4 physical attributes or qualities "
            "that appear in MOST or ALL of these listings — shared patterns that reveal this "
            "collector's taste. Only include something if it genuinely recurs across multiple "
            "listings. If the listings are too diverse to find common ground, return fewer terms "
            "or nothing. Ignore generic terms: vintage, Timex, watch, wristwatch, running, works. "
            "Focus on: materials (leather, gold tone, silver), dial features (original, patina, "
            "roman numerals), strap type, condition signals, or notable attributes. "
            "Return ONLY a comma-separated list, nothing else. Example: leather strap, gold tone, original dial"
        )
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}],
        )
        keyword_suggestion = response.content[0].text.strip().strip('"').strip("'")

    return {
        "movement": suggested_movement,
        "eras": suggested_eras,
        "models": suggested_models,
        "keywords": keyword_suggestion,
    }


def enrich_and_store(conn, listing_id: str) -> None:
    from db import get_listing_by_id, save_enrichment
    listing = get_listing_by_id(conn, listing_id)
    if not listing:
        return
    result = enrich_listing(listing)
    save_enrichment(conn, listing_id, result)
