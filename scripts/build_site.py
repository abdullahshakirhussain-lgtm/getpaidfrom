"""Build the Get Paid From static site from data/countries/*.json + data/display/ (blueprint: docs/BLUEPRINT.md).

    python scripts/build_site.py                 # countries that have short answers (data/display/short/<CC>.json)
    python scripts/build_site.py --only LK,PK    # just these
    SITE_URL=https://getpaidfrom.com python scripts/build_site.py

Pages: home (search), /<country>/, /<platform>/ (e.g. /paypal/), /about/, 404. Search runs in the browser from
search.json: country, platform and topic words ("paypal nepal", "vat kenya") answered from the data, no AI.
Plain HTML + one CSS file + one small JS file; no framework, tracking or external requests.
"""
import copy
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
from i18n import LANGS, Translator, country_names, load_json
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
CODE_LABEL = {k.split("_")[0]: label.lower() for k, label in BEFORE + MORE} | {"P4": "PayPal", "P5": "Payoneer and Wise", "W1": "legal ways"}
ANCHOR.update({"P4_paypal": "paypal", "P5_payoneer_wise": "payoneer"})  # these facts are shown as platform tiles
TOPICS = {  # search words -> fact anchor
    "tax": "L3_income_tax_foreign", "income": "L3_income_tax_foreign", "vat": "L4_vat_gst", "gst": "L4_vat_gst",
    "register": "L1_registration", "registration": "L1_registration", "business": "L1_registration", "tin": "L2_tax_id",
    "ntn": "L2_tax_id", "id": "D1_id_document", "kyc": "D1_id_document", "dollar": "P2_fcy_account", "usd": "P2_fcy_account",
    "account": "P2_fcy_account", "bank": "P2_fcy_account", "gateway": "P3_local_gateways", "privacy": "L5_data_protection",
    "data": "L5_data_protection", "refund": "L6_consumer_ecommerce", "consumer": "L6_consumer_ecommerce",
    "exchange": "P1_fx_receipts", "repatriate": "P1_fx_receipts", "incentive": "L7_incentives",
}
TOPICS.update({w: "W1_workarounds" for w in ("upwork", "workaround", "workarounds", "alternative", "alternatives", "legal", "ways")})
ANCHOR["W1_workarounds"] = "ways"
BANNED = re.compile(r"\b(TRAP|not captured|search summary|Single source)\b|\b[PLDW]\d\b")
INDEXNOW_KEY = (SRC / "indexnow-key.txt").read_text(encoding="utf-8").strip()  # public by design: served at /<key>.txt

# W1 routes (generated by w1gen from the official platform lists) -> short title and one plain line.
# The full generated sentence stays behind "more". A line of None means: show the first sentence of the route text.
ROUTES = [
    ("Sell digital products or software through a merchant of record", "Sell digital products through a merchant of record",
     "They sell to your customers, handle the tax, and pay you out."),
    ("Sell services on Upwork", "Sell services on Upwork", "Upwork is open to freelancers here; your withdrawal options show in your account."),
    ("Paid apps and in-app sales through Google Play", "Sell apps on Google Play", "Google Play merchant registration is open here."),
    ("Creator income through the YouTube Partner Program", "Earn from YouTube", "The YouTube Partner Program is open here."),
    ("Physical or digital goods on Etsy", "Sell on Etsy", "Etsy pays sellers here."),
    ("Stripe accepts merchants here", "Take card payments with Stripe", "Stripe accepts businesses here, for your own website."),
    ("Stripe lists this country as 'Preview'", "Stripe, by invitation only", "Stripe lists this country as a preview: contact their sales team."),
    ("Card payments on your own site through Paystack", "Take card payments with Paystack", "Paystack, a Stripe company, covers this country."),
    ("For direct clients, a bank transfer", "Ask direct clients for a bank transfer",
     "A SWIFT transfer into your own account always works; keep your invoices."),
    ("Local official channel:", "Use your country's official route", None),
]


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
    text = re.sub(r",? see [PLDW]\d for [^)]*", "", text)  # "(not on PayPal's Payouts list, see P4 for ordinary ...)"
    text = re.sub(r"\s*\((?:see |per )?(?:[PLDW]\d)(?:\s*(?:/|,|and)\s*[PLDW]\d)*\)", "", text)
    text = re.sub(r"\b(see|per) [PLDW]\d\b", "", text)
    # any code left mid-sentence ("the regime in L3") -> the line's plain name on the page
    text = re.sub(r"\b([PLDW]\d)\b", lambda m: f"the {CODE_LABEL.get(m.group(1), 'related')} line", text)
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


