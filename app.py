from datetime import datetime

import streamlit as st

import config
from db import (
    get_conn, init_db, get_new_count, mark_seen,
    get_preferences, save_preferences, get_feed_listings,
    get_favourites, dismiss_listing, toggle_favourite, get_last_synced,
)
from sync import run_sync, start_background_sync


# ── helpers ────────────────────────────────────────────────────────────────

def _format_last_synced(ts):
    if not ts:
        return "Never synced"
    try:
        synced = datetime.fromisoformat(ts)
        delta = datetime.utcnow() - synced
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return "Just now"
        if minutes == 1:
            return "1 minute ago"
        if minutes < 60:
            return f"{minutes} minutes ago"
        hours = minutes // 60
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    except Exception:
        return "Unknown"


def _price_display(listing: dict) -> str:
    price = listing.get("price") or 0
    shipping = listing.get("shipping")
    confirmed = listing.get("shipping_confirmed", True)
    total = listing.get("total_cad") or price

    if shipping is not None:
        est = "" if confirmed else " est."
        return f"${price:.0f} + ${shipping:.0f}{est} = **${total:.0f} CAD**"
    return f"**${total:.0f} CAD**"


# ── sidebar ────────────────────────────────────────────────────────────────

def render_sidebar(conn):
    prefs = get_preferences(conn)
    favs = get_favourites(conn)

    with st.sidebar:
        st.title("Timex Watch Finder")

        st.subheader("Your Taste")
        taste = st.text_area(
            "Describe what you love (optional)",
            value=prefs.get("taste_description", ""),
            placeholder="e.g. I love 70s Marlins with original bracelets",
            height=80,
        )

        st.subheader("Reference Watches")
        for ref in config.REFERENCE_WATCHES:
            st.markdown(f"[{ref['title']}]({ref['url']})")

        st.subheader("Sources")
        ebay_on = st.checkbox("eBay", value=bool(prefs.get("ebay_enabled", 1)))
        etsy_on = st.checkbox("Etsy", value=bool(prefs.get("etsy_enabled", 1)))
        c24_on = st.checkbox("Chrono24", value=bool(prefs.get("chrono24_enabled", 1)))

        st.subheader("Score Threshold")
        threshold = st.slider("Min score to be a candidate", 0.0, 10.0,
                              float(prefs.get("threshold", 7.5)), 0.1)

        save_preferences(conn, {
            "taste_description": taste,
            "threshold": threshold,
            "ebay_enabled": int(ebay_on),
            "etsy_enabled": int(etsy_on),
            "chrono24_enabled": int(c24_on),
        })

        st.divider()

        fav_count = len(favs)
        if fav_count > 0:
            if st.button(f"★ Favourites ({fav_count})"):
                st.session_state.view = "favourites"
                st.rerun()
        else:
            st.caption("No favourites yet")

        if st.button("🔄 Refresh Now"):
            with st.spinner("Syncing…"):
                added = run_sync(conn)
            st.success(f"Done — {added} new listing{'s' if added != 1 else ''} added")
            st.rerun()


# ── listing card ───────────────────────────────────────────────────────────

def render_card(listing: dict, conn, dimmed: bool = False, show_compare: bool = False):
    score = listing.get("final_score") or 0
    is_candidate = score >= config.SCORE_THRESHOLD
    border_color = "#2ecc71" if is_candidate else "#555555"
    opacity = "0.65" if dimmed else "1.0"

    st.markdown(
        f'<div style="border-left: 4px solid {border_color}; padding-left: 12px; opacity: {opacity}; margin-bottom: 4px">',
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 3])
    with cols[0]:
        if listing.get("image_url"):
            st.image(listing["image_url"], use_container_width=True)

    with cols[1]:
        # Title line
        title = listing.get("title", "Untitled")
        model = listing.get("model_id")
        badge = " 🆕" if listing.get("is_new") else ""
        model_str = f" · *{model}*" if model else ""
        st.markdown(f"**{title}**{model_str}{badge}")

        # Price
        st.markdown(_price_display(listing))

        # Country / customs
        country = listing.get("seller_country", "")
        if country == "CA":
            st.markdown("🟢 Canadian seller")
        elif listing.get("customs_warning"):
            st.markdown("⚠️ Customs may apply")

        # AI reason
        if listing.get("reason"):
            st.caption(f"*\"{listing['reason']}\"*")

        # Score badge
        if score:
            color = "green" if is_candidate else "gray"
            st.markdown(f"Score: :{color}[**{score:.1f}**]")

        # Actions
        lid = listing["id"]
        action_cols = st.columns(3)
        with action_cols[0]:
            fav_label = "★ Unfavourite" if listing.get("is_favourite") else "☆ Favourite"
            if st.button(fav_label, key=f"fav_{lid}"):
                toggle_favourite(conn, lid)
                st.rerun()
        with action_cols[1]:
            if listing.get("url"):
                st.link_button("View Listing", listing["url"])
        with action_cols[2]:
            if st.button("Not Interested", key=f"dis_{lid}"):
                dismiss_listing(conn, lid)
                st.rerun()

        if show_compare:
            checked = lid in st.session_state.get("compare_ids", [])
            new_val = st.checkbox("Select for comparison", value=checked, key=f"cmp_{lid}")
            if new_val and lid not in st.session_state.compare_ids:
                st.session_state.compare_ids.append(lid)
            elif not new_val and lid in st.session_state.compare_ids:
                st.session_state.compare_ids.remove(lid)

    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()


