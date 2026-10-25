# Country research protocol (same for all 193 UN member states)

**Rule:** no fact from memory or a library. Every answer has sources with URL, publisher, retrieval date, evidence type and an
**exact quote** taken from the fetched page (`scripts/snap.py` saves the raw page and prints matching sentences). Paraphrase goes
in `answer`; proof goes in `quote`.

## Status rules (enforced by `scripts/country_build.py validate`)
- `verified`: ≥ 1 **official** source (government, central bank, tax authority, regulator, the platform itself) **or** ≥ 2 independent secondary sources that agree. Independent = different websites (the validator counts distinct domains; two quotes from one site are one source). Outlets that all relay one press release are noted as such.
- `conflicting`: ≥ 2 sources that disagree. All are shown; nothing is averaged.
- `unverified`: searched, not confirmed. The note says what was tried. Never filled with a guess.
- `not_applicable`: the question doesn't arise (e.g. no VAT system), with a source saying so.

## Checklist per country
**Payments (local side)**
- `P1_fx_receipts`: Can resident individuals receive foreign currency for services or digital exports? Any conversion or repatriation rule? (central bank / FX law)
- `P2_fcy_account`: Can individuals hold a foreign-currency bank account? (central bank or a licensed bank's official page)
- `P3_local_gateways`: Licensed local online payment gateways, and whether individuals or sole proprietors can sign up (regulator list + gateway's own page)
- `P4_paypal`: PayPal capability in the country (PayPal's own country/fee pages; automated Payouts table)
- `P5_payoneer_wise`: Payoneer / Wise availability for residents (their official pages)

**Legal**
- `L1_registration`: Must an individual selling digital products or services register a business? How (sole proprietor), cost, online? (official registry/portal)
- `L2_tax_id`: Tax identification number requirement and how to get it (tax authority)
- `L3_income_tax_foreign`: How residents' foreign-sourced or digital income is taxed (tax authority; global tax summaries as secondary)
- `L4_vat_gst`: VAT/GST rate, registration threshold, treatment of exported services and digital services (tax authority)
- `L5_data_protection`: Data-protection law: name, year, in force?, regulator (official gazette/regulator)
- `L6_consumer_ecommerce`: E-commerce / consumer-protection law relevant to online sales (official)
- `L7_incentives`: Government incentives or schemes for IT/digital exporters or freelancers (official)

**Documents**
- `D1_id_document`: Name of the national identity document residents use for identity checks (government issuer)

**Automated (filled from collectors, re-checked on every run):** Stripe, PayPal Payouts, PayPal market, Polar, Dodo, Whop,
Lemon Squeezy (bank), Etsy Payments, Paddle (exclusion list), Google Play merchant, YouTube Partner Program, UN membership + M49 data.

## Process per country
1. Search for the **official** source first (government domain, central bank, tax authority).
2. `snap.py <url> "keyword1|keyword2"`: save the page, print exact matching sentences.
3. Record the fact with its quote. Look for a second source; if it disagrees, the fact becomes `conflicting`.
4. `country_build.py validate <CODE>` **and** `check_quotes.py <CODE>` must both pass before the country counts as done.
   `check_quotes.py` proves each quote is really in its saved snapshot (ignoring case/spacing/punctuation). Quote conventions:
   `...` skips text; `{curly braces}` mark our own editorial words (not checked); `"quote_type": "description"` for absence
   findings from complete lists; `"quote_type": "rendered_reading"` when a table had to be read from the rendered page image.
   A source read only in a normal browser visit (site blocks scripts) has `snapshot: null`, and the fact's notes say so.
   `grep_snap.py <snapshot> "<regex>"` reads a whole provision from an already-saved snapshot.
5. Update the owner with a short country summary.
