import html as _html
import json
import re
from datetime import datetime
from itertools import zip_longest

import streamlit as st
import streamlit.components.v1 as components  # used for image carousel

import config
from db import (
    get_conn, init_db, get_new_count, mark_seen,
    get_preferences, save_preferences, get_feed_listings,
    get_favourites, dismiss_listing, toggle_favourite,
    get_last_synced, get_source_counts,
)
from sync import run_sync

VERSION = "V0.3"

# ── helpers ──────────────────────────────────────────────────────────────────

def _upgrade_image_url(url: str) -> str:
    if not url:
        return url
    # Etsy: il_255x319. or il_570xN. → il_1588xN.
    if "etsystatic.com" in url:
        return re.sub(r'il_\d+x[Nn\d]+\.', 'il_1588xN.', url)
    # eBay: s-l140.jpg or s-l225.jpg → s-l800.jpg; also strip /thumbs/ path
    if "ebayimg.com" in url:
        url = url.replace("/thumbs/images/", "/images/")
        return re.sub(r's-l\d+\.jpg', 's-l800.jpg', url)
    return url

def _format_last_synced(ts):
    if not ts:
        return "Never synced"
    try:
        synced = datetime.fromisoformat(ts)
        delta = datetime.utcnow() - synced
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes == 1:
            return "1 min ago"
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        return f"{hours}h ago"
    except Exception:
        return "unknown"


def _format_listed_at(listing):
    ts = listing.get("synced_at") or listing.get("listed_at")
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        delta = datetime.utcnow() - dt
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            return "listed just now"
        if hours < 24:
            return f"listed {hours}h ago"
        days = hours // 24
        return f"listed {days}d ago"
    except Exception:
        return ""


def _inject_styles():
    st.html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;1,6..72,300;1,6..72,400;1,6..72,500&family=Geist:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  /* ── Colour ─────────────────────────────────── */
  --bg:           #FAFAF8;    /* near-white, neutral — warmth is typography's job */
  --surface:      #FFFFFF;
  --surface-2:    #F2F2F0;    /* very light neutral gray                          */
  --sidebar-bg:   #F0EFED;    /* sidebar: barely-warmer than page                 */
  --ink:          #111110;    /* near-black                                        */
  --ink-2:        #4A4744;    /* dark warm-neutral gray                            */
  --ink-3:        #928E89;    /* medium warm-neutral gray                          */
  --accent:       #111110;    /* black. no gold. interactive = ink.                */
  --accent-dim:   rgba(17, 17, 16, 0.04);
  --accent-border:rgba(17, 17, 16, 0.18);
  --border:       rgba(17, 17, 16, 0.07);
  --border-md:    rgba(17, 17, 16, 0.13);
  --green:        #2A6E3A;

  /* ── Type scale ─────────────────────────────── */
  --t-xs:    0.6875rem;  /* 11px — chips, meta, breakdown     */
  --t-sm:    0.75rem;    /* 12px — tabs, secondary labels     */
  --t-ui:    0.875rem;   /* 14px — price, buttons, UI labels  */
  --t-body:  1.0625rem;  /* 17px — editorial prose            */
  --t-lead:  1.125rem;   /* 18px — subtitle / lead            */
  --t-sub:   1.75rem;    /* 28px — sidebar title              */
  --t-card:  2.25rem;    /* 36px — card title                 */
  --t-score: 2.625rem;   /* 42px — score display              */
  --t-hero:  4rem;       /* 64px — feed headline              */

  /* ── Line heights ───────────────────────────── */
  --lh-tight:   1.08;
  --lh-heading: 1.18;
  --lh-ui:      1.42;
  --lh-prose:   1.72;

  /* ── Letter spacing ─────────────────────────── */
  --ls-display: -0.032em;
  --ls-heading: -0.025em;
  --ls-ui:       0;
  --ls-label:    0.04em;
  --ls-caps:     0.08em;
}

/* Font rendering */
html, body, [data-testid="stApp"] {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-kerning: normal;
}

/* Sidebar — barely-warmer than page, clean zone */
[data-testid="stSidebar"] { background: var(--sidebar-bg) !important; border-right: 1px solid var(--border-md) !important; }
[data-testid="stSidebar"][aria-expanded="true"] { min-width: 380px !important; max-width: 380px !important; }
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child { width: 380px !important; }
/* ── Sidebar: one label style for every section header ── */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
[data-testid="stSidebar"] .stSlider > label,
[data-testid="stSidebar"] .stTextArea > label,
[data-testid="stSidebar"] .stTextInput > label,
[data-testid="stSidebar"] h3 {
  font-family: 'Geist', sans-serif !important;
  font-size: var(--t-xs) !important;
  letter-spacing: var(--ls-caps) !important;
  text-transform: uppercase !important;
  color: var(--ink-3) !important;
  font-weight: 500 !important;
  margin-top: 0 !important;
  margin-bottom: 6px !important;
  line-height: var(--lh-ui) !important;
}
/* h3 gets extra top margin to breathe above sections */
[data-testid="stSidebar"] h3 {
  margin-top: 20px !important;
}
/* Checkboxes: readable normal-case, not section-label treatment */
[data-testid="stSidebar"] .stCheckbox [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] .stCheckbox [data-testid="stWidgetLabel"] label {
  font-size: var(--t-ui) !important;
  letter-spacing: var(--ls-ui) !important;
  text-transform: none !important;
  color: var(--ink-2) !important;
  font-weight: 400 !important;
}
/* Breathing room between sidebar blocks */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.75rem !important;
}

/* Layout */
.block-container { padding-top: 3rem !important; padding-bottom: 4rem !important; max-width: 820px !important; }
hr { border-color: var(--border) !important; }

/* Info / Alert */
[data-testid="stAlert"] {
  background: var(--surface) !important;
  border: 1px solid var(--border-md) !important;
  border-radius: 6px !important;
}
[data-testid="stAlert"] p { color: var(--ink-2) !important; }

/* Buttons */
[data-testid="stBaseButton-secondary"] {
  background: transparent !important;
  border: 1px solid var(--border-md) !important;
  border-radius: 4px !important;
  color: var(--ink-2) !important;
  font-family: 'Geist', sans-serif !important;
  font-size: var(--t-ui) !important;
  letter-spacing: 0.01em !important;
  height: 40px !important;
  transition: background 0.12s ease, color 0.12s ease !important;
}
[data-testid="stBaseButton-secondary"]:hover {
  background: var(--surface-2) !important;
  color: var(--ink) !important;
}
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {
  border-radius: 4px !important;
  font-family: 'Geist', sans-serif !important;
  font-size: var(--t-ui) !important;
  letter-spacing: 0.01em !important;
  height: 40px !important;
}
/* Dismiss — text-only, no border */
[data-testid="stBaseButton-secondary"]:last-of-type {
  border-color: transparent !important;
  color: var(--ink-3) !important;
}
[data-testid="stBaseButton-secondary"]:last-of-type:hover {
  background: transparent !important;
  color: var(--ink-2) !important;
  border-color: transparent !important;
}

/* Slider track tint */
[data-testid="stSlider"] [data-baseweb="slider"] [role="progressbar"] {
  background: var(--accent) !important;
}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important;
  background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  font-family: 'Geist', sans-serif !important;
  font-size: var(--t-sm) !important;
  letter-spacing: var(--ls-caps) !important;
  text-transform: uppercase !important;
  font-weight: 600 !important;
  color: var(--ink-3) !important;
  padding: 10px 24px !important;
  background: transparent !important;
  border: none !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: var(--ink) !important;
  border-bottom: 2px solid var(--accent) !important;
}

