# Get Paid From: blueprint v1 (draft for discussion, 2026-10-25)

## The job
A freelancer or creator types their country and, within 10 seconds, knows:
1. **Can I get paid from here?**
2. **Which way is best for me?**
3. **What will trip me up?**

Everything else (tax, VAT, registration, sources) is one tap away, never in the way.

## What's wrong with v0 (the live site)
- Shows research notes instead of answers: long hedged paragraphs, "why this rating", quotes.
- Machine wording: fact codes (W1, P2), "TRAP", "Single source", "not captured".
- Leads with legal and tax research; people come for "which platforms work".
- Generic template look.
- Search only on the home page, country names only.

## Country page (mobile first)
```
┌──────────────────────────────────┐
│ 🔍 Ask: "paypal nepal", "tax…"   │  search on every page
├──────────────────────────────────┤
│ Get paid from 🇱🇰 Sri Lanka       │
│ ✅ You can. Easiest: Payoneer     │  verdict (fixed rule)
├──────────────────────────────────┤
│ Get paid by clients               │
│ [PayPal ✅] [Payoneer ✅] [Wise ❌]│  tap a tile = 1-line reason + source
│ Sell products online              │
│ [Stripe ❌] [Gumroad ?] [Lemon ✅]│
│ [Paddle ✅] [Polar ✅] [Payhip ?] │
├──────────────────────────────────┤
│ ⚠ Watch out (max 3, one line each)│
├──────────────────────────────────┤
│ Before you start                  │  tax ID · registration · VAT · income tax
│ one line each, "more" expands     │
└──────────────────────────────────┘
```
- Tile states: ✅ works · ⚠️ limited (receive-only, existing users only, conditions) · ❌ not available · ? not checked yet.
- Every line has a small "source" link and a confidence dot. The full research text sits behind "more".

## Writing rules
- Every answer gets a **short answer: 15 words or fewer**, plain words, no hedging. The long researched text stays behind "more".
- Banned on the page: fact codes, "TRAP", "Single source", "not captured", "search summary", "per X".
- Numbers and deadlines stay exact ("bring USD home within 180 days").
- Short answers are written from the verified long answer and checked against it. No new facts.

## Search ("ask a question", static, no AI)
- One search bar on every page, including the home page hero.
- Understands country names and aliases, platform names, and topics (tax, VAT, register, bank account, ID).
  - "paypal nepal" → Nepal page, PayPal tile open
  - "vat kenya" → Kenya page, VAT line
  - "stripe" → Stripe page listing countries
- Runs in the browser from a small index file: free, instant, cannot invent answers.

## Verdicts (fixed rule, same everywhere): two per country
**Clients pay you** (money accounts)
- "No clean route right now": sanctioned countries (BY CU IR KP RU SY).
- "You can. Easiest: X": the first ✅ in the order **PayPal › Payoneer › Wise** (decided 2026-10-25: clients already know PayPal).
- "Possible, with limits": only ⚠️ routes, or only a bank transfer.

**Selling online** (products and software)
- "You can. Easiest: X": the first ✅ in the order **Gumroad › Lemon Squeezy › Payhip › Polar › Paddle › Stripe**. Proposed: simplest setup for a beginner first; Paddle is software-only and reviewed case by case; Stripe needs your own website. Adjustable.
- "Not yet": nothing is ✅.

## Platform pages (in v1)
`/paypal/`, `/payoneer/`, `/stripe/` …: one line per country (✅ ⚠️ ❌), searchable. They capture searches like "countries where Stripe works".

## "Before you start" section
Four lines visible (tax ID, registration, VAT, income tax), one sentence each. Tap "more" for detail and sources.

## Data changes needed
1. Structured status for PayPal / Payoneer / Wise per country (today it's free text in P4/P5), each with a one-line reason and its source.
2. Gumroad and Payhip: new research from their official country lists.
3. A short answer per fact (about 2,700 lines), written and checked in batches.
4. Platform lists for the grid: Stripe, Lemon Squeezy, Paddle, Polar, Dodo and Whop are already structured.

## Look ("friendly app")
Light background, rounded cards, platform tiles with simple icons, colored ✅ ⚠️ ❌ chips, flag emoji, generous spacing. One accent color. No stock-template feel.

## Build order (proposed)
1. **Data:** structured PayPal / Payoneer / Wise status per country; Gumroad and Payhip research.
2. **Writing:** short answers and "watch out" lines, in batches, checked against the long answers. Start with the 38 largest freelancer markets, then the rest.
3. **Design:** home and country page in the friendly-app style; show the owner 2 country pages before building all of them.
4. **Search** and platform pages.
5. Tests (links, search index, short-answer length and banned words), then deploy.

## Not changing
Free static hosting, no tracking, the evidence rule (every line traceable to a source), legitimate routes only.
