"""Collect official country lists, snapshot the raw page, and write normalized source files.

    python scripts/collect.py                 # all sources
    python scripts/collect.py stripe polar    # some

Output per source: data/sources/<id>.json  (+ gzipped raw snapshot in data/snapshots/<id>/<date>-<sha12>.html.gz)
A source FAILS (non-zero exit, nothing written) if: fetch fails, any country name doesn't normalize,
or a list has fewer items than its `min_items` guard (protects against layout changes producing partial data).
"""
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from countries import UnknownCountry, normalize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
HEADING = re.compile(r"^h[1-4]$")


def fetch(url):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - report any network failure after retries
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


def soup_of(raw):
    s = BeautifulSoup(raw.decode("utf-8", errors="replace"), "html.parser")
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    return s


def section_items(soup, heading_re, item_tag="li", stop_level=None):
    """Items of `item_tag` between the heading matching heading_re and the next heading of the same/higher level."""
    h = next((x for x in soup.find_all(HEADING) if re.search(heading_re, x.get_text(" ", strip=True), re.I)), None)
    if h is None:
        raise RuntimeError(f"heading /{heading_re}/ not found (page layout changed?)")
    level = int(h.name[1]) if stop_level is None else stop_level
    out = []
    for el in h.find_all_next():
        if el.name and HEADING.match(el.name) and int(el.name[1]) <= level:
            break
        if el.name == item_tag:
            out.append(el.get_text(" ", strip=True))
    return out


# ---- one parser per source: returns {list_name: [(raw_text, label_or_None), ...]} -------------------------------

def parse_stripe(s):
    out = []
    for li in s.select("ul.GlobalCountryList li.GlobalCountryListItem"):
        parts = [p for p in li.get_text("|", strip=True).split("|") if p]
        out.append((parts[0], parts[1] if len(parts) > 1 else None))
    return {"available": out}


def parse_polar(s):
    return {"payouts": [(t, None) for t in section_items(s, r"^\W*Payouts$")]}


def parse_dodo(s):
    accepted = []
    h = next(x for x in s.find_all(HEADING) if "Accepted Countries" in x.get_text())
    ol = h.find_next("ol")
    accepted = [(li.get_text(" ", strip=True), None) for li in ol.find_all("li", recursive=False)]
    grand = []
    for c in s.select("div.callout"):
        txt = c.get_text(" ", strip=True)
        m = re.search(r"grandfathered under this provision[^:]*:\s*(.+?)(?:\.\s|$)", txt, re.I)
        if m:
            grand = [(x.strip(), None) for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)) if x.strip()]
    if not grand:
        # fall back to the paragraph that names the grandfathered countries (it may not be inside a callout)
        txt = s.get_text(" ", strip=True)
        m = re.search(r"Countries currently grandfathered under this provision\s*:?\s*(.+?)(?:\.\s|$)", txt, re.I)
        if m:
            grand = [(x.strip(), None) for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)) if x.strip()]
    return {"accepted": accepted, "grandfathered": grand}


def parse_whop(s):
    h = next(x for x in s.find_all(HEADING) if re.search(r"Supported countries", x.get_text(), re.I))
    grid = h.find_next("div", class_="mint-grid")
    return {"payouts": [(c.get_text(" ", strip=True), None) for c in grid.select("span.mint-rounded-md")]}


def parse_lemon(s):
    bank = []
    h = next(x for x in s.find_all(HEADING) if x.get_text(strip=True) == "Supported countries")
    for li in h.find_all_next("li"):
        inner = li.find("ul")
        if inner and "following countries" in li.get_text(" ", strip=True)[:200]:
            for x in inner.find_all("li", recursive=False):
                name = x.get_text(" ", strip=True)
                # A trailing '*' points to a footnote on the same page (e.g. India: Stripe invite-only since May 2024).
                bank.append((name.rstrip("* ").strip(), "footnote" if name.endswith("*") else None))
            break
    blocked = [(t, None) for t in section_items(s, r"^\W*Unsupported countries for purchases")]
    return {"bank_payouts": bank, "purchases_blocked": blocked}


def parse_etsy(s):
    h = next(x for x in s.find_all(HEADING) if "Countries Eligible for Etsy Payments" in x.get_text())
    ul = next(u for u in h.find_all_next("ul") if len(u.find_all("li", recursive=False)) > 15)
    out = []
    for li in ul.find_all("li", recursive=False):
        name = li.get_text(" ", strip=True)
        starred = name.endswith("*")
        out.append((name.rstrip("*").strip(), "payoneer" if starred else None))
    return {"eligible": out}