</style>
""")


def _price_line(listing):
    price = listing.get("price") or 0
    shipping = listing.get("shipping")
    confirmed = listing.get("shipping_confirmed", True)
    total = listing.get("total_cad") or price

    sans = "font-family:'Geist',sans-serif; font-size:var(--t-ui); font-feature-settings:'tnum' 1;"
    muted = "color:var(--ink-3);"
    est = "" if confirmed else " est."
    ship_style = f"{muted} font-style:italic;" if not confirmed else muted

    if shipping is not None:
        parts = [
            f'<span style="{sans} color:var(--ink-2);">${price:.0f}</span>',
            f'<span style="{sans} {muted}"> + </span>',
            f'<span style="{sans} {ship_style}">${shipping:.0f}{est} ship</span>',
            f'<span style="{sans} {muted}"> = </span>',
            f'<span style="{sans} font-weight:600; color:var(--ink);">${total:.0f} CAD</span>',
        ]
    else:
        parts = [f'<span style="{sans} font-weight:600; color:var(--ink);">${total:.0f} CAD</span>']

    return "".join(parts)


# ── sidebar ───────────────────────────────────────────────────────────────────

CLOCK_SVG = (
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
    'style="display:inline-block; vertical-align:middle; margin-right:9px; margin-bottom:2px;" '
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M12 8v4l2.5 2"/>'
    '</svg>'
)


def render_sidebar(conn):
    prefs = get_preferences(conn)
    favs = get_favourites(conn)
    counts = get_source_counts(conn)

    # Apply pending suggestion BEFORE any widgets render (Streamlit forbids setting
    # widget keys after the widget is instantiated in the same run). Pop first to
    # force Streamlit to treat each pill as a fresh widget with the new default.
    pending = st.session_state.pop("_pending_suggestion", None)
    if pending:
        movement_val = pending.get("movement")
        era_val = pending.get("eras") or ["Any"]
        models_val = pending.get("models") or ["Any"]
        kw_val = pending.get("keywords", "")

        for k in ("sb_movement", "_sb_movement_prev", "sb_era", "_sb_era_prev", "sb_models", "_sb_models_prev", "sb_taste"):
            st.session_state.pop(k, None)

        if movement_val:
            st.session_state["sb_movement"] = [movement_val]
            st.session_state["_sb_movement_prev"] = [movement_val]
        else:
            st.session_state["sb_movement"] = ["Any"]
            st.session_state["_sb_movement_prev"] = ["Any"]
        st.session_state["sb_era"] = era_val
        st.session_state["_sb_era_prev"] = era_val
        st.session_state["sb_models"] = models_val
        st.session_state["_sb_models_prev"] = models_val
        if kw_val:
            st.session_state["sb_taste"] = kw_val
            st.session_state["sb_taste_match_any"] = True

        # Toast summarises what was found — helps diagnose when pills don't change
        pill_parts = []
        if movement_val: pill_parts.append(f"Movement → {movement_val}")
        if era_val != ["Any"]: pill_parts.append(f"Era → {', '.join(era_val)}")
        if models_val != ["Any"]: pill_parts.append(f"Model → {', '.join(models_val)}")

        if pill_parts or kw_val:
            msg = "Filters updated: " + " · ".join(pill_parts)
            if kw_val:
                msg += (" · " if pill_parts else "") + f"Keywords → {kw_val}"
        else:
            msg = "Shortlist too diverse for pill filters — save more similar watches to build a pattern"
        st.toast(msg)

    with st.sidebar:
        sans = "font-family:'Geist',sans-serif;"
        st.markdown(
            f'<div style="margin-bottom:16px;">'
            f'  <div style="display:flex; align-items:center; margin-bottom:2px;">'
            f'    <span style="color:var(--ink);">{CLOCK_SVG}</span>'
            f'    <span style="font-family:\'Newsreader\',serif; font-size:28px; font-weight:500; color:var(--ink);">Timex Watch Finder</span>'
            f'  </div>'
            f'  <div style="{sans} font-size:var(--t-xs); letter-spacing:var(--ls-caps); color:var(--ink-3); text-transform:uppercase; padding-left:29px;">Vintage Timex · {VERSION}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ✦ Suggest — only shown when shortlist has 2+ saves
        if len(favs) >= 2:
            _pill = (
                "display:inline-flex;align-items:center;gap:5px;"
                "padding:4px 12px;border-radius:100px;"
                "border:1px solid #6B3FA0;background:transparent;"
                "cursor:pointer;font-family:'Geist',sans-serif;"
                "font-size:0.6875rem;letter-spacing:0.08em;text-transform:uppercase;"
                "color:#111110;transition:opacity 120ms ease;margin-bottom:2px;"
            )
            st.markdown(
                f'<style>#sb-suggest-pill{{display:inline-flex;}}'
                f'section[data-testid="stSidebar"] .stMarkdown:has(#sb-suggest-pill){{margin-bottom:0!important;}}</style>'
                f'<button id="sb-suggest-pill" style="{_pill}">✦&thinsp;Suggest</button>',
                unsafe_allow_html=True,
            )
            if st.button("SBSUGGEST", key="sb_suggest"):
                from enricher import suggest_taste
                suggestion = suggest_taste(favs)
                st.session_state["_pending_suggestion"] = suggestion
                st.rerun()
            components.html("""<script>
(function(){
  var p=window.parent.document;
  function hideAndWire(){
    p.querySelectorAll('button').forEach(function(b){
      if(b.textContent.trim()==='SBSUGGEST'){
        var el=b;
        for(var i=0;i<6;i++){
          if(!el.parentElement)break;
          el=el.parentElement;
          var ti=el.getAttribute('data-testid')||'';
          if(ti==='stBaseButtonContainer'||ti==='stButton'||ti==='element-container'){
            el.style.cssText='display:none!important;height:0!important;overflow:hidden!important;';
            break;
          }
        }
      }
    });
    var pill=p.getElementById('sb-suggest-pill');
    if(pill&&!pill._wired){
      pill.addEventListener('click',function(){
        p.querySelectorAll('button').forEach(function(b){
          if(b.textContent.trim()==='SBSUGGEST')b.click();
        });
      });
      pill.addEventListener('mouseover',function(){pill.style.opacity='0.55';});
      pill.addEventListener('mouseout',function(){pill.style.opacity='1';});
      pill._wired=true;
    }
    return pill;
  }
  var n=0;
  function tryWire(){if(hideAndWire()||n++>25)return;setTimeout(tryWire,80);}
  tryWire();
  [100,300,700].forEach(function(t){setTimeout(hideAndWire,t);});
})();
</script>""", height=1)

        # Movement — multi select with Any-exclusivity
        _movement_raw = prefs.get("movement_pref") or "Any"
        try:
            _movement_parsed = json.loads(_movement_raw)
            _movement_init = _movement_parsed if isinstance(_movement_parsed, list) else [_movement_parsed]
        except Exception:
            _movement_init = [_movement_raw] if _movement_raw and _movement_raw != "Any" else ["Any"]
        if "sb_movement" not in st.session_state:
            st.session_state["sb_movement"] = _movement_init

        def _movement_on_change():
            cur = list(st.session_state.get("sb_movement") or [])
            prev = list(st.session_state.get("_sb_movement_prev") or ["Any"])
            if not cur:
                st.session_state["sb_movement"] = ["Any"]
            elif "Any" in cur and "Any" not in prev:
                st.session_state["sb_movement"] = ["Any"]
            elif "Any" in cur and len(cur) > 1:
                st.session_state["sb_movement"] = [v for v in cur if v != "Any"]
            st.session_state["_sb_movement_prev"] = list(st.session_state["sb_movement"])

        if "_sb_movement_prev" not in st.session_state:
            st.session_state["_sb_movement_prev"] = list(st.session_state["sb_movement"])

        movement_prefs_raw = st.pills(
            "Movement",
            ["Any", "Mechanical", "Automatic", "Electric", "Quartz"],
            selection_mode="multi",
            key="sb_movement",
            on_change=_movement_on_change,
        ) or ["Any"]
        movement_pref = "Any" if "Any" in movement_prefs_raw else movement_prefs_raw

        if "sb_size" not in st.session_state:
            st.session_state["sb_size"] = prefs.get("size_pref") or "Any"
        size_pref = st.pills(
            "Type",
            ["Any", "Men's", "Women's"],
            selection_mode="single",
            key="sb_size",
        ) or "Any"

        # Era — multi select with Any-exclusivity
        _era_saved = json.loads(prefs.get("era_prefs") or "[]")
        if "sb_era" not in st.session_state:
            st.session_state["sb_era"] = _era_saved if _era_saved else ["Any"]

        def _era_on_change():
            cur = list(st.session_state.get("sb_era") or [])
            prev = list(st.session_state.get("_sb_era_prev") or ["Any"])
            if not cur:
                st.session_state["sb_era"] = ["Any"]
            elif "Any" in cur and "Any" not in prev:
                st.session_state["sb_era"] = ["Any"]
            elif "Any" in cur and len(cur) > 1:
                st.session_state["sb_era"] = [v for v in cur if v != "Any"]
            st.session_state["_sb_era_prev"] = list(st.session_state["sb_era"])

        if "_sb_era_prev" not in st.session_state:
            st.session_state["_sb_era_prev"] = list(st.session_state["sb_era"])

        era_prefs_raw = st.pills(
            "Era",
            ["Any", "1950s", "1960s", "1970s", "1980s", "1990s+"],
            selection_mode="multi",
            key="sb_era",
            on_change=_era_on_change,
        ) or ["Any"]
        era_prefs = [] if "Any" in era_prefs_raw else list(era_prefs_raw)

        # Models — multi select with Any-exclusivity
        _ALL_MODELS = ["Marlin", "Viscount", "Mercury", "Sprite", "Sportster", "Super Thin", "21 Jewel", "Electric", "Weekender", "Easy Reader", "Expedition", "Ironman"]
        _models_saved = json.loads(prefs.get("model_prefs") or "[]")
        if "custom_models" not in st.session_state:
            st.session_state.custom_models = [m for m in _models_saved if m not in _ALL_MODELS]

        _pill_options = ["Any"] + _ALL_MODELS + st.session_state.custom_models
        if "sb_models" not in st.session_state:
            _known_saved = [m for m in _models_saved if m in _pill_options]
            st.session_state["sb_models"] = _known_saved if _known_saved else ["Any"]

        def _models_on_change():
            cur = list(st.session_state.get("sb_models") or [])
            prev = list(st.session_state.get("_sb_models_prev") or ["Any"])
            if not cur:
                st.session_state["sb_models"] = ["Any"]
            elif "Any" in cur and "Any" not in prev:
                st.session_state["sb_models"] = ["Any"]
            elif "Any" in cur and len(cur) > 1:
                st.session_state["sb_models"] = [v for v in cur if v != "Any"]
            st.session_state["_sb_models_prev"] = list(st.session_state["sb_models"])

        if "_sb_models_prev" not in st.session_state:
            st.session_state["_sb_models_prev"] = list(st.session_state["sb_models"])

        def _add_custom_model():
            val = st.session_state.sb_model_input.strip()
            if val and val not in st.session_state.custom_models and val not in _ALL_MODELS:
                st.session_state.custom_models.append(val)
                current = [m for m in (st.session_state.get("sb_models") or []) if m != "Any"]
                st.session_state["sb_models"] = current + [val]
                st.session_state["_sb_models_prev"] = list(st.session_state["sb_models"])
            st.session_state.sb_model_input = ""

        model_prefs_raw = st.pills(
            "Models",
            _pill_options,
            selection_mode="multi",
            key="sb_models",
            on_change=_models_on_change,
        ) or ["Any"]
        st.text_input(
            "Add model",
            placeholder="Don't see your model? Add it here…",
            key="sb_model_input",
            on_change=_add_custom_model,
            label_visibility="collapsed",
        )
        model_prefs = [] if "Any" in model_prefs_raw else list(model_prefs_raw)

        st.markdown(
            f'<div style="{sans} font-size:var(--t-xs); letter-spacing:var(--ls-caps); text-transform:uppercase; '
            f'color:var(--ink-3); font-weight:500; margin-top:20px; margin-bottom:4px;">Keyword filter</div>',
            unsafe_allow_html=True,
        )
        st.markdown("""