def first_sentence(text):
    # the first "." or ";" that ends a sentence, skipping ones inside brackets such as "(BCRA Com. 'A' 8417)"
    head = text
    for m in re.finditer(r"[.;](?=\s|$)", text):
        if text.count("(", 0, m.start()) == text.count(")", 0, m.start()):
            head = text[:m.end()]
            break
    return head.rstrip(";") + ("" if head.endswith(".") else ".")


def ways_view(c, t):
    """The legal routes ('Ways to get paid, legally') from the W1 answer. The PayPal route follows the PayPal tile,
    which rests on newer, country-specific evidence (P4) than the Payouts list W1 was generated from."""
    f = c["facts"].get("W1_workarounds")
    if not f:
        return None
    m = re.match(r"Barriers: (.*?)\. (Simple legal routes:|No clean workaround:)(.*)$", f["answer"], re.S)
    if not m:
        raise SystemExit(f"{c['code']}: W1 answer in an unknown shape")
    plain = {  # w1gen barrier phrases -> plain words (the full text stays in the W1 answer and its sources)
        "Stripe does not accept merchants here": "Stripe (doesn't accept businesses here)",
        "Wise does not let residents hold money": "Wise balances (residents can't hold money)",
        "PayPal is not available": "PayPal (not available)",
        "major freelance and payment platforms exclude residents (sanctions or payment-partner restrictions)":
            "the major freelance and payment platforms (sanctions or partner rules)",
    }
    parts = []
    for part in m.group(1).split("; "):
        if part.startswith("none of"):
            continue
        if part.startswith("platforms that pay out through PayPal Payouts"):
            if t["paypal"]["status"] == "no":
                continue  # PayPal itself is unavailable; already said
            parts.append("payouts from sites that pay through PayPal Payouts (PayPal doesn't list this country)")
        else:
            parts.append(plain.get(part, clean_long(part)))
    # keep this line consistent with the PayPal and Wise tiles (newer, country-specific evidence)
    if t["paypal"]["status"] == "no" and plain["PayPal is not available"] not in parts:
        parts.insert(1 if parts and parts[0].startswith("Stripe") else 0, plain["PayPal is not available"])
    if t["wise"]["status"] == "no" and plain["Wise does not let residents hold money"] not in parts:
        parts.append(plain["Wise does not let residents hold money"])
    blocked = ""
    if parts:
        blocked = "; ".join(parts) + "."
        blocked = blocked[0].upper() + blocked[1:]
    view = {"blocked": blocked, "routes": [], "closing": "", "sources": sources(f)}
    if m.group(2).startswith("No clean"):
        closing = clean_long(m.group(3).strip())
        view["closing"] = closing[:1].upper() + closing[1:]
        return view
    body = re.split(r" Avoid: ", m.group(3))[0]
    for raw in (r.strip() for r in re.split(r" ?\(\d+\) ", body) if r.strip()):
        detail = clean_long(raw)
        if raw.startswith("Client payments by PayPal"):
            pp = t["paypal"]
            if pp["status"] == "works":
                view["routes"].append({"title": "Take client payments by PayPal", "line": pp["reason"], "detail": detail})
            elif pp["status"] == "limited":
                view["routes"].append({"title": "PayPal, with limits", "line": pp["reason"], "detail": ""})
            continue
        for prefix, title, line in ROUTES:
            if raw.startswith(prefix):
                rest = detail[len(prefix):].strip() if prefix.endswith(":") else detail
                view["routes"].append({"title": title, "line": line or first_sentence(rest), "detail": rest if line is None else detail})
                break
        else:
            view["routes"].append({"title": first_sentence(detail).rstrip("."), "line": "", "detail": detail})
    for r in view["routes"]:  # don't repeat the line as the only detail
        if r["detail"].strip() == r["line"].strip():
            r["detail"] = ""
    return view