def parse_paddle(s):
    h = next(x for x in s.find_all(HEADING) if "Unsupported Countries" in x.get_text())
    ul = h.find_next("ul")
    out = []
    for li in ul.find_all("li", recursive=False):
        name = li.get_text(" ", strip=True).replace("*", "").strip()
        out.append((name, None))
    return {"unsupported": out}


def parse_paypal_payouts(s):
    h = next(x for x in s.find_all(HEADING) if "Eligible countries and their feature sets" in x.get_text())
    tbl = h.find_next("table")
    out = []
    for r in tbl.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        if len(cells) >= 2 and cells[0]:
            # Superscript digits (e.g. 'Brazil¹') point to PayPal's country-specific restriction notes on the same page.
            name = re.sub(r"[¹²³⁰-⁹]+$", "", cells[0]).strip()
            footnote = name != cells[0]
            out.append((name + (" (see PayPal restriction note)" if footnote else ""), cells[1]))
    return {"eligible": out}


def parse_paypal_worldwide(s):
    # Each PayPal market is a link to /<cc>/home whose name span sits inside an HTML <template>; bs4's default get_text
    # skips template strings, so collect every NavigableString explicitly.
    from bs4.element import NavigableString
    out, seen = [], set()
    for sp in s.select("[data-testid=country-list-item-name]"):
        name = "".join(str(c) for c in sp.descendants if isinstance(c, NavigableString)).strip()
        a = sp.find_parent("a")
        if name and a is not None and re.fullmatch(r"/[a-z]{2}/home", a.get("href", "")) and name not in seen:
            seen.add(name)
            out.append((name, None))
    return {"markets": out}


def parse_gplay(s):
    h = next(x for x in s.find_all(HEADING) if "Supported locations for developer and merchant registration" in x.get_text())
    tbl = next(t for t in h.find_all_next("table") if "Merchant Registration" in t.get_text())
    # Footnote markers like "EGP[1]" point to text below the table (e.g. "[1] Developers in these countries will be paid in
    # USD or EUR, depending on their location."). Read it from the page; a marker without its text fails the build.
    page = s.get_text(" ", strip=True)
    notes = {n: t.strip() for n, t in re.findall(r"\[(\d+)\]\s+([A-Z][^\[]*?\.)(?=\s|$)", page)}
    dev, merch = [], []
    for r in tbl.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in r.find_all("td")]
        if len(cells) < 3:
            continue
        name, d, m = cells[0], cells[1], cells[2]
        cur = cells[3] if len(cells) > 3 else None
        if d == "✔":
            dev.append((name, None))
        if m == "✔":
            label = None
            if cur and cur not in ("☆",):
                mk = re.search(r"\[(\d+)\]\s*$", cur)
                cur_clean = re.sub(r"\s*\[\d+\]\s*$", "", cur)
                label = f"default currency {cur_clean}"
                if mk:
                    if mk.group(1) not in notes:
                        raise RuntimeError(f"Google Play footnote [{mk.group(1)}] used by {name} but its text was not found")
                    label += f"; footnote [{mk.group(1)}]: {notes[mk.group(1)]}"
            merch.append((name, label))
    return {"developer_registration": dev, "merchant_registration": merch}


def parse_un(s):
    out = []
    for card in s.select("div.card-body"):
        h = card.find("h2")
        if not h:
            continue
        m = re.search(r"Date of Admission:\s*([0-9-]+)", card.get_text(" ", strip=True))
        out.append((h.get_text(" ", strip=True), f"admitted {m.group(1)}" if m else None))
    return {"members": out}


def parse_youtube_ypp(s):
    intro = next((el for el in s.find_all(["p", "div", "strong"])
                  if "in the following areas" in el.get_text(" ", strip=True)
                  and len(el.get_text(" ", strip=True)) < 300), None)
    if intro is None:
        raise RuntimeError("YPP intro sentence not found (page layout changed?)")
    ul = intro.find_next("ul")
    return {"signup_areas": [(li.get_text(" ", strip=True), None) for li in ul.find_all("li", recursive=False)]}