<style>
section[data-testid="stSidebar"] div[data-testid="InputInstructions"] {
    font-size: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="InputInstructions"]::after {
    content: "↵";
    font-size: 12px;
    color: #928E89;
    font-family: 'Geist', sans-serif;
}
</style>""", unsafe_allow_html=True)
        def _taste_on_change():
            st.session_state["sb_taste_match_any"] = False  # manual edit → reset to AND

        taste = st.text_input(
            "keyword_filter",
            value=prefs.get("taste_description", ""),
            placeholder="leather strap, original dial, collab",
            label_visibility="collapsed",
            key="sb_taste",
            on_change=_taste_on_change,
        )
        match_any = st.session_state.get("sb_taste_match_any", False)
        _and_bg  = "#111110" if not match_any else "transparent"
        _and_col = "#F0EFED" if not match_any else "#928E89"
        _or_bg   = "#111110" if match_any else "transparent"
        _or_col  = "#F0EFED" if match_any else "#928E89"
        _pill_s  = ("font-family:'Geist',sans-serif;font-size:9px;letter-spacing:0.07em;"
                    "text-transform:uppercase;padding:3px 10px;border:none;cursor:pointer;"
                    "transition:background 120ms ease,color 120ms ease;line-height:1;")
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'margin-top:4px;margin-bottom:10px;">'
            f'  <span style="font-family:\'Geist\',sans-serif;font-size:var(--t-xs);'
            f'color:var(--ink-3);line-height:1.4;">Comma-separate terms · partial words work</span>'
            f'  <div style="display:inline-flex;border:1px solid rgba(17,17,16,0.18);'
            f'border-radius:3px;overflow:hidden;flex-shrink:0;margin-left:8px;">'
            f'    <button id="taste-and-pill" style="{_pill_s}background:{_and_bg};color:{_and_col};">AND</button>'
            f'    <button id="taste-or-pill"  style="{_pill_s}background:{_or_bg};color:{_or_col};">OR</button>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("TASTEAND", key="taste_mode_and"):
            st.session_state["sb_taste_match_any"] = False
            st.rerun()
        if st.button("TASTEOR", key="taste_mode_or"):
            st.session_state["sb_taste_match_any"] = True
            st.rerun()
        components.html("""<script>
(function(){
  var p=window.parent.document;
  function clickBtn(text){
    p.querySelectorAll('button').forEach(function(b){
      if(b.textContent.trim()===text)b.click();
    });
  }
  function hideAndWire(){
    p.querySelectorAll('button').forEach(function(b){
      var t=b.textContent.trim();
      if(t==='TASTEAND'||t==='TASTEOR'){
        var el=b;
        for(var i=0;i<6;i++){
          if(!el.parentElement)break;
          el=el.parentElement;
          var ti=el.getAttribute('data-testid')||'';
          if(ti==='stBaseButtonContainer'||ti==='stButton'||ti==='element-container'){
            el.style.cssText='display:none!important;height:0!important;overflow:hidden!important;';
            break;
          }
        }
      }
    });
    var a=p.getElementById('taste-and-pill');
    var o=p.getElementById('taste-or-pill');
    if(a&&!a._wired){a.addEventListener('click',function(){clickBtn('TASTEAND');});a._wired=true;}
    if(o&&!o._wired){o.addEventListener('click',function(){clickBtn('TASTEOR');});o._wired=true;}
    return a&&o;
  }
  var n=0;
  function tryWire(){if(hideAndWire()||n++>25)return;setTimeout(tryWire,80);}
  tryWire();
  [100,300,700].forEach(function(t){setTimeout(hideAndWire,t);});
})();
</script>""", height=1)


        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

        if "sb_budget" not in st.session_state:
            st.session_state["sb_budget"] = int(prefs.get("budget_cad") or config.BUDGET_CAD)
        budget_cad = st.slider(
            "Max price (CAD)",
            min_value=10, max_value=500,
            step=5,
            key="sb_budget",
        )
        st.markdown(
            f'<div style="{sans} font-size:var(--t-xs); letter-spacing:var(--ls-caps); text-transform:uppercase; '
            f'color:var(--ink-3); font-weight:500; margin-top:20px; margin-bottom:8px;">Sources</div>',
            unsafe_allow_html=True,
        )
        if "sb_ebay" not in st.session_state:
            st.session_state["sb_ebay"] = bool(prefs.get("ebay_enabled", 1))
        ebay_on = st.checkbox("eBay", key="sb_ebay")

        if "sb_etsy" not in st.session_state:
            st.session_state["sb_etsy"] = bool(prefs.get("etsy_enabled", 1))
        etsy_on = st.checkbox("Etsy", key="sb_etsy")

        if "sb_c24" not in st.session_state:
            st.session_state["sb_c24"] = bool(prefs.get("chrono24_enabled", 1))
        c24_on = st.checkbox("Chrono24", key="sb_c24")

        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

        if "sb_search_query" not in st.session_state:
            st.session_state["sb_search_query"] = prefs.get("search_query") or "timex vintage"
        search_query = st.text_input(
            "Search query",
            key="sb_search_query",
            help="Sent to eBay/Chrono24 at sync time. Broad terms work best — filtering happens locally.",
        )

        save_preferences(conn, {
            "taste_description": taste,
            "ebay_enabled": int(ebay_on),
            "etsy_enabled": int(etsy_on),
            "chrono24_enabled": int(c24_on),
            "kijiji_enabled": 0,
            "search_query": search_query,
            "budget_cad": float(budget_cad),
            "movement_pref": json.dumps(movement_pref) if isinstance(movement_pref, list) else (movement_pref or "Any"),
            "size_pref": size_pref,
            "era_prefs": json.dumps(era_prefs),
            "model_prefs": json.dumps(model_prefs),
            "exclude_nonworking": 1,
            "exclude_forparts": 1,
        })

        # Hidden buttons — JS hides them visually and clicks them for navigation/sync
        if st.button("Sync now", key="sidebar_sync", use_container_width=True):
            with st.spinner("Syncing…"):
                run_sync(conn)
            st.session_state.new_count = get_new_count(conn)
            st.rerun()
        if st.button("NAVFEED", key="nav_feed"):
            st.session_state.view = "feed"
            st.rerun()
        if st.button("NAVFAVS", key="nav_favs"):
            st.session_state.view = "favourites"
            st.rerun()

        fav_count = st.session_state.get("fav_count", len(favs))
        fav_nav = f"Shortlist ({fav_count})" if fav_count else "Shortlist"
        current_view = st.session_state.get("view", "feed")
        feed_active = "t-active" if current_view == "feed" else ""
        favs_active = "t-active" if current_view == "favourites" else ""
        synced_str = _format_last_synced(get_last_synced(conn))

        components.html(f"""<script>