def upwork_status(c):
    p = c["platforms"].get("upwork.restricted")
    if not p:
        return None
    open_ = p["status"] == "not_excluded"
    return {"open": open_, "label": "Open to freelancers" if open_ else "Not available",
            "tone": "ok" if open_ else "bad",
            "reason": "Not on Upwork's list of restricted countries." if open_ else "On Upwork's list of restricted countries.",
            "source": {"publisher": "Upwork", "title": "Countries where Upwork isn't available", "url": p["source_url"],
                       "official": True, "retrieved": day(p.get("retrieved_at"))}}


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
    ways = ways_view(c, t)
    up = upwork_status(c)
    return {"code": code, "name": name, "official": c["un_name"] if c["un_name"] != name else "", "slug": slugify(name),
            "region": c.get("sub_region") or c.get("region") or "", "ways": ways, "upwork": up,
            "ways_n": len(ways["routes"]) if ways else 0, "ways_upwork": bool(up and up["open"]),
            "clients": verdict(code, t, CLIENT_ORDER, "clients"), "selling": verdict(code, t, SELL_ORDER, "selling"),
            "client_tiles": [t[s] for s in CLIENT_ORDER], "sell_tiles": [t[s] for s in SELL_ORDER], "tiles": t,
            "watch": watch, "before": [line(k, l) for k, l in BEFORE], "more": [line(k, l) for k, l in MORE],
            "checked": max(dates) if dates else "", "search": " ".join([name] + ALIASES.get(code, []) + [c["un_name"]]).lower(),
            "en_name": name}


LABEL_KEY = {"L2_tax_id": "label_tax_id", "L1_registration": "label_registering", "L4_vat_gst": "label_vat",
             "L3_income_tax_foreign": "label_income_tax", "P1_fx_receipts": "label_fx", "P2_fcy_account": "label_fcy",
             "P3_local_gateways": "label_gateways", "L7_incentives": "label_incentives", "L5_data_protection": "label_data",
             "L6_consumer_ecommerce": "label_consumer", "D1_id_document": "label_id"}


def ways_line(v, tr):
    if v["ways_n"]:
        return tr.t("ways_line_n_upwork" if v["ways_upwork"] else "ways_line_n", n=v["ways_n"])
    return tr.t("ways_line_none")


def localize(v, tr, names):
    """A copy of a country view in tr.lang: our own wording translated, research text and sources left in English."""
    x = copy.deepcopy(v)
    if tr.lang == "en":
        for tl in x["tiles"].values():
            tl["label"] = tr.t(f"status_{tl['status']}")
        return x
    x["name"], x["official"] = names[v["code"]], ""
    x["search"] = " ".join([names[v["code"]], v["search"]]).lower()
    for k in ("clients", "selling"):
        x[k]["headline"], x[k]["detail"] = tr.text(v[k]["headline"]), tr.text(v[k]["detail"])
    for tl in x["tiles"].values():
        tl["label"], tl["reason"] = tr.t(f"status_{tl['status']}"), tr.text(tl["reason"])
    x["client_tiles"] = [x["tiles"][s] for s in CLIENT_ORDER]
    x["sell_tiles"] = [x["tiles"][s] for s in SELL_ORDER]
    for w in x["watch"]:
        w["text"] = tr.text(w["text"])
    for ln in x["before"] + x["more"]:
        ln["label"], ln["short"] = tr.t(LABEL_KEY[ln["key"]]), tr.text(ln["short"])
    if x["ways"]:
        x["ways"]["blocked"], x["ways"]["closing"] = tr.text(v["ways"]["blocked"]), tr.text(v["ways"]["closing"])
        for r in x["ways"]["routes"]:
            r["title"], r["line"], r["detail"] = tr.text(r["title"]), tr.text(r["line"]), tr.text(r["detail"])
    if x["upwork"]:
        x["upwork"]["label"] = tr.t("upwork_open") if x["upwork"]["open"] else tr.t("status_no")
        x["upwork"]["reason"] = tr.t("upwork_reason_open" if x["upwork"]["open"] else "upwork_reason_closed")
    return x