SOURCES = {
    "stripe": {
        "route": "stripe", "url": "https://stripe.com/global", "parser": parse_stripe,
        "lists": {"available": {"meaning": "merchant_signup_available", "min_items": 40,
                                "label_meanings": {"Extended network": "extended_network_via_paystack", "Preview": "preview_contact_sales"}}},
    },
    "polar": {
        "route": "polar", "url": "https://polar.sh/docs/merchant-of-record/supported-countries", "parser": parse_polar,
        "lists": {"payouts": {"meaning": "payout_supported", "min_items": 80,
                              "caveat": "Payouts run on Stripe Connect Express; individuals need Stripe Express to support the 'individual' business type in your country (check per Polar's FAQ)."}},
    },
    "dodo": {
        "route": "dodo", "url": "https://docs.dodopayments.com/miscellaneous/accepted-countries-and-territories", "parser": parse_dodo,
        # Explicit, reviewed mappings for names that are ambiguous on their own. Reason is stored with each entry.
        "name_overrides": {"Virgin Islands": ("VI", "Listed as 'Virgin Islands'; 'British Virgin Islands' is listed separately "
                                                    "on the same page, so this entry is read as the U.S. Virgin Islands.")},
        "lists": {"accepted": {"meaning": "seller_accepted", "min_items": 120,
                               "caveat": "Eligibility is decided by the country that issued your government ID (every director/owner for companies)."},
                  "grandfathered": {"meaning": "grandfathered_only", "min_items": 3,
                                    "caveat": "Only merchants already onboarded before the country was prohibited may continue (enhanced monitoring); no new sign-ups."}},
    },
    "whop": {
        "route": "whop", "url": "https://docs.whop.com/manage-your-business/manage-payouts/set-up-payouts", "parser": parse_whop,
        "lists": {"payouts": {"meaning": "payout_supported", "min_items": 150,
                              "caveat": "Payout methods (bank, PayPal, crypto) vary by country and are shown in your Whop balance screen."}},
    },
    "lemon": {
        "route": "lemonsqueezy", "url": "https://docs.lemonsqueezy.com/help/getting-started/supported-countries", "parser": parse_lemon,
        "lists": {"bank_payouts": {"meaning": "payout_supported_bank", "min_items": 60,
                                   "label_meanings": {"footnote": "payout_supported_bank_restricted"},
                                   "footnote": "From May 2024, Stripe only accepts new accounts from India on an invite-only basis; merchants "
                                               "can only set up a bank payout if their accounts are pre-approved by Stripe, otherwise they "
                                               "must use PayPal (quoted from Lemon Squeezy's page, 2026-10-17).",
                                   "caveat": "PayPal payouts are documented separately ('200+ countries' per PayPal's list) and are not confirmed per country here. Lemon Squeezy is migrating merchants to Stripe Managed Payments."},
                  "purchases_blocked": {"meaning": "buyers_blocked", "min_items": 1}},
    },
    "etsy": {
        "route": "etsy", "url": "https://help.etsy.com/hc/en-us/articles/115015710408", "parser": parse_etsy,
        "group_entries": {"United States territories": "Group entry on Etsy's list; not expanded to individual territories."},
        "lists": {"eligible": {"meaning": "seller_payments_eligible", "min_items": 40,
                               "label_meanings": {"payoneer": "seller_payments_eligible_via_payoneer"},
                               "caveat": "Countries marked * on Etsy's page accept Etsy Payments through a Payoneer Payment Account."}},
    },
    "paddle": {
        "route": "paddle", "url": "https://www.paddle.com/help/start/intro-to-paddle/which-countries-are-supported-by-paddle",
        "parser": parse_paddle,
        "lists": {"unsupported": {"meaning": "seller_unsupported", "min_items": 15,
                                  "caveat": "Paddle states it 'works with software businesses anywhere in the world with the exception of' "
                                            "these countries. Software only; every seller and product is reviewed before sales are enabled."}},
    },
    "paypal_payouts": {
        "route": "paypal", "url": "https://developer.paypal.com/payouts/supported-features", "parser": parse_paypal_payouts,
        "lists": {"eligible": {"meaning": "paypal_payouts_receive", "min_items": 60,
                               "label_meanings": {"Receive and withdraw": "paypal_payouts_receive_only",
                                                  "Send, receive, and withdraw": "paypal_payouts_send_receive",
                                                  "Send, receive, and withdraw in local currency": "paypal_payouts_send_receive_local",
                                                  "Fully localized": "paypal_payouts_fully_localized"},
                               "caveat": "PayPal Payouts is how many platforms (e.g. creator platforms) send earnings to PayPal accounts. "
                                         "A country missing here may still have PayPal accounts that can buy or send."}},
    },
    "paypal_worldwide": {
        "route": "paypal", "url": "https://www.paypal.com/us/webapps/mpp/country-worldwide", "parser": parse_paypal_worldwide,
        "lists": {"markets": {"meaning": "paypal_market_listed", "min_items": 150,
                              "caveat": "Listed = PayPal operates a site for this market. It does NOT say whether accounts there can receive money."}},
    },
    "gplay": {
        "route": "google_play", "url": "https://support.google.com/googleplay/android-developer/answer/9306917?hl=en", "parser": parse_gplay,
        "lists": {"developer_registration": {"meaning": "developer_registration", "min_items": 100},
                  "merchant_registration": {"meaning": "merchant_registration", "min_items": 80,
                                            "caveat": "Merchant registration is required to sell paid apps, in-app purchases or subscriptions."}},
    },
    "un_members": {
        "route": "_scope", "url": "https://www.un.org/en/about-us/member-states", "parser": parse_un,
        "lists": {"members": {"meaning": "un_member_state", "min_items": 193, "exact_items": 193}},
    },
    "youtube_ypp": {
        "route": "youtube", "url": "https://support.google.com/youtube/answer/7101720?hl=en", "parser": parse_youtube_ypp,
        "name_overrides": {"Republic of Ireland": ("IE", "YouTube lists 'Republic of Ireland' and 'United Kingdom' as separate entries; "
                                                         "the only UN members with 'Ireland' in their UN name are Ireland (IE) and the United "
                                                         "Kingdom of Great Britain and Northern Ireland (GB), so this entry is IE. Checked 2026-10-17.")},
        "lists": {"signup_areas": {"meaning": "ypp_signup_available", "min_items": 100,
                                   "caveat": "Availability is by the channel's country. The page also carries a 10 March 2022 note pausing new "
                                             "Russian AdSense/AdMob/Ad Manager accounts."}},
    },
}