(function() {{
  var p = window.parent.document;

  ['timex-strip', 'timex-strip-css'].forEach(function(id) {{
    var el = p.getElementById(id); if (el) el.remove();
  }});

  var style = p.createElement('style');
  style.id = 'timex-strip-css';
  style.textContent = `
    footer[data-testid="stFooter"] {{ display: none !important; }}
    #timex-strip {{
      position: fixed; top: 44px; left: 380px; right: 0;
      height: 40px; background: #F0EFED;
      border-bottom: 1px solid rgba(17,17,16,0.10);
      display: flex; align-items: center;
      justify-content: space-between; padding: 0 48px;
      z-index: 100; box-sizing: border-box;
      transition: left 200ms ease;
    }}
    .t-nav {{ display: flex; gap: 28px; align-items: center; }}
    .t-btn {{
      background: none; border: none; padding: 0; cursor: pointer;
      font-family: 'Geist', sans-serif; font-size: 0.6875rem;
      letter-spacing: 0.08em; text-transform: uppercase;
      color: #928E89; transition: color 120ms ease;
    }}
    .t-btn:hover {{ color: #111110; }}
    .t-btn.t-active {{ color: #111110; font-weight: 600; }}
    .t-btn.t-sync {{ color: #111110; font-weight: 500; }}
    .t-btn.t-sync:hover {{ opacity: 0.55; }}
    .t-right {{ display: flex; align-items: center; gap: 20px; }}
    .t-synced {{
      font-family: 'Geist', sans-serif; font-size: 0.625rem;
      letter-spacing: 0.06em; text-transform: uppercase; color: #C2BAB0;
    }}
    [data-testid="stMain"] {{ padding-top: 40px !important; }}
  `;
  p.head.appendChild(style);

  // Measure actual header height
  var headerEl = p.querySelector('[data-testid="stHeader"]');
  var headerH = headerEl ? headerEl.getBoundingClientRect().height : 44;

  var strip = p.createElement('div');
  strip.id = 'timex-strip';
  strip.style.top = headerH + 'px';
  strip.innerHTML =
    '<div class="t-nav">' +
      '<button class="t-btn {feed_active}" id="ts-feed">Feed</button>' +
      '<button class="t-btn {favs_active}" id="ts-favs">{fav_nav}</button>' +
    '</div>' +
    '<div class="t-right">' +
      '<span class="t-synced">Synced {synced_str}</span>' +
      '<button class="t-btn t-sync" id="ts-sync">Sync</button>' +
    '</div>';
  p.body.appendChild(strip);

  function clickSidebarBtn(label) {{
    var btns = p.querySelectorAll('[data-testid="stSidebar"] button');
    for (var i = 0; i < btns.length; i++) {{
      if (btns[i].textContent.trim() === label) {{ btns[i].click(); return; }}
    }}
  }}

  // Hide the sidebar trigger buttons
  ['Sync now', 'NAVFEED', 'NAVFAVS'].forEach(function(label) {{
    var btns = p.querySelectorAll('[data-testid="stSidebar"] button');
    for (var i = 0; i < btns.length; i++) {{
      if (btns[i].textContent.trim() === label) {{
        var wrap = btns[i].closest('[data-testid="stBaseButtonContainer"]') || btns[i].parentElement;
        if (wrap) wrap.style.cssText = 'height:0;overflow:hidden;margin:0;padding:0;';
        break;
      }}
    }}
  }});

  p.getElementById('ts-feed').addEventListener('click', function() {{ clickSidebarBtn('NAVFEED'); }});
  p.getElementById('ts-favs').addEventListener('click', function() {{ clickSidebarBtn('NAVFAVS'); }});
  p.getElementById('ts-sync').addEventListener('click', function() {{ clickSidebarBtn('Sync now'); }});

  // Adjust strip left when sidebar collapses/expands
  function syncStripLeft() {{
    var sb = p.querySelector('[data-testid="stSidebar"]');
    var s = p.getElementById('timex-strip');
    if (!sb || !s) return;
    s.style.left = sb.getAttribute('aria-expanded') === 'false' ? '0px' : '380px';
  }}
  syncStripLeft();
  var sb = p.querySelector('[data-testid="stSidebar"]');
  if (sb) new MutationObserver(syncStripLeft).observe(sb, {{attributes: true, attributeFilter: ['aria-expanded']}});
}})();
</script>""", height=1)


# ── image carousel ────────────────────────────────────────────────────────────

def _render_carousel(images: list, listing_id: str, is_new: bool = False) -> None:
    """Render image(s). Single image stays in markdown (CSS vars work). Multiple images
    use st.html() so JavaScript navigation works without triggering a Streamlit rerun."""
    if not images:
        st.markdown(
            '<div style="width:100%;aspect-ratio:3/2;border-radius:3px;overflow:hidden;position:relative;'
            'background:repeating-linear-gradient(45deg,var(--surface-2),var(--surface-2) 1.5px,var(--bg) 1.5px,var(--bg) 18px);">'
            '<div style="position:absolute;bottom:14px;left:14px;'
            'font-family:\'Geist\',sans-serif;font-size:9px;color:var(--ink-3);">No image</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    new_badge_md = (
        '<div style="position:absolute;top:10px;left:10px;z-index:2;">'
        '<span style="font-family:\'Geist\',sans-serif;font-size:9px;font-weight:700;'
        'letter-spacing:0.1em;padding:3px 8px;background:var(--ink);color:var(--surface);'
        'border-radius:2px;text-transform:uppercase;">New</span></div>'
    ) if is_new else ""

    if len(images) == 1:
        st.markdown(
            f'<div style="position:relative;margin-bottom:24px;">'
            f'<img src="{_html.escape(images[0])}" alt="Watch listing photo" '
            f'style="width:100%;aspect-ratio:3/2;object-fit:cover;display:block;border-radius:3px;">'
            f'{new_badge_md}</div>',
            unsafe_allow_html=True,
        )
        return

    # Multiple images — self-contained JS carousel in an iframe
    n = len(images)
    lid_safe = re.sub(r'[^a-zA-Z0-9]', '_', listing_id)
    imgs_json = json.dumps(images)
    new_badge_html = (
        "<div style='position:absolute;top:10px;left:10px;z-index:2;'>"
        "<span style='font-family:-apple-system,system-ui,sans-serif;font-size:9px;font-weight:700;"
        "letter-spacing:0.1em;padding:3px 8px;background:#111110;color:#fff;"
        "border-radius:2px;text-transform:uppercase;'>New</span></div>"
    ) if is_new else ""

    html = f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;overflow:hidden;font-family:-apple-system,system-ui,sans-serif}}
.car{{position:relative;width:100%;border-radius:3px;overflow:hidden}}
.car img{{width:100%;height:420px;object-fit:cover;display:block;transition:opacity 0.15s ease}}
.car img.fading{{opacity:0.35}}
.nav{{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);
      display:flex;align-items:center;gap:10px;
      background:rgba(17,17,16,0.58);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
      border-radius:100px;padding:5px 14px}}
.btn{{background:none;border:none;cursor:pointer;color:rgba(255,255,255,0.75);
      font-size:15px;line-height:1;padding:2px 3px}}
.btn:hover{{color:#fff}}
.btn:disabled{{opacity:0.2;cursor:default}}
.cnt{{color:rgba(255,255,255,0.88);font-size:11px;font-weight:500;
      letter-spacing:0.06em;font-feature-settings:'tnum' 1;white-space:nowrap}}
</style></head><body>
<div class="car">
  <img id="i{lid_safe}" src="{_html.escape(images[0])}" alt="Watch photo">
  {new_badge_html}
  <div class="nav">
    <button class="btn" id="p{lid_safe}" onclick="go(-1)" disabled>&#8592;</button>
    <span class="cnt" id="c{lid_safe}">1&#8202;&#47;&#8202;{n}</span>
    <button class="btn" id="n{lid_safe}" onclick="go(1)">&#8594;</button>
  </div>
</div>
<script>
const imgs={imgs_json},
  img=document.getElementById('i{lid_safe}'),
  cnt=document.getElementById('c{lid_safe}'),
  prev=document.getElementById('p{lid_safe}'),
  nxt=document.getElementById('n{lid_safe}');
let idx=0;
function go(d){{
  img.classList.add('fading');
  setTimeout(()=>{{
    idx=Math.max(0,Math.min(imgs.length-1,idx+d));
    img.src=imgs[idx];
    img.onload=img.onerror=()=>img.classList.remove('fading');
    cnt.textContent=(idx+1)+' / '+imgs.length;
    prev.disabled=idx===0;
    nxt.disabled=idx===imgs.length-1;
  }},100);
}}
</script></body></html>"""

    components.html(html, height=435)


