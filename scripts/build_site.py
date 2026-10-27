"""Build the Get Paid From static site from data/countries/*.json + data/display/ (blueprint: docs/BLUEPRINT.md).

    python scripts/build_site.py                 # countries that have short answers (data/display/short/<CC>.json)
    python scripts/build_site.py --only LK,PK    # just these
    SITE_URL=https://getpaidfrom.com python scripts/build_site.py

Pages: home (search), /<country>/, /<platform>/ (e.g. /paypal/), /about/, 404. Search runs in the browser from
search.json: country, platform and topic words ("paypal nepal", "vat kenya") answered from the data, no AI.
Plain HTML + one CSS file + one small JS file; no framework, tracking or external requests.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site"
OUT = SRC / "dist"
DISPLAY = ROOT / "data" / "display"
SITE_URL = os.environ.get("SITE_URL", "https://abdullahshakirhussain-lgtm.github.io/getpaidfrom").rstrip("/")

SHORT = {"BO": "Bolivia", "BS": "Bahamas", "BN": "Brunei", "CD": "DR Congo", "CG": "Republic of the Congo", "CI": "Côte d'Ivoire",
         "CN": "China", "FM": "Micronesia", "GB": "United Kingdom", "GM": "Gambia", "GW": "Guinea-Bissau", "IR": "Iran",
         "KP": "North Korea", "KR": "South Korea", "LA": "Laos", "MD": "Moldova", "NL": "Netherlands", "NR": "Nauru",
         "RU": "Russia", "SY": "Syria", "TZ": "Tanzania", "US": "United States", "VE": "Venezuela", "VN": "Vietnam",
         "ST": "São Tomé and Príncipe"}
ALIASES = {"TR": ["Turkey"], "CI": ["Ivory Coast"], "CZ": ["Czech Republic"], "MM": ["Burma"], "SZ": ["Swaziland"],
           "TL": ["East Timor"], "CV": ["Cape Verde"], "GB": ["UK", "Britain", "England"], "US": ["USA", "America"],
           "AE": ["UAE", "Dubai"], "MK": ["Macedonia"], "CD": ["Congo-Kinshasa"], "CG": ["Congo-Brazzaville"], "NL": ["Holland"]}
SANCTIONED = {"BY", "CU", "IR", "KP", "RU", "SY"}

STATUS = {  # status -> (label, tone); the page draws a shape per tone next to the label (docs/DESIGN.md)
    "works": ("Works", "ok"), "likely": ("Likely", "likely"), "limited": ("Limited", "warn"),
    "unconfirmed": ("Not confirmed", "muted"), "no": ("Not available", "bad"),
}
# platform slug -> display name, group; logos in site/logos/<slug>.svg (sources: site/logos/SOURCES.md)
PLATFORMS = {
    "paypal": ("PayPal", "clients"), "payoneer": ("Payoneer", "clients"), "wise": ("Wise", "clients"),
    "gumroad": ("Gumroad", "selling"), "lemon-squeezy": ("Lemon Squeezy", "selling"), "payhip": ("Payhip", "selling"),
    "polar": ("Polar", "selling"), "paddle": ("Paddle", "selling"), "stripe": ("Stripe", "selling"),
}
CLIENT_ORDER = ["paypal", "payoneer", "wise"]                                            # owner decision 2026-10-25
SELL_ORDER = ["gumroad", "lemon-squeezy", "payhip", "polar", "paddle", "stripe"]
PLATFORM_LIST = {  # sell platforms read from the official-list collectors: key -> {status code: (status, reason)}
    "lemon-squeezy": ("lemon.bank_payouts", {"payout_supported_bank": ("works", "Bank payouts supported."),
                                             "payout_supported_bank_restricted": ("limited", "Bank payouts with restrictions."),
                                             "not_listed": ("no", "No bank payouts to this country.")}),
    "polar": ("polar.payouts", {"payout_supported": ("works", "Payouts supported (through Stripe Connect)."),
                                "not_listed": ("no", "Payouts not available here.")}),
    "paddle": ("paddle.unsupported", {"not_excluded": ("limited", "Software and digital products only; each seller is reviewed."),
                                      "seller_unsupported": ("no", "Sellers here are not supported.")}),
    "stripe": ("stripe.available", {"merchant_signup_available": ("works", "Accepts businesses here; needs your own website."),
                                    "extended_network_via_paystack": ("works", "Available through Paystack, a Stripe company."),
                                    "preview_contact_sales": ("limited", "Preview only: you must contact Stripe sales."),
                                    "not_listed": ("no", "Stripe doesn't accept businesses here.")}),
}
BEFORE = [("L2_tax_id", "Tax ID"), ("L1_registration", "Registering"), ("L4_vat_gst", "VAT / GST"), ("L3_income_tax_foreign", "Income tax")]
MORE = [("P1_fx_receipts", "Receiving foreign money"), ("P2_fcy_account", "Dollar / foreign-currency account"),
        ("P3_local_gateways", "Local payment gateways"), ("L7_incentives", "Tax breaks and simple regimes"),
        ("L5_data_protection", "Data protection"), ("L6_consumer_ecommerce", "Selling to consumers online"), ("D1_id_document", "ID for sign-ups")]
ANCHOR = {k: k.split("_", 1)[1].replace("_", "-") for k, _ in BEFORE + MORE}
ANCHOR.update({"P4_paypal": "paypal", "P5_payoneer_wise": "payoneer"})  # these facts are shown as platform tiles
TOPICS = {  # search words -> fact anchor
    "tax": "L3_income_tax_foreign", "income": "L3_income_tax_foreign", "vat": "L4_vat_gst", "gst": "L4_vat_gst",
    "register": "L1_registration", "registration": "L1_registration", "business": "L1_registration", "tin": "L2_tax_id",
    "ntn": "L2_tax_id", "id": "D1_id_document", "kyc": "D1_id_document", "dollar": "P2_fcy_account", "usd": "P2_fcy_account",
    "account": "P2_fcy_account", "bank": "P2_fcy_account", "gateway": "P3_local_gateways", "privacy": "L5_data_protection",
    "data": "L5_data_protection", "refund": "L6_consumer_ecommerce", "consumer": "L6_consumer_ecommerce",
    "exchange": "P1_fx_receipts", "repatriate": "P1_fx_receipts", "incentive": "L7_incentives",
}
BANNED = re.compile(r"\b(TRAP|not captured|search summary|Single source)\b|\b[PLDW]\d\b")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


BRAND = json.loads((SRC / "logos" / "colors.json").read_text(encoding="utf-8"))  # official hex per Simple Icons; Polar has none (ink)


def contrast_on_white(hexcode):
    """WCAG contrast ratio of a colour against white."""
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(hexcode[i:i + 2], 16)) for i in (0, 2, 4))
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)


def logo(slug):
    """The company's mark as inline SVG in its brand colour. Colours too pale to see on white (under 3:1)
    keep their exact hex but sit on a small ink square, so the mark is never recoloured."""
    svg = (SRC / "logos" / f"{slug}.svg").read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]+)"', svg).group(1)
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    inner = re.sub(r'\sfill="[^"]*"', "", re.sub(r"<title>.*?</title>", "", inner))
    colour = BRAND.get(slug)
    cls = "logo on-ink" if colour and contrast_on_white(colour) < 3 else "logo"
    style = f' style="color:#{colour}"' if colour else ""
    return Markup(f'<svg class="{cls}"{style} viewBox="{box}" fill="currentColor" aria-hidden="true" focusable="false">{inner}</svg>')


LOGOS = {slug: logo(slug) for slug in PLATFORMS}


def day(ts):
    return (ts or "")[:10]


def clean_long(text):
    """Research text for the 'more' panels: drop internal fact codes and labels."""
    text = re.sub(r"\s*\((?:see |per )?(?:[PLDW]\d)(?:\s*(?:/|,|and)\s*[PLDW]\d)*\)", "", text)
    text = re.sub(r"\b(see|per) [PLDW]\d\b", "", text)
    return re.sub(r"\bTRAP( for [a-z ]+)?:\s*", "Watch out: ", text).strip()


def sources(f):
    """One entry per URL: a page quoted several times (one source per quote) is listed once, with its latest date."""
    seen = {}
    for s in f.get("sources", []):
        prev = seen.get(s["url"])
        if prev is None or day(s.get("retrieved")) > prev["retrieved"]:
            seen[s["url"]] = {"publisher": s.get("publisher") or "", "title": s.get("title") or "", "url": s["url"],
                              "official": s.get("evidence") == "official", "retrieved": day(s.get("retrieved"))}
    return list(seen.values())


def tile(slug, status, reason, src, fact=None):
    name, group = PLATFORMS[slug]
    label, tone = STATUS[status]
    return {"slug": slug, "name": name, "group": group, "logo": LOGOS[slug], "status": status, "label": label, "tone": tone,
            "reason": reason, "sources": src, "fact": fact}


def tiles_for(c, acc):
    out = {}
    for slug in ("paypal", "payoneer", "wise", "gumroad", "payhip"):
        a = acc[slug.replace("-", "")]
        src = sources(c["facts"][a["fact"]]) if a.get("fact") else []
        if a.get("source"):
            s = a["source"]
            src = src + [{"publisher": s["publisher"], "title": s["title"], "url": s["url"], "official": True, "retrieved": s["retrieved"]}]
        out[slug] = tile(slug, a["status"], a["reason"], src, a.get("fact"))
    for slug, (key, mapping) in PLATFORM_LIST.items():
        p = c["platforms"].get(key)
        st, reason = mapping.get(p["status"], ("unconfirmed", "Not confirmed.")) if p else ("unconfirmed", "Not confirmed.")
        src = [{"publisher": PLATFORMS[slug][0], "title": "Official country list", "url": p["source_url"], "official": True,
                "retrieved": day(p.get("retrieved_at"))}] if p else []
        out[slug] = tile(slug, st, reason, src)
    return out


def verdict(code, tiles, order, kind):
    """One plain sentence per question, picked by the fixed order (owner decision 2026-10-25)."""
    if code in SANCTIONED:
        return {"tone": "bad", "headline": "Not through the big platforms.", "detail": "Sanctions stop them serving residents."}
    for want, tone, head in (("works", "ok", "Yes, through {}."), ("likely", "likely", "Probably, through {}."),
                             ("limited", "warn", "Yes, with limits, through {}.")):
        hit = next((tiles[s] for s in order if tiles[s]["status"] == want), None)
        if hit:
            return {"tone": tone, "headline": head.format(hit["name"]), "detail": hit["reason"], "slug": hit["slug"]}
    if kind == "clients":
        return {"tone": "warn", "headline": "No platform confirmed.", "detail": "Ask clients to pay by international bank transfer (SWIFT)."}
    return {"tone": "bad", "headline": "No platform confirmed.", "detail": "None of these confirm payouts here yet."}


def country_view(c, acc, short):
    code = c["code"]
    name = SHORT.get(code, c["un_name"])
    t = tiles_for(c, acc)
    F = c["facts"]

    def line(key, label):
        f = F[key]
        return {"key": key, "anchor": ANCHOR[key], "label": label, "short": short["facts"].get(key, ""),
                "long": clean_long(f["answer"]), "notes": clean_long(f.get("notes") or ""), "status": f["status"], "sources": sources(f)}

    watch = [{"text": w["text"], "anchor": ANCHOR[w["fact"]]} for w in short.get("watch_out", [])]
    dates = [s["retrieved"] for f in F.values() for s in sources(f) if s["retrieved"]]
    return {"code": code, "name": name, "official": c["un_name"] if c["un_name"] != name else "", "slug": slugify(name),
            "region": c.get("sub_region") or c.get("region") or "",
            "clients": verdict(code, t, CLIENT_ORDER, "clients"), "selling": verdict(code, t, SELL_ORDER, "selling"),
            "client_tiles": [t[s] for s in CLIENT_ORDER], "sell_tiles": [t[s] for s in SELL_ORDER], "tiles": t,
            "watch": watch, "before": [line(k, l) for k, l in BEFORE], "more": [line(k, l) for k, l in MORE],
            "checked": max(dates) if dates else "", "search": " ".join([name] + ALIASES.get(code, []) + [c["un_name"]]).lower()}


def check_short(code, short):
    problems = []
    texts = list(short["facts"].values()) + [w["text"] for w in short.get("watch_out", [])]
    for t in texts:
        if len(t.split()) > 15:
            problems.append(f"{code}: over 15 words: {t}")
        if BANNED.search(t):
            problems.append(f"{code}: banned wording: {t}")
    if len(short.get("watch_out", [])) > 3:
        problems.append(f"{code}: more than 3 watch-outs")
    return problems


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    acc_all = load(DISPLAY / "accounts.json")
    shorts = {p.stem: load(p) for p in (DISPLAY / "short").glob("*.json")}
    codes = sorted(only or shorts)
    problems = [p for cc in codes for p in check_short(cc, shorts.get(cc, {"facts": {}}))]
    missing = [cc for cc in codes if cc not in shorts]
    if problems or missing:
        sys.exit("\n".join(problems + [f"{cc}: no short answers yet" for cc in missing]))
    all_countries = {p.stem: load(p) for p in sorted((ROOT / "data" / "countries").glob("*.json"))}
    views = [country_view(all_countries[cc], acc_all[cc], shorts[cc]) for cc in codes]
    assert len({v["slug"] for v in views}) == len(views)

    env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "static", OUT / "static")
    ver = hashlib.sha256(b"".join(p.read_bytes() for p in sorted((SRC / "static").rglob("*")) if p.is_file())).hexdigest()[:8]  # cache-busting
    common = {"site_url": SITE_URL, "built": built, "n_countries": len(views), "statuses": STATUS, "ver": ver}

    def write(outfile, template, **ctx):
        (OUT / outfile).parent.mkdir(parents=True, exist_ok=True)
        (OUT / outfile).write_text(env.get_template(template).render(**common, **ctx), encoding="utf-8")

    # platform pages: every built country's tile for that platform
    platform_pages = {}
    for slug, (name, group) in PLATFORMS.items():
        rows = sorted(({"country": v["name"], "slug": v["slug"], **v["tiles"][slug]} for v in views),
                      key=lambda r: (list(STATUS).index(r["status"]), r["country"]))
        platform_pages[slug] = {"name": name, "slug": slug, "group": group, "logo": LOGOS[slug], "rows": rows,
                                "groups": [(s, STATUS[s], [r for r in rows if r["status"] == s]) for s in STATUS],
                                "counts": {s: sum(r["status"] == s for r in rows) for s in STATUS}}
    by_letter = defaultdict(list)
    for v in sorted(views, key=lambda v: slugify(v["name"])):
        by_letter[slugify(v["name"])[0].upper()].append(v)
    write("index.html", "index.html", letters=sorted(by_letter.items()), platforms=platform_pages, root="", path="")
    write("about/index.html", "about.html", root="../", path="about/")
    write("404.html", "404.html", root=f"{SITE_URL}/", path="404.html")
    for v in views:
        write(f"{v['slug']}/index.html", "country.html", c=v, root="../", path=f"{v['slug']}/")
    for slug, p in platform_pages.items():
        write(f"{slug}/index.html", "platform.html", p=p, root="../", path=f"{slug}/")

    search = {"countries": [{"n": v["name"], "s": v["slug"], "k": v["search"],
                             "t": {k: [x["status"], x["reason"]] for k, x in v["tiles"].items()},
                             "a": {ANCHOR[l["key"]]: l["short"] for l in v["before"] + v["more"] if l["short"]}} for v in views],
              "platforms": {k: v[0] for k, v in PLATFORMS.items()},
              "topics": {w: ANCHOR[k] for w, k in TOPICS.items()},
              "status": {k: [v[0], v[1]] for k, v in STATUS.items()}}
    (OUT / "search.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    urls = ["", "about/"] + [f"{v['slug']}/" for v in views] + [f"{s}/" for s in PLATFORMS]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{SITE_URL}/{u}</loc><lastmod>{built}</lastmod></url>\n" for u in urls)
                                     + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(views)} country pages, {len(platform_pages)} platform pages, home, about, 404 for {SITE_URL}")


if __name__ == "__main__":
    main()