def collect(sid):
    cfg = SOURCES[sid]
    raw = fetch(cfg["url"])
    sha = hashlib.sha256(raw).hexdigest()
    parsed = cfg["parser"](soup_of(raw))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lists, problems = {}, []
    for name, lcfg in cfg["lists"].items():
        items = parsed.get(name, [])
        if "exact_items" in lcfg and len(items) != lcfg["exact_items"]:
            problems.append(f"{sid}.{name}: {len(items)} items, expected exactly {lcfg['exact_items']}")
        if len(items) < lcfg.get("min_items", 1):
            problems.append(f"{sid}.{name}: only {len(items)} items (< {lcfg.get('min_items')}); layout may have changed")
        entries, seen = [], set()
        overrides = cfg.get("name_overrides", {})
        groups = cfg.get("group_entries", {})
        skipped_groups = []
        for raw_name, label in items:
            if raw_name in groups:
                skipped_groups.append({"raw": raw_name, "note": groups[raw_name]})
                continue
            mapping_note = None
            try:
                if raw_name in overrides:
                    code, mapping_note = overrides[raw_name]
                    note = None
                else:
                    code, note = normalize(raw_name)
            except UnknownCountry:
                problems.append(f"{sid}.{name}: unknown country name {raw_name!r} (add an alias in countries.py)")
                continue
            if code in seen:
                continue
            seen.add(code)
            meaning = lcfg["meaning"]
            tag = label or note
            if tag and tag in lcfg.get("label_meanings", {}):
                meaning = lcfg["label_meanings"][tag]
            entry = {"code": code, "raw": raw_name, "label": tag, "meaning": meaning}
            if tag == "footnote" and lcfg.get("footnote"):
                entry["footnote"] = lcfg["footnote"]
            if mapping_note:
                entry["mapping_note"] = mapping_note
            entries.append(entry)
        lists[name] = {"meaning": lcfg["meaning"], "caveat": lcfg.get("caveat"), "count": len(entries), "entries": entries,
                       "group_entries_not_expanded": skipped_groups}
    if problems:
        raise RuntimeError("\n  ".join([f"{sid} FAILED, nothing written:"] + problems))

    snap_dir = ROOT / "data" / "snapshots" / sid
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap = snap_dir / f"{now[:10]}-{sha[:12]}.html.gz"
    if not snap.exists():
        snap.write_bytes(gzip.compress(raw))
    out = {"source": sid, "route": cfg["route"], "url": cfg["url"], "retrieved_at": now, "sha256": sha,
           "snapshot": str(snap.relative_to(ROOT)).replace("\\", "/"), "evidence": "official", "lists": lists}
    (ROOT / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "sources" / f"{sid}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ids = sys.argv[1:] or list(SOURCES)
    failed = 0
    for sid in ids:
        try:
            out = collect(sid)
            print(f"OK   {sid}: " + ", ".join(f"{k}={v['count']}" for k, v in out["lists"].items()))
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