# ── candidate card ────────────────────────────────────────────────────────────

def render_candidate_card(listing, conn):
    source = _html.escape((listing.get("source") or "").upper())
    model = _html.escape(listing.get("model_id") or "")
    title = _html.escape(listing.get("title") or "Untitled")
    ai_summary = _html.escape(listing.get("ai_summary") or "")
    is_new = listing.get("is_new")
    listed_str = _format_listed_at(listing)

    sans = "font-family:'Geist',sans-serif;"

    # Build merged image list (stored gallery + primary fallback)
    try:
        all_images = json.loads(listing.get("image_urls") or "[]")
    except Exception:
        all_images = []
    all_images = [_upgrade_image_url(u) for u in all_images if u]
    primary = _upgrade_image_url(listing.get("image_url") or "")
    if primary and primary not in all_images:
        all_images.insert(0, primary)
    elif not all_images and primary:
        all_images = [primary]

    chip = (
        f"font-family:'Geist',sans-serif; font-size:var(--t-xs); font-weight:600; letter-spacing:var(--ls-caps); "
        f"padding:3px 9px; border-radius:3px; display:inline-block; white-space:nowrap;"
    )
    source_chip = f'<span style="{chip} background:var(--surface-2); color:var(--ink-2);">{source}</span>'
    model_chip = (
        f'<span style="{chip} background:var(--accent-dim); color:var(--accent); margin-left:5px;">'
        f'{model}</span>'
        if model else ""
    )
    listed_text = (
        f'<span style="font-family:\'Geist\',sans-serif; font-size:var(--t-xs); color:var(--ink-3); margin-left:8px;">'
        f'{listed_str}</span>'
        if listed_str else ""
    )

    summary_html = (
        f'<p style="font-family:\'Newsreader\',serif; font-size:var(--t-lead); font-weight:300; '
        f'line-height:var(--lh-prose); margin:22px 0 0; color:var(--ink); max-width:65ch; '
        f'font-optical-sizing:auto; text-wrap:pretty;">{ai_summary}</p>'
        if ai_summary else ""
    )

    lid = listing["id"]

    # Card separator
    st.markdown(
        '<div style="border-top:1px solid var(--border); height:48px;"></div>',
        unsafe_allow_html=True,
    )

    # Image / carousel
    _render_carousel(all_images, lid, is_new=bool(is_new))

    # Card body
    st.markdown(
        f'<div style="padding:20px 0 48px;">'
        f'  <div style="display:flex; align-items:center; gap:8px; margin-bottom:16px; flex-wrap:wrap;">'
        f'    {source_chip}{model_chip}{listed_text}'
        f'  </div>'
        f'  <h2 style="font-family:\'Newsreader\',serif; font-size:var(--t-card); font-weight:400; '
        f'letter-spacing:var(--ls-heading); margin:0 0 22px; line-height:var(--lh-heading); color:var(--ink); '
        f'text-wrap:balance; max-width:760px; font-optical-sizing:auto;">{title}</h2>'
        f'  {_price_line(listing)}'
        f'  {summary_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    url = listing.get("url", "#")
    is_fav = bool(listing.get("is_favourite"))
    fav_label = "Saved" if is_fav else "Save"
    _ab  = "display:flex;border:1px solid rgba(17,17,16,0.10);margin-top:8px;"
    _base = ("font-family:'Geist',sans-serif;font-size:0.6875rem;letter-spacing:0.08em;"
             "text-transform:uppercase;background:none;border:none;cursor:pointer;"
             "display:flex;align-items:center;justify-content:center;"
             "padding:10px 0;transition:opacity 120ms ease;text-decoration:none;")
    st.markdown(
        f'<div style="{_ab}">'
        f'  <a href="{url}" style="{_base}flex:2;border-right:1px solid rgba(17,17,16,0.10);background:#111110;color:#FAFAF8;" target="_blank">View listing</a>'
        f'  <button id="edfav-{lid}" style="{_base}flex:1;border-right:1px solid rgba(17,17,16,0.10);color:#928E89;">{fav_label}</button>'
        f'  <button id="eddis-{lid}" style="{_base}flex:1;color:#928E89;">Dismiss</button>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button(f"EDFAV_{lid}", key=f"edfav_{lid}"):
        toggle_favourite(conn, lid)
        st.session_state["fav_count"] = conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0]
        st.rerun()
    if st.button(f"EDDIS_{lid}", key=f"eddis_{lid}"):
        dismiss_listing(conn, lid)
        st.rerun()


# ── listing modal ─────────────────────────────────────────────────────────────

@st.dialog(" ", width="large")
def _show_listing_modal(listing, conn):
    lid = listing["id"]
    source = _html.escape((listing.get("source") or "").upper())
    model = _html.escape(listing.get("detected_model") or "")
    title = _html.escape(listing.get("title") or "Untitled")
    ai_summary = _html.escape(listing.get("ai_summary") or "")
    listed_str = _format_listed_at(listing)
    is_new = listing.get("is_new")
    fav_label = "Saved" if listing.get("is_favourite") else "Save"
    url = listing.get("url") or ""
    total = listing.get("total_cad") or listing.get("price") or 0
    price = listing.get("price") or 0
    shipping = listing.get("shipping")

    primary = _upgrade_image_url(listing.get("image_url") or "")
    image_html = (
        f'<img src="{primary}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:4px;display:block;">'
        if primary else
        f'<div style="width:100%;height:100%;border-radius:4px;'
        f'background:repeating-linear-gradient(45deg,#D9D0BE,#D9D0BE 1px,var(--surface) 1px,var(--surface) 14px);"></div>'
    )
    new_badge = (
        '<span style="font-family:\'Geist\',sans-serif;font-size:0.6rem;font-weight:700;'
        'letter-spacing:0.1em;padding:2px 6px;background:var(--ink);color:var(--surface);'
        'border-radius:2px;margin-left:4px;">NEW</span>'
        if is_new else ""
    )

    sans = "font-family:'Geist',sans-serif;"
    chip_base = "font-family:'Geist',sans-serif;font-size:0.6rem;font-weight:700;letter-spacing:0.08em;padding:2px 8px;border-radius:3px;display:inline-block;"
    source_chip = f'<span style="{chip_base}background:var(--surface-2);color:var(--ink-2);">{source}</span>'
    model_chip = f'<span style="{chip_base}background:var(--accent-dim);color:var(--accent);margin-left:5px;">{model}</span>' if model else ""
    listed_text = f'<span style="{sans}font-size:0.7rem;color:var(--ink-3);margin-left:8px;">{listed_str}</span>' if listed_str else ""

    ship_txt = f" + ${shipping:.0f} ship" if shipping else ""
    price_html = (
        f'<div style="{sans}font-size:0.85rem;color:var(--ink-2);margin:10px 0 0;">'
        f'${price:.0f}{ship_txt} = <strong style="color:var(--ink);">${total:.0f} CAD</strong></div>'
    )
    summary_html = (
        f'<p style="font-family:\'Newsreader\',serif;font-size:1rem;font-weight:300;'
        f'line-height:1.5;margin:10px 0 0;color:var(--ink);font-optical-sizing:auto;'
        f'display:-webkit-box;-webkit-line-clamp:10;-webkit-box-orient:vertical;overflow:hidden;">{ai_summary}</p>'
        if ai_summary else ""
    )
    mab = ("font-family:'Geist',sans-serif;font-size:0.6875rem;letter-spacing:0.08em;"
           "text-transform:uppercase;background:none;border:none;"
           "cursor:pointer;padding:10px 0;transition:opacity 120ms ease;text-decoration:none;"
           "display:flex;align-items:center;justify-content:center;")

    st.markdown(
        # Force dialog wider/shorter via CSS
        f'<style>'
        f'div[data-testid="stDialog"]>div>div{{max-width:720px!important;width:720px!important;}}'
        f'div[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"],'
        f'div[data-testid="stDialog"] [data-testid="stVerticalBlock"]>div:last-child{{padding-bottom:0!important;margin-bottom:0!important;}}'
        f'div[data-testid="stDialog"] .stElementContainer:last-child,'
        f'div[data-testid="stDialog"] [data-testid="stIFrame"]{{margin-bottom:0!important;padding-bottom:0!important;}}'
        f'</style>'
        # Side-by-side layout: image left, content right
        f'<div style="display:grid;grid-template-columns:220px 1fr;gap:20px;align-items:start;">'
        f'  <div style="height:320px;">{image_html}</div>'
        f'  <div style="min-width:0;">'
        f'    <div style="display:flex;align-items:center;flex-wrap:wrap;margin-bottom:10px;">'
        f'      {source_chip}{model_chip}{new_badge}{listed_text}'
        f'    </div>'
        f'    <h2 style="font-family:\'Newsreader\',serif;font-size:1.35rem;font-weight:400;'
        f'letter-spacing:-0.01em;margin:0;line-height:1.25;color:var(--ink);'
        f'display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;'
        f'font-optical-sizing:auto;">{title}</h2>'
        f'    {price_html}'
        f'    {summary_html}'
        f'  </div>'
        f'</div>'
        # Action bar
        f'<div style="display:flex;border:1px solid rgba(17,17,16,0.10);margin-top:16px;">'
        f'  <a href="{url}" style="{mab}flex:2;border-right:1px solid rgba(17,17,16,0.10);background:#111110;color:#FAFAF8;" target="_blank">View listing</a>'
        f'  <button style="{mab}flex:1;border-right:1px solid rgba(17,17,16,0.10);color:#928E89;" id="mmfav-{lid}">{fav_label}</button>'
        f'  <button style="{mab}flex:1;color:#928E89;" id="mmdis-{lid}">Dismiss</button>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Hidden Streamlit buttons wired up by JS below
    if st.button(f"MMFAV_{lid}", key=f"mmfav_{lid}"):
        toggle_favourite(conn, lid)
        st.session_state["fav_count"] = conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0]
        st.rerun()
    if st.button(f"MMDIS_{lid}", key=f"mmdis_{lid}"):
        dismiss_listing(conn, lid)
        st.rerun()
    components.html(f"""<script>
(function() {{
  var p = window.parent.document;
  function clickHidden(text) {{
    p.querySelectorAll('button').forEach(function(b) {{
      if (b.textContent.trim() === text) b.click();
    }});
  }}
  function hideControlButtons() {{
    ['MMFAV_{lid}', 'MMDIS_{lid}'].forEach(function(label) {{
      p.querySelectorAll('button').forEach(function(b) {{
        if (b.textContent.trim() === label) {{
          var el = b;
          for (var i = 0; i < 6; i++) {{
            if (!el.parentElement) break;
            el = el.parentElement;
            var ti = el.getAttribute('data-testid') || '';
            if (ti === 'stBaseButtonContainer' || ti === 'stButton' || ti === 'element-container') {{
              el.style.cssText = 'display:none!important;height:0;overflow:hidden;margin:0;padding:0;';
              break;
            }}
          }}
          b.style.cssText = 'display:none!important;';
        }}
      }});
    }});
  }}
  hideControlButtons();
  [100, 300, 700, 1500].forEach(function(t) {{ setTimeout(hideControlButtons, t); }});
  function wireModal() {{
    var fav = p.getElementById('mmfav-{lid}');
    var dis = p.getElementById('mmdis-{lid}');
    if (!fav && !dis) {{ setTimeout(wireModal, 60); return; }}
    if (fav && !fav._mmWired) {{
      fav._mmWired = true;
      fav.addEventListener('click', function() {{ clickHidden('MMFAV_{lid}'); }});
    }}
    if (dis && !dis._mmWired) {{
      dis._mmWired = true;
      dis.addEventListener('click', function() {{ clickHidden('MMDIS_{lid}'); }});
    }}
  }}
  wireModal();
}})();
</script>""", height=0)


# ── compact card ──────────────────────────────────────────────────────────────

def render_compact_card(listing, conn):
    lid = listing["id"]
    source = _html.escape((listing.get("source") or "").upper())
    model = _html.escape(listing.get("model_id") or listing.get("detected_model") or "")
    title = _html.escape(listing.get("title") or "Untitled")
    card_text = _html.escape(listing.get("ai_summary") or "")
    image_url = _upgrade_image_url(listing.get("image_url") or "")
    is_new = listing.get("is_new")
    total = listing.get("total_cad") or listing.get("price") or 0
    listed_str = _format_listed_at(listing)
    url = listing.get("url") or ""
    fav_label = "Saved" if listing.get("is_favourite") else "Save"

    sans = "font-family:'Geist',sans-serif;"
    cab = ("font-family:'Geist',sans-serif;font-size:0.6875rem;letter-spacing:0.08em;"
           "text-transform:uppercase;background:none;border:none;"
           "cursor:pointer;padding:10px 0;transition:opacity 120ms ease;"
           "display:flex;align-items:center;justify-content:center;")

    new_badge = (
        f'<span style="{sans} font-size:var(--t-xs); font-weight:600; letter-spacing:var(--ls-caps); '
        f'padding:2px 6px; background:var(--ink); color:var(--surface); border-radius:2px; margin-left:4px;">NEW</span>'
        if is_new else ""
    )
    model_chip = (
        f'<span style="{sans} font-size:var(--t-xs); color:var(--accent); letter-spacing:var(--ls-caps); font-weight:600;">{model}</span>'
        if model else ""
    )
    meta_sep = " · " if model and listed_str else ""
    listed_html = f'<span style="{sans} font-size:var(--t-xs); color:var(--ink-3);">{meta_sep}{listed_str}</span>' if listed_str else ""

    image_html = (
        f'<img src="{image_url}" alt="" style="width:100%; border-radius:3px; object-fit:cover; aspect-ratio:1; display:block;">'
        if image_url else
        f'<div style="width:100%; aspect-ratio:1; border-radius:3px; '
        f'background:repeating-linear-gradient(45deg,#D9D0BE,#D9D0BE 1px,var(--surface) 1px,var(--surface) 14px);"></div>'
    )
    summary_html = (
        f'<div style="height:4.2em; overflow:hidden; margin-top:6px;">'
        f'<p style="font-family:\'Newsreader\',serif; font-size:var(--t-sm); font-weight:300; '
        f'line-height:1.4; margin:0; color:var(--ink); font-optical-sizing:auto; '
        f'display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;">{card_text}</p>'
        f'</div>'
        if card_text else '<div style="height:4.2em;"></div>'
    )

    st.markdown(
        f'<div id="cc-{lid}" style="background:var(--surface); border:1px solid var(--border-md); '
        f'border-radius:5px; margin-bottom:4px; cursor:pointer; transition:box-shadow 150ms ease;">'
        f'  <div style="padding:14px; display:grid; grid-template-columns:80px 1fr; gap:12px;">'
        f'    <div>{image_html}</div>'
        f'    <div style="min-width:0;">'
        f'      <div style="display:flex; align-items:center; gap:4px; margin-bottom:5px; flex-wrap:wrap;">'
        f'        <span style="{sans} font-size:var(--t-xs); color:var(--ink-3); letter-spacing:var(--ls-caps);">{source}</span>'
        f'        {model_chip}{new_badge}{listed_html}'
        f'      </div>'
        f'      <h3 style="font-family:\'Newsreader\',serif; font-size:var(--t-ui); font-weight:400; '
        f'line-height:var(--lh-heading); margin:0 0 5px; color:var(--ink); font-optical-sizing:auto; '
        f'display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">{title}</h3>'
        f'      <div style="{sans} font-size:var(--t-ui); font-weight:600; color:var(--ink); '
        f'font-feature-settings:\'tnum\' 1; margin-bottom:3px;">${total:.0f} CAD</div>'
        f'      {summary_html}'
        f'    </div>'
        f'  </div>'
        f'  <div style="display:flex;border:1px solid rgba(17,17,16,0.10);">'
        f'    <a href="{url}" id="ccview-{lid}" style="{cab}flex:2;border-right:1px solid rgba(17,17,16,0.10);background:#111110;color:#FAFAF8;text-decoration:none;" target="_blank">View listing</a>'
        f'    <button id="ccfav-{lid}" style="{cab}flex:1;border-right:1px solid rgba(17,17,16,0.10);color:#928E89;">{fav_label}</button>'
        f'    <button id="ccdis-{lid}" style="{cab}flex:1;color:#928E89;">Dismiss</button>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Hidden Streamlit buttons — JS wires card body click + action bar buttons to these
    if st.button(f"CCOPEN_{lid}", key=f"ccopen_{lid}"):
        _show_listing_modal(listing, conn)
    if st.button(f"CCFAV_{lid}", key=f"ccfav_{lid}"):
        toggle_favourite(conn, lid)
        st.session_state["fav_count"] = conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0]
        st.rerun()
    if st.button(f"CCDIS_{lid}", key=f"ccdis_{lid}"):
        dismiss_listing(conn, lid)
        st.rerun()


def _inject_card_js(lids: list):
    if not lids:
        return
    lids_js = json.dumps(lids)
    components.html(f"""<script>
(function() {{
  var p = window.parent.document;

  function clickHidden(text) {{
    p.querySelectorAll('button').forEach(function(b) {{
      if (b.textContent.trim() === text) b.click();
    }});
  }}

  // Hide ghost control buttons — walk up the DOM tree to find the outermost
  // Streamlit wrapper and collapse it entirely
  function hideControlButtons() {{
    p.querySelectorAll('button').forEach(function(b) {{
      var t = b.textContent.trim();
      if (t.startsWith('CCOPEN_') || t.startsWith('CCFAV_') || t.startsWith('CCDIS_')) {{
        var el = b;
        // Walk up until we hit a direct child of the column or block container
        for (var i = 0; i < 6; i++) {{
          if (!el.parentElement) break;
          el = el.parentElement;
          var ti = el.getAttribute('data-testid') || '';
          if (ti === 'stBaseButtonContainer' || ti === 'stButton' || ti === 'element-container') {{
            el.style.cssText = 'display:none!important;height:0;overflow:hidden;margin:0;padding:0;';
            break;
          }}
        }}
        // Fallback: hide the button itself
        b.style.cssText = 'display:none!important;';
      }}
    }});
  }}

  // Run hiding immediately and at intervals (page may still be hydrating)
  hideControlButtons();
  [100, 300, 700, 1500].forEach(function(t) {{ setTimeout(hideControlButtons, t); }});

  function wireCards() {{
    var wired = 0;
    {lids_js}.forEach(function(lid) {{
      var card = p.getElementById('cc-' + lid);
      if (!card || card._ccWired) return;
      card._ccWired = true;
      wired++;

      card.addEventListener('mouseenter', function() {{
        card.style.boxShadow = '0 2px 10px rgba(17,17,16,0.10)';
      }});
      card.addEventListener('mouseleave', function() {{
        card.style.boxShadow = 'none';
      }});

      card.addEventListener('click', function(e) {{
        if (e.target.closest('[id^="ccfav-"],[id^="ccview-"],[id^="ccdis-"]')) return;
        clickHidden('CCOPEN_' + lid);
      }});

      var fav = p.getElementById('ccfav-' + lid);
      if (fav) fav.addEventListener('click', function(e) {{
        e.stopPropagation();
        clickHidden('CCFAV_' + lid);
      }});

      var dis = p.getElementById('ccdis-' + lid);
      if (dis) dis.addEventListener('click', function(e) {{
        e.stopPropagation();
        clickHidden('CCDIS_' + lid);
      }});
    }});
    return wired;
  }}

  var wireAttempts = 0;
  function tryWire() {{
    if (wireCards() > 0 || wireAttempts++ > 25) return;
    setTimeout(tryWire, 80);
  }}
  tryWire();
}})();
</script>""", height=0)


# ── main feed ─────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'is', 'was', 'are', 'were', 'be', 'been', 'has', 'had',
    'it', 'its', 'this', 'that', 'from', 'by', 'as', 'up', 'if', 'no',
})


