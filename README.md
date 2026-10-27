# Get Paid From

How to get paid from your country: payment platforms, foreign-currency accounts, tax ID, VAT and business registration for all 193 UN member states, with a source and a check date for every answer.

Site: <https://abdullahshakirhussain-lgtm.github.io/getpaidfrom/> (moving to Cloudflare; see Hosting below)

## What is in this repo

| Path | What it is |
|---|---|
| `data/countries/<CC>.json` | The published data: one file per country, with platform availability from official lists and 14 researched answers, each with sources |
| `data/research/<CC>.json` | The research files the country files are built from |
| `data/sources/*.json` | Parsed official platform country lists (Stripe, PayPal, Paddle, Lemon Squeezy, Polar, Dodo, Whop, Upwork, Etsy, YouTube, Google Play) |
| `scripts/` | Collectors, validation and the site generator (`build_site.py`) |
| `data/display/` | Plain-language short answers (max 15 words) and platform statuses shown on the pages |
| `site/templates`, `site/static`, `site/logos` | Page templates, stylesheet, self-hosted fonts and service logos (sources in `site/logos/SOURCES.md`) |
| `tests/` | Plain-script checks: `python tests/<name>.py` |
| `docs/RESEARCH_PROTOCOL.md` | The rules every answer follows |
| `docs/BLUEPRINT.md`, `docs/DESIGN.md` | What each page must answer, and the design rules |

The raw page snapshots that back each quote are kept privately and are not in this repo: they are copies of third-party pages. Each source records the URL, check date and the exact quoted sentence, so anyone can re-check it against the live page.

## Status of an answer

- **verified**: at least one official source, or two independent secondary sources that agree
- **unverified**: one secondary source only
- **conflicting**: sources disagree; both are shown
- **not yet researched**: left blank rather than guessed

## Build the site locally

```bash
pip install Jinja2==3.1.6 MarkupSafe==3.0.4
python scripts/build_site.py
python -m http.server 8765 --directory site/dist
```

Set `SITE_URL` to change the canonical address used in links, the sitemap and robots.txt.

## Hosting

`.github/workflows/pages.yml` builds and tests the site on every push to `main`, then deploys it:

- to **Cloudflare** (Workers static assets, configured in `wrangler.toml`) when the repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` exist;
- otherwise to **GitHub Pages**.

Set the repository variable `SITE_URL` to the public address so canonical links and the sitemap point to it.

## Not advice

General information from public sources, not legal, tax or financial advice. Legitimate routes only: no borrowed identities, foreign addresses, VPN tricks or sanctions evasion.