def sort_key(name, lang):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    if lang == "ar" and s.startswith("ال"):
        s = s[2:]
    return s


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


def load_views(only=None):
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
    return views


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    views = load_views(only)

    env = Environment(loader=FileSystemLoader(SRC / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "static", OUT / "static")
    ver = hashlib.sha256(b"".join(p.read_bytes() for p in sorted((SRC / "static").rglob("*")) if p.is_file())).hexdigest()[:8]  # cache-busting

    # Languages: English always; others only when every line has a translation (never a half-translated page).
    wanted = sys.argv[sys.argv.index("--langs") + 1].split(",") if "--langs" in sys.argv else list(LANGS)
    translators, skipped = {}, {}
    for lang in wanted:
        if lang != "en" and not (ROOT / "data" / "i18n" / f"ui.{lang}.json").exists():
            skipped[lang] = "no interface file yet"
            continue
        tr = Translator(lang)
        names = country_names(lang) if lang != "en" else None
        for v in views:
            ways_line(localize(v, tr, names), tr)
        for key in tr.en_ui:
            tr.t(key)
        if tr.missing and "--draft" not in sys.argv:  # --draft: local preview only, untranslated lines stay English
            skipped[lang] = f"{len(tr.missing)} untranslated lines"
            continue
        translators[lang] = (tr, names)
    built_langs = list(translators)
    latest = max(v["checked"] for v in views)
    sitemap = []

    for lang, (tr, names) in translators.items():
        prefix = "" if lang == "en" else f"{lang}/"
        out = OUT / prefix if prefix else OUT
        lviews = [localize(v, tr, names) for v in views]
        common = {"site_url": SITE_URL, "built": built, "n_countries": len(lviews), "ver": ver, "t": tr.t, "lang": lang,
                  "dir": LANGS[lang][1], "langs": {k: LANGS[k][0] for k in built_langs}, "prefix": prefix}

        def write(outfile, template, depth, path, **ctx):
            (out / outfile).parent.mkdir(parents=True, exist_ok=True)
            ctx = {"root": "../" * (depth + (1 if prefix else 0)), "base": "../" * depth, "path": path, **ctx}
            (out / outfile).write_text(env.get_template(template).render(**common, **ctx), encoding="utf-8")

        platform_pages = {}
        for slug, (name, group) in PLATFORMS.items():
            rows = sorted(({"country": v["name"], "slug": v["slug"], **v["tiles"][slug]} for v in lviews),
                          key=lambda r: (list(STATUS).index(r["status"]), sort_key(r["country"], lang)))
            platform_pages[slug] = {"name": name, "slug": slug, "group": group, "logo": LOGOS[slug], "rows": rows,
                                    "groups": [(s, (tr.t(f"status_{s}"), STATUS[s][1]), [r for r in rows if r["status"] == s])
                                               for s in STATUS],
                                    "counts": {s: sum(r["status"] == s for r in rows) for s in STATUS}}
        by_letter = defaultdict(list)
        for v in sorted(lviews, key=lambda v: sort_key(v["name"], lang)):
            by_letter[sort_key(v["name"], lang)[:1].upper()].append(v)
        # Upwork: whether freelancers can join, plus the receiving routes (Upwork doesn't publish its withdrawal methods per country)
        up_rows = sorted(({"country": v["name"], "slug": v["slug"], "up": v["upwork"], "routes": v["client_tiles"]} for v in lviews if v["upwork"]),
                         key=lambda r: (not r["up"]["open"], sort_key(r["country"], lang)))
        upwork_page = {"logo": logo("upwork"), "open": [r for r in up_rows if r["up"]["open"]],
                       "closed": [r for r in up_rows if not r["up"]["open"]], "source": up_rows[0]["up"]["source"] if up_rows else None}

        write("index.html", "index.html", 0, "", letters=list(by_letter.items()), platforms=platform_pages, upwork=upwork_page)
        write("about/index.html", "about.html", 1, "about/")
        if lang == "en":  # served for any unknown URL, so its links must be absolute
            write("404.html", "404.html", 0, "404.html")
            page = (OUT / "404.html").read_text(encoding="utf-8")
            (OUT / "404.html").write_text(page.replace('href="static/', f'href="{SITE_URL}/static/')
                                          .replace('src="static/', f'src="{SITE_URL}/static/')
                                          .replace('data-root=""', f'data-root="{SITE_URL}/"')
                                          .replace('href="about/', f'href="{SITE_URL}/about/')
                                          .replace('href="./"', f'href="{SITE_URL}/"'), encoding="utf-8")
        for v in lviews:
            write(f"{v['slug']}/index.html", "country.html", 1, f"{v['slug']}/", c=v)
        for slug, p in platform_pages.items():
            write(f"{slug}/index.html", "platform.html", 1, f"{slug}/", p=p)
        write("upwork/index.html", "upwork.html", 1, "upwork/", u=upwork_page)

        sw = load_json(ROOT / "data" / "i18n" / f"search.{lang}.json") if lang != "en" else {"stop": [], "topics": {}}
        topics = {w: ANCHOR[k] for w, k in TOPICS.items()} | {w: ANCHOR[k] for w, k in sw["topics"].items()}
        search = {"countries": [{"n": v["name"], "s": v["slug"], "k": v["search"],
                                 "t": {k: [x["status"], x["reason"]] for k, x in v["tiles"].items()},
                                 "a": {**{ANCHOR[ln["key"]]: ln["short"] for ln in v["before"] + v["more"] if ln["short"]},
                                       "ways": ways_line(v, tr)}}
                                for v in lviews],
                  "platforms": {k: v[0] for k, v in PLATFORMS.items()},
                  "topics": topics, "stop": sw["stop"],
                  "labels": {ANCHOR[k]: tr.t(LABEL_KEY[k]) for k, _ in BEFORE + MORE} | {"ways": tr.t("s_ways")},
                  "ui": {k: tr.t(k) for k in ("s_where_work", "s_every_country", "s_upwork", "s_upwork_sub", "s_no_match", "s_see_details", "s_in")},
                  "status": {k: [tr.t(f"status_{k}"), v[1]] for k, v in STATUS.items()}}
        (out / "search.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        # sitemap: lastmod is when the page's facts were last checked, not the build date
        sitemap += [(prefix + u, d) for u, d in [("", latest), ("about/", None), ("upwork/", latest)]
                    + [(f"{v['slug']}/", v["checked"]) for v in lviews] + [(f"{s}/", latest) for s in PLATFORMS]]

    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{SITE_URL}/{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>\n"
                                               for u, d in sitemap)
                                     + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(views)} countries x {len(built_langs)} languages ({', '.join(built_langs)}) for {SITE_URL}")
    for lang, why in skipped.items():
        print(f"  skipped {lang}: {why}")


if __name__ == "__main__":
    main()