# ── main feed ──────────────────────────────────────────────────────────────

def render_feed(conn, new_count: int):
    prefs = get_preferences(conn)
    threshold = prefs.get("threshold", config.SCORE_THRESHOLD)

    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"Last synced: {_format_last_synced(get_last_synced(conn))}")
    with col2:
        if new_count > 0:
            st.caption(f"🆕 {new_count} new since your last visit")

    all_listings = get_feed_listings(conn)
    candidates = [l for l in all_listings if (l.get("final_score") or 0) >= threshold]
    rest = [l for l in all_listings if (l.get("final_score") or 0) < threshold]

    if candidates:
        st.subheader(f"★ Purchase Candidates ({len(candidates)})")
        for listing in candidates:
            render_card(listing, conn)
    else:
        st.info("No purchase candidates yet — try clicking Refresh Now, or lower the score threshold in the sidebar.")

    st.markdown(f"--- All Listings · {len(all_listings)} total ---")

    if rest:
        st.subheader(f"All Listings ({len(rest)})")
        for listing in rest:
            render_card(listing, conn, dimmed=True)


# ── favourites view ────────────────────────────────────────────────────────

def render_favourites(conn):
    if st.button("← Back to Feed"):
        st.session_state.view = "feed"
        st.session_state.compare_ids = []
        st.rerun()

    st.header("★ Favourites")
    favs = get_favourites(conn)

    if not favs:
        st.info("You haven't starred any listings yet.")
        return

    for listing in favs:
        render_card(listing, conn, show_compare=True)

    selected = st.session_state.get("compare_ids", [])
    if len(selected) >= 2:
        if st.button(f"Compare {len(selected)} listings"):
            st.session_state.view = "comparison"
            st.rerun()
    elif len(selected) == 1:
        st.caption("Select at least 2 listings to compare")


# ── comparison view ────────────────────────────────────────────────────────

def render_comparison(conn):
    if st.button("← Back to Favourites"):
        st.session_state.view = "favourites"
        st.session_state.compare_ids = []
        st.rerun()

    st.header("Side-by-Side Comparison")
    ids = st.session_state.get("compare_ids", [])[:4]

    if not ids:
        st.warning("No listings selected for comparison.")
        return

    # Build a lookup from feed + favourites
    lookup = {l["id"]: l for l in get_feed_listings(conn)}
    lookup.update({l["id"]: l for l in get_favourites(conn)})

    cols = st.columns(len(ids))
    for col, lid in zip(cols, ids):
        listing = lookup.get(lid)
        if not listing:
            continue
        with col:
            if listing.get("image_url"):
                st.image(listing["image_url"], use_container_width=True)
            st.markdown(f"**{listing.get('title', '')}**")
            if listing.get("model_id"):
                st.caption(listing["model_id"])
            st.markdown(_price_display(listing))
            score = listing.get("final_score")
            if score:
                st.markdown(f"Score: **{score:.1f}**")
            if listing.get("reason"):
                st.caption(f"*\"{listing['reason']}\"*")
            st.caption(f"{listing.get('source', '').capitalize()} · {listing.get('seller_country', '') or 'country unknown'}")
            if listing.get("url"):
                st.link_button("View Listing", listing["url"])


# ── entry point ────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Timex Watch Finder", layout="wide")

    conn = get_conn(config.DB_PATH)
    init_db(conn)

    if "view" not in st.session_state:
        st.session_state.view = "feed"
    if "compare_ids" not in st.session_state:
        st.session_state.compare_ids = []

    # Count new listings once per session before marking them seen
    if "new_count" not in st.session_state:
        st.session_state.new_count = get_new_count(conn)
        mark_seen(conn)

    # Start background sync once per session
    if "scheduler" not in st.session_state:
        st.session_state.scheduler = start_background_sync(conn)

    render_sidebar(conn)

    if st.session_state.view == "comparison":
        render_comparison(conn)
    elif st.session_state.view == "favourites":
        render_favourites(conn)
    else:
        render_feed(conn, st.session_state.new_count)


if __name__ == "__main__":
    main()
