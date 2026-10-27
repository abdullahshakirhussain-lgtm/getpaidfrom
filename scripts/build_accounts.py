"""Structured platform status per country for the site's tiles and verdicts: PayPal, Payoneer, Wise, Gumroad, Payhip.

    python scripts/build_accounts.py        # writes data/display/accounts.json

Statuses: works / limited / likely / unconfirmed / no. Each entry has a one-line reason (15 words max) and its evidence:
either a fact in data/research (PayPal -> P4, Payoneer -> P5) or an official page snapshot (Wise, Gumroad, Payhip).
PayPal and Payoneer are read from the researched answers with explicit rules; any answer the rules don't recognise
stops the build so it gets reviewed instead of guessed.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from countries import UnknownCountry, normalize  # noqa: E402
from grep_snap import text_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "display" / "accounts.json"
WISE = {"url": "https://wise.com/help/articles/2813542/where-do-i-need-to-live-to-hold-money-with-wise", "publisher": "Wise",
        "title": "Where do I need to live to hold money with Wise?", "snapshot": "data/snapshots/_research/2026-10-25-883fe1515f7f.html.gz",
        "retrieved": "2026-10-25", "evidence": "official"}
GUMROAD = {"url": "https://gumroad.com/help/article/13-getting-paid", "publisher": "Gumroad", "title": "Getting paid by Gumroad",
           "snapshot": "data/snapshots/_research/2026-10-25-dd67ae825440.txt.gz", "retrieved": "2026-10-25", "evidence": "official"}
PAYHIP = {"url": "https://help.payhip.com/article/173-how-do-i-get-paid", "publisher": "Payhip", "title": "How do I get paid?",
          "snapshot": "data/snapshots/_research/2026-10-25-c1ac60567f2f.html.gz", "retrieved": "2026-10-25", "evidence": "official"}
PAYONEER = {"url": "https://www.payoneer.com/withdraw-funds/", "publisher": "Payoneer", "title": "Withdraw funds",
            "snapshot": "data/snapshots/_research/2026-10-25-d552328d05dc.html.gz", "retrieved": "2026-10-25", "evidence": "official"}
LOCAL_NAMES = {"Korea": "KR", "UK": "GB", "UAE (Business accounts)": "AE", "Czech Republic": "CZ", "Turkey": "TR", "Laos": "LA",
               "Vietnam": "VN", "Bolivia": "BO", "Moldova": "MD", "Tanzania": "TZ", "Brunei": "BN", "Bahamas": "BS", "Gambia": "GM"}

# ---- PayPal: classify the researched P4 answer ----
PP_WORKS = ("Yes", "Available", "Fully available", "PayPal works", "Officially yes", "Receiving now works", "PayPal operates in India")
PP_NO = ("No", "PayPal does not operate", "No local PayPal", "Effectively no")
PP_UNCONF = ("Unclear", "Not confirmed", "UNCLEAR", "PayPal lists")
PP_OVERRIDE = {  # status, reason: cases where the opening word isn't enough
    "IN": ("works", "Receive payments from abroad; money goes straight to your Indian bank."),
    "LK": ("works", "Works with Sampath or Commercial Bank, for personal accounts."),
    "MA": ("works", "Works; withdraw to a Moroccan bank within 30 days."),
    "KE": ("works", "Withdraw to your bank or to M-PESA."),
    "ZA": ("works", "Withdraw through FNB to a South African bank."),
    "TH": ("works", "Withdraw to a Thai bank; free from THB 5,000."),
    "NG": ("limited", "You must link a Nigerian partner bank to receive money."),
    "TZ": ("limited", "New M-Pesa link announced in May 2026; rollout still under way."),
    "SN": ("limited", "Officially works, but local withdrawals are slow and costly."),
    "CN": ("limited", "Works, with extra PayPal restrictions for China."),
    "DZ": ("limited", "Receiving needs a foreign card or US bank; withdrawals are limited."),
    "CI": ("no", "Send-only here: no withdrawals to local banks."),
    "CM": ("no", "You can receive, but can't withdraw to a local bank."),
    "TN": ("no", "Send-only here: you can pay, but not receive income."),
    "NP": ("no", "You can open an account, but not receive payments."),
    "ET": ("no", "Accounts here can only send and shop, not receive."),
    "TR": ("no", "PayPal stopped operating in Türkiye in 2016."),
    "YE": ("no", "Not usable here for receiving payments."),
    "EG": ("unconfirmed", "PayPal operates here, but receiving and withdrawing aren't confirmed."),
    "UG": ("unconfirmed", "Reports conflict on whether you can withdraw."),
}


def paypal(cc, fact):
    if cc in PP_OVERRIDE:
        return PP_OVERRIDE[cc]
    a = fact["answer"]
    if a.startswith(PP_WORKS):
        return "works", "Receive from clients and withdraw to your bank."
    if a.startswith(PP_NO):
        return "no", "PayPal doesn't operate here."
    if a.startswith(PP_UNCONF):
        return "unconfirmed", "PayPal operates here, but receiving payments isn't confirmed."
    raise SystemExit(f"PayPal answer for {cc} not recognised, review it: {a[:120]}")


# ---- Payoneer: confirmed where research found country-specific evidence; 'likely' elsewhere ----
PO_WORKS = {  # country-specific evidence in P5 (reason may be specific)
    "BD": "Withdraw to your bank or bKash.", "LK": "Withdraw to an eZ Cash wallet.",
    "PK": "Individual accounts allowed; no registered business needed.", "IN": "Withdraw in rupees to your Indian bank.",
    "VN": "Personal accounts allowed without a business licence.", "KE": "Receive in shillings; withdraw to your bank.",
    "MA": "Works; the money must come home to a Moroccan bank.", "PH": "Withdraw to any Philippine bank in your name.",
    "AR": "Withdraw in pesos, or in USD to an Argentine account.", "CO": "Withdraw in pesos or USD to a Colombian bank.",
    "MX": "Withdraw in pesos to a Mexican bank.", "GH": "Withdraw in cedis to a Ghanaian bank.",
    "SN": "Withdraw in CFA francs to a Senegalese bank.", "CI": "Withdraw in CFA francs to an Ivorian bank.",
    "UG": "Withdraw in shillings to a Ugandan bank.", "TZ": "Withdraw to a Tanzanian bank.",
    "RW": "Withdraw to a Rwandan bank.", "ZA": "Withdraw to a South African bank.", "TR": "Withdraw to a Turkish bank.",
    "UA": "Widely used by Ukrainian freelancers.", "EG": "Available; withdrawal routes not confirmed.",
    "ID": "Receive in rupiah; withdraw to an Indonesian bank.", "BR": "Withdraw to your Brazilian bank.",
}
PO_LIMITED = {"NG": "Only via Kuda, for businesses registered with the CAC.",
              "DZ": "Used widely, but withdrawals to dinars are restricted."}
PO_UNCONF = {"NP": "Reports conflict; not confirmed on any Payoneer page.", "ET": "Not confirmed for residents here.",
             "ML": "Not confirmed for residents here.", "TN": "Not confirmed for residents here.",
             "BF": "Not confirmed for residents here."}
SANCTIONED = {"BY", "CU", "IR", "KP", "RU", "SY"}


def payoneer(cc, fact, platforms):
    if cc in SANCTIONED:
        return "no", "Not available to residents here (sanctions)."
    if cc in PO_LIMITED:
        return "limited", PO_LIMITED[cc]
    if cc in PO_UNCONF:
        return "unconfirmed", PO_UNCONF[cc]
    if cc in PO_WORKS:
        return "works", PO_WORKS[cc]
    if platforms.get("etsy.eligible", {}).get("status") == "seller_payments_eligible_via_payoneer":
        return "works", "Etsy pays sellers here through Payoneer."
    return "likely", "Payoneer serves 190+ countries; confirm when you sign up."


# ---- Wise: the official hold-money list ----
WISE_NOTE = {"IN": ("limited", "Only while you're travelling abroad, not at home."),
             "TH": ("limited", "Wise has paused new account details for Thailand."),
             "BH": ("works", "Personal accounts only."), "IL": ("works", "Personal accounts only."), "MY": ("works", "Personal accounts only."),
             "US": ("works", "Hold and receive money (not if you live in Nevada).")}


def wise_list(countries):
    """Countries named in Wise's hold-money list (names and restriction notes share one line, so match known names)."""
    t = re.sub(r"\s+", " ", text_of(WISE["snapshot"]))
    seg = t[t.index("Additional restrictions") + len("Additional restrictions"):t.index("We sometimes need to make changes")]
    codes = set()
    for cc, c in countries.items():
        for n in {c["un_name"], c.get("m49_name") or "", SHORT_NAMES.get(cc, "")}:
            if n and re.search(rf"(?<![A-Za-z]){re.escape(n)}(?![A-Za-z])", seg):
                codes.add(cc)
    return codes


