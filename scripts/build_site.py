"""Build the Get Paid From static site (home + one page per country + method page) from data/countries/*.json.

    python scripts/build_site.py                          # writes site/dist/ for the default SITE_URL
    SITE_URL=https://getpaidfrom.com python scripts/build_site.py

Country pages live at /<slug>/ (e.g. /sri-lanka/), so the address reads as the search: "get paid from sri lanka".
No framework, no tracking, no external requests: plain HTML + one CSS file + a few lines of optional JS for search.
Pages with fewer than MIN_SOURCED facts that have a sourced answer get noindex (docs/PLAN.md stage 6).
"""
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site"
OUT = SRC / "dist"
MIN_SOURCED = 8
SITE_URL = os.environ.get("SITE_URL", "https://abdullahshakirhussain-lgtm.github.io/getpaidfrom").rstrip("/")

# Everyday names for UN formal names (the formal name is still shown on the page).
SHORT = {"BO": "Bolivia", "BS": "Bahamas", "BN": "Brunei", "CD": "DR Congo", "CG": "Republic of the Congo", "CI": "Côte d'Ivoire",
         "CN": "China", "FM": "Micronesia", "GB": "United Kingdom", "GM": "Gambia", "GW": "Guinea-Bissau", "IR": "Iran",
         "KP": "North Korea", "KR": "South Korea", "LA": "Laos", "MD": "Moldova", "NL": "Netherlands", "NR": "Nauru",
         "RU": "Russia", "SY": "Syria", "TZ": "Tanzania", "US": "United States", "VE": "Venezuela", "VN": "Vietnam",
         "ST": "São Tomé and Príncipe"}
# Other names people search for.
ALIASES = {"TR": ["Turkey"], "CI": ["Ivory Coast"], "CZ": ["Czech Republic"], "MM": ["Burma"], "SZ": ["Swaziland"],
           "TL": ["East Timor"], "CV": ["Cape Verde"], "GB": ["UK", "Britain", "England"], "US": ["USA", "America"],
           "AE": ["UAE", "Dubai"], "MK": ["Macedonia"], "CD": ["Congo-Kinshasa"], "CG": ["Congo-Brazzaville"], "NL": ["Holland"]}