def _search_summaries(listings: list, query: str, match_any: bool = False) -> list:
    """
    Comma-separated terms. match_any=False → AND (all must match, default for manual entry).
    match_any=True → OR (any term matches, used for shortlist suggestions).
    Partial words work: 'mech' matches 'mechanical'.
    """
    if not query.strip():
        return listings
    terms = [t.strip().lower() for t in query.split(',') if t.strip()]
    if not terms:
        return listings

    result = []
    for listing in listings:
        searchable = ' '.join([
            listing.get('ai_summary') or '',
            listing.get('title') or '',
            (listing.get('description') or '')[:300],
            listing.get('detected_model') or '',
            listing.get('detected_movement') or '',
            listing.get('detected_era') or '',
            listing.get('detected_size') or '',
        ]).lower()

        def term_matches(term):
            words = [w for w in term.split() if w not in _STOPWORDS and len(w) >= 2]
            return not words or all(w in searchable for w in words)

        if match_any:
            matched = any(term_matches(t) for t in terms)
        else:
            matched = all(term_matches(t) for t in terms)

        if matched:
            result.append(listing)
    return result


def _apply_display_filters(listings, movement_pref, size_pref, era_prefs, model_prefs):
    if movement_pref and movement_pref != "Any":
        if isinstance(movement_pref, list):
            listings = [l for l in listings if (l.get("detected_movement") or "") in movement_pref]
        else:
            listings = [l for l in listings if (l.get("detected_movement") or "").lower() == movement_pref.lower()]
    if size_pref and size_pref != "Any":
        listings = [l for l in listings if (l.get("detected_size") or "").lower() == size_pref.lower()]
    if era_prefs:
        listings = [l for l in listings if l.get("detected_era") in era_prefs]
    if model_prefs:
        listings = [l for l in listings
                    if l.get("detected_model") in model_prefs or l.get("model_id") in model_prefs]
    return listings