SHORT_NAMES = {"KR": "South Korea", "CZ": "Czechia", "US": "United States", "GB": "United Kingdom", "NL": "Netherlands"}


def gumroad_table():
    t = text_of(GUMROAD["snapshot"])
    rows = t[t.index("Bank deposit countries"):t.index("Payout schedule")].splitlines()[1:]
    out = {}
    for row in rows:
        if "|" not in row:
            continue
        name, cur = [x.strip() for x in row.split("|", 1)]
        try:
            code = LOCAL_NAMES.get(name) or normalize(name)[0]
        except UnknownCountry:
            continue
        out[code] = cur
    return out


def main():
    countries = {json.loads(p.read_text(encoding="utf-8"))["code"]: json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted((ROOT / "data" / "countries").glob("*.json"))}
    wise = wise_list(countries)
    gum = gumroad_table()
    unknown_gum = set(gum) - set(countries)  # territories (HK, MO, TW, GI) are fine to ignore
    out = {}
    for cc, c in countries.items():
        F, P = c["facts"], c["platforms"]
        pp_s, pp_r = paypal(cc, F["P4_paypal"])
        po_s, po_r = payoneer(cc, F["P5_payoneer_wise"], P)
        if cc in WISE_NOTE:
            w_s, w_r = WISE_NOTE[cc]
        elif cc in wise:
            w_s, w_r = "works", "Hold money and get account details to receive payments."
        else:
            w_s, w_r = "no", "Wise doesn't let residents here hold or receive money."
        if cc in gum:
            g = ("works", f"Paid to your bank in {gum[cc].split(' (')[0]}.", GUMROAD)
        elif cc == "US":
            g = ("works", "Paid to your US bank account.", GUMROAD)
        elif pp_s == "works":
            g = ("works", "Paid through PayPal (2% fee); no bank deposits here.", GUMROAD)
        elif pp_s in ("limited", "unconfirmed"):
            g = ("unconfirmed", "Only through PayPal, which isn't confirmed here.", GUMROAD)
        else:
            g = ("no", "No payout route here (no bank deposit or PayPal).", GUMROAD)
        stripe = P.get("stripe.available", {}).get("status")
        if pp_s == "works" or stripe == "merchant_signup_available":
            h = ("works", "Connect PayPal or Stripe to get paid.", PAYHIP)
        elif stripe == "extended_network_via_paystack":
            h = ("works", "Connect Paystack to get paid.", PAYHIP)
        else:
            h = ("unconfirmed", "Needs a local processor Payhip supports; not confirmed here.", PAYHIP)
        out[cc] = {
            "paypal": {"status": pp_s, "reason": pp_r, "fact": "P4_paypal"},
            "payoneer": {"status": po_s, "reason": po_r, "fact": "P5_payoneer_wise",
                         **({"source": PAYONEER} if po_s == "likely" else {})},
            "wise": {"status": w_s, "reason": w_r, "source": WISE},
            "gumroad": {"status": g[0], "reason": g[1], "source": g[2]},
            "payhip": {"status": h[0], "reason": h[1], "source": h[2]},
        }
        for k, v in out[cc].items():
            assert len(v["reason"].split()) <= 15, (cc, k, v["reason"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    for k in ("paypal", "payoneer", "wise", "gumroad", "payhip"):
        print(k, dict(Counter(v[k]["status"] for v in out.values())))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out)} countries; Gumroad territories ignored: {sorted(unknown_gum)})")


if __name__ == "__main__":
    main()
