# Timex Watch Finder

I built this tool to solve a real problem: finding good vintage Timex listings across multiple marketplaces takes too long, and good ones sell fast. The brief gave me three reference watches to anchor the taste profile — a 1972 Marlin, another Marlin, and a 1960s Electric — so I had something concrete to design around.

## What it does

Fetches listings from eBay, Etsy, and Chrono24 every 30 minutes, cuts the obvious junk (broken watches, over-budget listings), and uses Claude AI to score every remaining listing on how well it matches the collector's taste. The top listings surface in a "Purchase Candidates" section. You can star listings you like, come back later, and compare them side-by-side.

## How I designed it

**The scoring is in two phases because speed matters.** The first pass is just keyword matching — "for parts," "not working," that kind of thing. No AI needed, takes milliseconds, and cuts maybe 30–40% of listings immediately. The AI only sees what passes that filter, which keeps the cost low and the latency reasonable.

**I used Claude Haiku (not Sonnet or Opus) for scoring.** Haiku is fast and cheap — about $0.01–0.05 per 100 listings. For a task that's essentially "does this watch look like those three reference watches," Haiku is the right call. I didn't need reasoning depth, I needed throughput.

**The taste profile is seeded from the three reference watches, not described from scratch.** Instead of asking the user to articulate what they want, I hardcoded descriptions of the three watches from the brief and pass them to Claude as examples of "interesting." Users can add a plain-English description in the sidebar if they want to, but it's additive — the reference watches are always the anchor.

**Shipping math is handled systematically, not by the user.** Canadian sellers get a green badge. US sellers without listed shipping get a $12 CAD estimate. International sellers get a "customs may apply" warning. None of this requires the user to think about it.

**The composite score weights taste heavily (60%) because that's the hardest thing to automate.** Price and freshness are measurable; taste is the actual problem this tool solves. The 30/10 split for value/freshness adds signal without overriding a genuinely good match at a fair price.

## Tradeoffs I made

- **eBay and Etsy use scrapers, not official APIs** — both APIs require approval that takes a few days. I built scrapers so the demo works now with real data. The adapter pattern means swapping to the official APIs later is a one-file change per marketplace.

- **Etsy prices convert from USD at a fixed rate** — the Etsy scraper doesn't always surface prices, and USD is what's available. Good enough for a $50 CAD threshold, but I'd use a live rate API in v2.

- **Chrono24 scraping is best-effort** — Chrono24 doesn't have a public API. The scraper works with their current HTML structure but degrades gracefully to an empty list if the structure changes. eBay is the primary source.

- **No authentication or accounts** — this runs locally, for one user. Adding multi-user support would mean a backend, user sessions, and a much bigger scope. Out of scope for the brief.

## What I'd build next

1. **Thumbs up/down on listings** to let the AI learn from feedback over time — right now the taste profile is static
2. **Price trend for known models** — a Marlin that's usually $45 selling for $20 is a much better find than a Marlin at $45
3. **Desktop notification** when a new purchase candidate appears — the "fear of missing something" problem isn't fully solved if you have to remember to open the app
4. **Depop and WatchPatrol adapters** — same adapter interface, one new file each
5. **Official eBay and Etsy APIs** — swap the scrapers once approved, nothing else changes

## Running it locally

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/timex-finder
cd timex-finder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Anthropic API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-your-key-here

# 4. Run
streamlit run app.py
```

Only one API key needed — eBay and Etsy data comes from scrapers. Get your Anthropic key at console.anthropic.com.