FACTS = {
    "W1_workarounds": "Simple legal routes for beginners",
    "P1_fx_receipts": "Receiving foreign payments",
    "P2_fcy_account": "Foreign-currency bank account",
    "P3_local_gateways": "Local payment gateways",
    "P4_paypal": "PayPal",
    "P5_payoneer_wise": "Payoneer and Wise",
    "L1_registration": "Registering as a business",
    "L2_tax_id": "Tax ID",
    "L3_income_tax_foreign": "Income tax on foreign income",
    "L4_vat_gst": "VAT / GST",
    "L7_incentives": "Incentives and simplified regimes",
    "L5_data_protection": "Data protection",
    "L6_consumer_ecommerce": "Consumer and e-commerce rules",
    "D1_id_document": "ID for verification",
}
SECTIONS = [
    ("start", "Start here", ["W1_workarounds"]),
    ("paid", "Getting paid", ["P1_fx_receipts", "P2_fcy_account", "P3_local_gateways", "P4_paypal", "P5_payoneer_wise"]),
    ("tax", "Registering and tax", ["L1_registration", "L2_tax_id", "L3_income_tax_foreign", "L4_vat_gst", "L7_incentives"]),
    ("rules", "Rules for selling online", ["L5_data_protection", "L6_consumer_ecommerce"]),
    ("id", "Identity checks", ["D1_id_document"]),
]
STATUS = {  # fact status -> (badge text, css class)
    "verified": ("Verified", "ok"),
    "unverified": ("Single source", "warn"),
    "conflicting": ("Sources disagree", "bad"),
    "not_applicable": ("Not applicable", "muted"),
    "gap": ("Not yet researched", "muted"),
}
# platform list key -> (group, platform name, {status: (plain label, tone)}); tones: ok / bad / warn / muted
PLATFORMS = {
    "stripe.available": ("Take card payments", "Stripe", {
        "merchant_signup_available": ("Accepts merchants", "ok"), "extended_network_via_paystack": ("Through Paystack (Stripe's extended network)", "ok"),
        "preview_contact_sales": ("Preview: contact Stripe sales", "warn"), "not_listed": ("Does not accept merchants here", "bad")}),
    "paypal_worldwide.markets": ("PayPal", "PayPal (market)", {
        "paypal_market_listed": ("PayPal operates here", "ok"), "not_listed": ("No PayPal market", "bad")}),
    "paypal_payouts.eligible": ("PayPal", "PayPal Payouts (platform payouts)", {
        "paypal_payouts_send_receive": ("Can receive Payouts", "ok"), "paypal_payouts_fully_localized": ("Can receive Payouts (fully localized)", "ok"),
        "paypal_payouts_send_receive_local": ("Can receive Payouts (local currency)", "ok"), "paypal_payouts_receive_only": ("Receive only", "ok"),
        "not_listed": ("Not on the Payouts list", "bad")}),
    "paddle.unsupported": ("Sell software and digital products", "Paddle", {
        "not_excluded": ("Not excluded (software sellers, reviewed case by case)", "ok"), "seller_unsupported": ("Sellers not supported", "bad")}),
    "lemon.bank_payouts": ("Sell software and digital products", "Lemon Squeezy payouts", {
        "payout_supported_bank": ("Bank payouts supported", "ok"), "payout_supported_bank_restricted": ("Bank payouts (restricted)", "warn"),
        "not_listed": ("No bank payouts listed", "bad")}),
    "polar.payouts": ("Sell software and digital products", "Polar", {
        "payout_supported": ("Payouts supported", "ok"), "not_listed": ("Payouts not listed", "bad")}),
    "dodo.accepted": ("Sell software and digital products", "Dodo Payments", {
        "seller_accepted": ("Accepts sellers", "ok"), "not_listed": ("Not on the accepted list", "bad")}),
    "dodo.grandfathered": ("Sell software and digital products", "Dodo Payments (existing sellers)", {
        "grandfathered_only": ("Existing sellers only, no new sign-ups", "warn")}),
    "whop.payouts": ("Sell software and digital products", "Whop", {
        "payout_supported": ("Payouts supported", "ok"), "not_listed": ("Payouts not listed", "bad"), "unverified": ("Unclear", "warn")}),
    "lemon.purchases_blocked": ("Sell software and digital products", "Lemon Squeezy (buyers here)", {
        "buyers_blocked": ("Buyers in this country are blocked", "bad")}),
    "upwork.restricted": ("Marketplaces and creator income", "Upwork", {
        "not_excluded": ("Open to freelancers", "ok"), "freelancer_restricted": ("Freelancers restricted", "bad")}),
    "etsy.eligible": ("Marketplaces and creator income", "Etsy", {
        "seller_payments_eligible": ("Etsy Payments available", "ok"), "seller_payments_eligible_via_payoneer": ("Etsy Payments through a Payoneer account", "ok"),
        "not_listed": ("Not on the Etsy Payments list", "bad")}),
    "youtube_ypp.signup_areas": ("Marketplaces and creator income", "YouTube Partner Program", {
        "ypp_signup_available": ("Available", "ok"), "not_listed": ("Not available", "bad")}),
    "gplay.merchant_registration": ("Marketplaces and creator income", "Google Play (paid apps)", {
        "merchant_registration": ("Merchant registration available", "ok"), "not_listed": ("Free apps only", "bad")}),
}
GROUP_ORDER = ["Take card payments", "PayPal", "Sell software and digital products", "Marketplaces and creator income"]
REF = re.compile(r"\b(P[1-5]|L[1-7]|D1|W1)\b")
CODE = {k.split("_")[0]: k for k in FACTS}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def day(ts):
    return (ts or "")[:10]


def rich(text):
    """Escape, then emphasise TRAP warnings and turn fact codes (e.g. 'see L3') into in-page links."""
    s = str(escape(text))
    s = re.sub(r"\bTRAP\b( for [a-z ]+)?:?", lambda m: f"<strong class=trap>{m.group(0)}</strong>", s)
    s = REF.sub(lambda m: f'<a href="#{m.group(1)}" title="{FACTS[CODE[m.group(1)]]}">{m.group(1)}</a>', s)
    return Markup(s)


def routes_view(answer):
    """Split the generated W1 text ('Barriers: a; b. Simple legal routes: (1) .. (2) .. Avoid: ..') into lists.
    Returns None when the text does not have that shape, and the page then shows it as plain text."""
    m = re.match(r"Barriers: (.*?)\. (?:Simple legal routes: (.*?) )?(Avoid: .*|No clean workaround: .*)$", answer, re.S)
    if not m:
        return None
    barriers = [b.strip() for b in m.group(1).split("; ") if b.strip()]
    routes = [r.strip() for r in re.split(r"\(\d+\) ", m.group(2) or "") if r.strip()]
    return {"barriers": barriers, "routes": routes, "closing": m.group(3)}