def render_feed(conn, new_count):
    prefs = get_preferences(conn)

    movement_prefs_raw = list(st.session_state.get("sb_movement") or ["Any"])
    movement_pref = "Any" if "Any" in movement_prefs_raw else movement_prefs_raw
    size_pref = st.session_state.get("sb_size") or "Any"
    era_prefs_raw = list(st.session_state.get("sb_era") or ["Any"])
    era_prefs = [] if "Any" in era_prefs_raw else era_prefs_raw
    model_prefs_raw = list(st.session_state.get("sb_models") or ["Any"])
    model_prefs = [] if "Any" in model_prefs_raw else model_prefs_raw
    keyword = (st.session_state.get("sb_taste") or prefs.get("taste_description") or "").strip()
    match_any = st.session_state.get("sb_taste_match_any", False)
    budget_cad = float(prefs.get("budget_cad") or config.BUDGET_CAD)

    from filters import _FORPARTS_PHRASES, _NONWORKING_PHRASES, _PARTS_COMPONENT_RE

    def _is_bad_listing(l):
        # Check title + description + ai_summary for parts/non-working signals
        text = ' '.join([
            l.get('title') or '',
            l.get('description') or '',
            l.get('ai_summary') or '',
        ]).lower()
        if any(p in text for p in _FORPARTS_PHRASES + _NONWORKING_PHRASES):
            return True
        if _PARTS_COMPONENT_RE.search(text):
            return True
        return False

    raw_listings = get_feed_listings(conn)[:100]

    hard_filtered = [l for l in raw_listings
                     if (l.get("total_cad") or 0) <= budget_cad and not _is_bad_listing(l)]
    pill_filtered = _apply_display_filters(hard_filtered, movement_pref, size_pref, era_prefs, model_prefs)

    EDITORIAL_N = 10
    sans = "font-family:'Geist',sans-serif;"

    # Compact filter label, e.g. "Mechanical · Marlin · 1970s"
    _filter_parts = []
    if movement_pref and movement_pref != "Any":
        _filter_parts.extend(movement_pref if isinstance(movement_pref, list) else [movement_pref])
    if size_pref and size_pref != "Any":
        _filter_parts.append(size_pref)
    if era_prefs:
        _filter_parts.extend(era_prefs)
    if model_prefs:
        _filter_parts.extend(model_prefs)
    filter_label = ' · '.join(_filter_parts)
    active_filters = bool(_filter_parts)

    terms = ', '.join(f'"{t.strip()}"' for t in keyword.split(',') if t.strip()) if keyword else ""

    # New listings that pass current filters
    new_matching = [l for l in pill_filtered if l.get("is_new")]

    if keyword:
        keyword_matches = _search_summaries(pill_filtered, keyword, match_any=match_any)
        # Among keyword matches, surface new ones first
        new_in_kw = [l for l in keyword_matches if l.get("is_new")]
        editorial = new_in_kw if new_in_kw else keyword_matches
        rest = [l for l in pill_filtered if l["id"] not in {m["id"] for m in editorial}]
    elif new_matching:
        # New listings drive the editorial when no keyword active
        editorial = new_matching[:EDITORIAL_N]
        rest = [l for l in pill_filtered if l["id"] not in {m["id"] for m in editorial}]
    else:
        editorial = pill_filtered[:EDITORIAL_N]
        rest = pill_filtered[EDITORIAL_N:]

    # Headline + subtitle
    if not raw_listings:
        headline = "No listings yet."
        subtitle = "Hit Sync to fetch listings."
    elif keyword and editorial:
        n_new = len([l for l in editorial if l.get("is_new")])
        n = len(keyword_matches)
        if n_new:
            headline = f"{n_new} new listing{'s' if n_new != 1 else ''} matching {terms}."
            rest_note = f" · {n - n_new} older matches below" if n > n_new else ""
        else:
            headline = f"{n} listing{'s' if n != 1 else ''} matching {terms}."
            rest_note = f" · {len(rest)} others below" if rest else ""
        subtitle = (f"{filter_label} · filtered from {len(pill_filtered)}{rest_note}"
                    if filter_label else f"Filtered from {len(pill_filtered)}{rest_note}")
    elif keyword and not editorial:
        headline = "No matches found."
        subtitle = (f"{filter_label} · {terms} didn't match anything"
                    if filter_label else f"{terms} didn't appear in any current listing — try different keywords")
    elif new_matching:
        n_new = len(new_matching)
        headline = f"{min(n_new, EDITORIAL_N)} new since last sync."
        rest_note = f" · {len(rest)} older listings below" if rest else ""
        subtitle = (f"{filter_label}{rest_note}" if filter_label else f"{len(pill_filtered)} total{rest_note}")
    elif active_filters and editorial:
        n = len(pill_filtered)
        headline = f"{len(editorial)} of {n} listings."
        subtitle = f"{filter_label} · newest first · add keywords to narrow further"
    elif editorial:
        n = len(pill_filtered)
        headline = f"{len(editorial)} of {n} listings."
        subtitle = "Newest first · use filters and keywords to narrow"
    else:
        headline = "Nothing matches your current filters."
        subtitle = f"{filter_label} · try widening the filters or budget" if filter_label else "Try widening the filters or budget"

    st.markdown(
        f'<div style="margin-bottom:48px;">'
        f'  <h1 style="font-family:\'Newsreader\',serif; font-size:var(--t-hero); font-weight:400; '
        f'letter-spacing:var(--ls-display); margin:0; line-height:var(--lh-tight); color:var(--ink); '
        f'text-wrap:balance; font-optical-sizing:auto;">{_html.escape(headline)}</h1>'
        f'  <p style="font-family:\'Geist\',sans-serif; font-size:var(--t-ui); '
        f'color:var(--ink-3); margin:14px 0 0; line-height:var(--lh-ui); '
        f'letter-spacing:var(--ls-ui);">{_html.escape(subtitle)}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Editorial cards — keyword matches when searching, top 10 by recency otherwise
    for listing in editorial:
        render_candidate_card(listing, conn)

    # Divider between editorial and the rest
    PAGE_SIZE = 6
    if editorial and rest:
        rest_label = f"{len(rest)} more listing{'s' if len(rest) != 1 else ''}"
        st.markdown(
            f'<div style="margin:48px 0 24px; display:flex; align-items:center; gap:16px;">'
            f'  <div style="flex:1; height:1px; background:var(--border);"></div>'
            f'  <span style="{sans} font-size:12px; color:var(--ink-3);">{rest_label}</span>'
            f'  <div style="flex:1; height:1px; background:var(--border);"></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if rest:
        total_pages = max(1, -(-len(rest) // PAGE_SIZE))

        if "feed_page" not in st.session_state:
            st.session_state.feed_page = 0
        if st.session_state.feed_page >= total_pages:
            st.session_state.feed_page = 0

        page = st.session_state.feed_page
        page_items = rest[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

        rendered_lids = []
        for left, right in zip_longest(page_items[::2], page_items[1::2]):
            c1, c2 = st.columns(2)
            with c1:
                if left:
                    rendered_lids.append(left["id"])
                    render_compact_card(left, conn)
            with c2:
                if right:
                    rendered_lids.append(right["id"])
                    render_compact_card(right, conn)
        _inject_card_js(rendered_lids)

        st.markdown(
            f'<div style="{sans} font-size:11.5px; color:var(--ink-3); text-align:center; margin-top:16px;">'
            f'Page {page + 1} of {total_pages} · {len(rest)} listings'
            f'</div>',
            unsafe_allow_html=True,
        )
        col_prev, col_gap, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.button("← Prev", disabled=page == 0, use_container_width=True):
                st.session_state.feed_page -= 1
                st.rerun()
        with col_next:
            if st.button("Next →", disabled=page >= total_pages - 1, use_container_width=True):
                st.session_state.feed_page += 1
                st.rerun()

    elif not raw_listings:
        st.caption("No listings yet — click Sync now to fetch results.")


# ── favourites ────────────────────────────────────────────────────────────────

def _inject_shortlist_js(lids: list):
    """Wire all shortlist card action buttons in one iframe — same pattern as _inject_card_js."""
    if not lids:
        return
    lids_js = json.dumps(lids)
    components.html(f"""<script>
(function() {{
  var p = window.parent.document;

  function clickHidden(text) {{
    p.querySelectorAll('button').forEach(function(b) {{
      if (b.textContent.trim() === text) b.click();
    }});
  }}

  function hideControlButtons() {{
    p.querySelectorAll('button').forEach(function(b) {{
      var t = b.textContent.trim();
      if (t.startsWith('EDFAV_') || t.startsWith('EDDIS_')) {{
        var el = b;
        for (var i = 0; i < 6; i++) {{
          if (!el.parentElement) break;
          el = el.parentElement;
          var ti = el.getAttribute('data-testid') || '';
          if (ti === 'stBaseButtonContainer' || ti === 'stButton' || ti === 'element-container') {{
            el.style.cssText = 'display:none!important;height:0;overflow:hidden;margin:0;padding:0;';
            break;
          }}
        }}
        b.style.cssText = 'display:none!important;';
      }}
    }});
  }}

  hideControlButtons();
  [100, 300, 700, 1500].forEach(function(t) {{ setTimeout(hideControlButtons, t); }});

  function wireCards() {{
    var wired = 0;
    {lids_js}.forEach(function(lid) {{
      var fav = p.getElementById('edfav-' + lid);
      var dis = p.getElementById('eddis-' + lid);
      if (!fav || !dis || fav._edWired) return;
      fav._edWired = true;
      wired++;
      fav.addEventListener('click', function() {{ clickHidden('EDFAV_' + lid); }});
      dis.addEventListener('click', function() {{ clickHidden('EDDIS_' + lid); }});
    }});
    return wired;
  }}

  var wireAttempts = 0;
  function tryWire() {{
    if (wireCards() > 0 || wireAttempts++ > 25) return;
    setTimeout(tryWire, 80);
  }}
  tryWire();
}})();
</script>""", height=0)


def render_favourites(conn):
    favs_all = get_favourites(conn)
    n = len(favs_all)
    subtitle = f"{n} watch{'es' if n != 1 else ''} saved · your buying shortlist"
    st.markdown(
        f'<div style="margin-bottom:48px;">'
        f'  <h1 style="font-family:\'Newsreader\',serif; font-size:var(--t-hero); font-weight:400; '
        f'letter-spacing:var(--ls-display); margin:0; line-height:var(--lh-tight); color:var(--ink); '
        f'text-wrap:balance; font-optical-sizing:auto;">Shortlist.</h1>'
        f'  <p style="font-family:\'Geist\',sans-serif; font-size:var(--t-ui); '
        f'color:var(--ink-3); margin:14px 0 0; line-height:var(--lh-ui); '
        f'letter-spacing:var(--ls-ui);">{subtitle}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    favs = favs_all
    if not favs:
        st.markdown(
            '<p style="font-family:\'Geist\',sans-serif;font-size:var(--t-ui);color:var(--ink-3);margin-top:-24px;">'
            'Save listings you\'re considering — they\'ll live here as your shortlist.</p>',
            unsafe_allow_html=True,
        )
        return

    lids = []
    for listing in favs:
        render_candidate_card(listing, conn)
        lids.append(listing["id"])

    _inject_shortlist_js(lids)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Timex Watch Finder", page_icon="🕐", layout="wide")
    _inject_styles()

    conn = get_conn(config.DB_PATH)
    init_db(conn)

    if "view" not in st.session_state:
        st.session_state.view = "feed"
    if "new_count" not in st.session_state:
        st.session_state.new_count = get_new_count(conn)
    # Always refresh fav_count from DB so the nav badge stays accurate
    st.session_state["fav_count"] = conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0]

    render_sidebar(conn)

    if st.session_state.view == "favourites":
        render_favourites(conn)
    else:
        render_feed(conn, st.session_state.new_count)

    st.markdown(
        '<style>'
        '#rtt-link{position:fixed;bottom:28px;right:32px;z-index:9999;'
        'font-family:"Geist",sans-serif;font-size:0.6875rem;letter-spacing:0.08em;'
        'text-transform:uppercase;color:#928E89;text-decoration:none;'
        'transition:color 120ms ease;}'
        '#rtt-link:hover{color:#111110;}'
        '</style>'
        '<a id="rtt-link" href="#">Top</a>',
        unsafe_allow_html=True,
    )
    components.html("""<script>
(function(){
  var p = window.parent.document;
  function wire(){
    var a = p.getElementById('rtt-link');
    if(!a){ setTimeout(wire, 100); return; }
    a.addEventListener('click', function(e){
      e.preventDefault();
      var sc = p.querySelector('[data-testid="stMain"]') || p.documentElement;
      sc.scrollTo({top:0, behavior:'smooth'});
    });
  }
  wire();
})();
</script>""", height=1)



if __name__ == "__main__":
    main()
