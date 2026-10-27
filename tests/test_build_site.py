"""Checks for the site generator's rules (no network, no build output needed).

    python tests/test_build_site.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import CLIENT_ORDER, SELL_ORDER, check_short, clean_long, logo, sources, tile, verdict  # noqa: E402


def tiles(**status):
    return {s: tile(s, status.get(s.replace("-", "_"), "no"), f"{s} reason", []) for s in CLIENT_ORDER + SELL_ORDER}


def test_verdict_follows_fixed_order():
    v = verdict("XX", tiles(paypal="limited", payoneer="works", wise="works"), CLIENT_ORDER, "clients")
    assert v["headline"] == "Yes, through Payoneer." and v["slug"] == "payoneer", v
    v = verdict("XX", tiles(payoneer="likely"), CLIENT_ORDER, "clients")
    assert v["headline"] == "Probably, through Payoneer.", v
    v = verdict("XX", tiles(), CLIENT_ORDER, "clients")
    assert v["headline"] == "No platform confirmed." and "SWIFT" in v["detail"], v


def test_verdict_sanctioned_both_questions():
    for kind, order in (("clients", CLIENT_ORDER), ("selling", SELL_ORDER)):
        v = verdict("KP", tiles(paypal="works", gumroad="works"), order, kind)
        assert v["tone"] == "bad" and "Sanctions" in v["detail"], v


def test_check_short_rules():
    ok = {"facts": {"L4_vat_gst": "15% VAT above 2 million dalasi a year."}, "watch_out": []}
    assert check_short("GM", ok) == []
    bad = {"facts": {"L4_vat_gst": "15% VAT above D2 million a year.",
                     "L3_income_tax_foreign": " ".join(["word"] * 16)},
           "watch_out": [{"text": "TRAP: x", "fact": "L3_income_tax_foreign"}] * 4}
    problems = check_short("XX", bad)
    for expected in ("banned wording: 15% VAT above D2", "over 15 words", "banned wording: TRAP", "more than 3 watch-outs"):
        assert any(expected in p for p in problems), (expected, problems)


def test_every_country_has_valid_short_answers():
    shorts = sorted((ROOT / "data" / "display" / "short").glob("*.json"))
    countries = {p.stem for p in (ROOT / "data" / "countries").glob("*.json")}
    assert {p.stem for p in shorts} == countries, countries ^ {p.stem for p in shorts}
    for p in shorts:
        assert check_short(p.stem, json.loads(p.read_text(encoding="utf-8"))) == [], p.stem


def test_sources_listed_once_per_url():
    f = {"sources": [{"url": "https://a", "retrieved": "2026-10-01"}, {"url": "https://a", "retrieved": "2026-10-05"},
                     {"url": "https://b"}]}
    out = sources(f)
    assert [s["url"] for s in out] == ["https://a", "https://b"] and out[0]["retrieved"] == "2026-10-05", out


def test_clean_long_hides_internal_codes():
    out = clean_long("TRAP: rate changed (see L3). Use the account (P2 and P5).")
    assert "TRAP" not in out and "L3" not in out and "P2" not in out, out


def test_logos_are_inline_ink():
    svg = str(logo("paypal"))
    assert svg.startswith('<svg class="logo"') and 'fill="currentColor"' in svg and "<title>" not in svg, svg


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK ({len(tests)} checks)")