def fact_view(key, f):
    gap = f["answer"].startswith("Not established") or not f["answer"].strip()
    badge, tone = STATUS["gap" if gap else f["status"]]
    sources = [{"publisher": s.get("publisher") or "", "title": s.get("title") or s.get("url"), "url": s["url"],
                "official": s.get("evidence") == "official", "retrieved": day(s.get("retrieved")),
                "quote": s.get("quote") or "", "summary": s.get("quote_type") == "description"} for s in f.get("sources", [])]
    return {"code": key.split("_")[0], "key": key, "title": FACTS[key], "question": f["question"], "answer": f["answer"],
            "gap": gap, "badge": badge, "tone": tone, "notes": f.get("notes") or "", "note": f.get("note") or "", "sources": sources,
            "routes": routes_view(f["answer"]) if key == "W1_workarounds" else None}


def platform_view(platforms):
    groups = defaultdict(list)
    for key, (group, name, labels) in PLATFORMS.items():
        p = platforms.get(key)
        if not p or p["status"] not in labels:
            continue  # e.g. 'not_listed' on a list that only flags exceptions
        label, tone = labels[p["status"]]
        groups[group].append({"name": name, "label": label, "tone": tone, "caveat": p.get("caveat") or "",
                              "url": p["source_url"], "retrieved": day(p.get("retrieved_at")), "official": p.get("evidence") == "official"})
    return [(g, groups[g]) for g in GROUP_ORDER if groups[g]]


def country_view(c):
    facts = {k: fact_view(k, c["facts"][k]) for k in FACTS if k in c["facts"]}
    sourced = [f for f in facts.values() if f["sources"] and not f["gap"]]
    dates = [s["retrieved"] for f in facts.values() for s in f["sources"] if s["retrieved"]]
    name = SHORT.get(c["code"], c["un_name"])
    return {"code": c["code"], "name": name, "official": c["un_name"] if c["un_name"] != name else "", "slug": slugify(name),
            "search": " ".join([name] + ALIASES.get(c["code"], []) + ([c["un_name"]] if c["un_name"] != name else [])).lower(),
            "region": c.get("sub_region") or c.get("region") or "",
            "sections": [(sid, title, [facts[k] for k in keys if k in facts]) for sid, title, keys in SECTIONS],
            "platforms": platform_view(c["platforms"]),
            "n_verified": sum(f["tone"] == "ok" for f in facts.values()), "n_facts": len(facts),
            "n_gaps": sum(f["gap"] for f in facts.values()), "noindex": len(sourced) < MIN_SOURCED,
            "checked": max(dates) if dates else "", "first": min(dates) if dates else ""}


def main():
    env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["rich"] = rich
    countries = [country_view(load(p)) for p in sorted((ROOT / "data" / "countries").glob("*.json"))]
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slugs = [c["slug"] for c in countries]
    assert len(set(slugs)) == len(slugs), "duplicate country slugs"
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "static", OUT / "static")
    by_region = defaultdict(list)
    for c in countries:
        by_region[c["region"]].append(c)
    stats = {"countries": len(countries), "verified": sum(c["n_verified"] for c in countries),
             "facts": sum(c["n_facts"] for c in countries), "built": built,
             "sources": sum(len(f["sources"]) for c in countries for _, _, fs in c["sections"] for f in fs)}
    common = {"stats": stats, "site_url": SITE_URL}

    def write(outfile, template, **ctx):
        (OUT / outfile).parent.mkdir(parents=True, exist_ok=True)
        (OUT / outfile).write_text(env.get_template(template).render(**common, **ctx), encoding="utf-8")

    write("index.html", "index.html", regions=sorted(by_region.items()), root="", path="")
    write("about/index.html", "about.html", root="../", path="about/")
    write("404.html", "404.html", root=f"{SITE_URL}/", path="404.html")
    for c in countries:
        write(f"{c['slug']}/index.html", "country.html", c=c, root="../", path=f"{c['slug']}/")
    urls = [""] + ["about/"] + [f"{c['slug']}/" for c in countries if not c["noindex"]]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{SITE_URL}/{u}</loc><lastmod>{built}</lastmod></url>\n" for u in urls)
                                     + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(countries)} country pages + index + about + 404 + sitemap into {OUT.relative_to(ROOT)} "
          f"for {SITE_URL} ({sum(c['noindex'] for c in countries)} noindex)")


if __name__ == "__main__":
    main()
