"""Checks for the site generator's text handling (no network, no build output needed).

    python tests/test_build_site.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import rich, routes_view  # noqa: E402


def test_routes_split():
    r = routes_view("Barriers: Stripe does not accept merchants here; platforms that pay out through PayPal Payouts cannot pay PayPal "
                    "accounts here (not on PayPal's Payouts list, see P4 for ordinary PayPal receiving). Simple legal routes: (1) Sell on "
                    "Upwork. (2) For direct clients, a bank transfer works. Avoid: opening accounts with a foreign address.")
    assert len(r["barriers"]) == 2, r
    assert r["routes"] == ["Sell on Upwork.", "For direct clients, a bank transfer works."], r
    assert r["closing"].startswith("Avoid:"), r


def test_routes_sanctioned():
    r = routes_view("Barriers: Stripe does not accept merchants here; PayPal is not available. No clean workaround: these platforms exclude residents.")
    assert r["routes"] == [] and r["closing"].startswith("No clean workaround"), r


def test_routes_other_shape():
    assert routes_view("Some free text without the generated structure.") is None


def test_rich_escapes_and_links():
    out = str(rich("TRAP: <script>x</script> see L3 & P1"))
    assert "<script>" not in out and "&lt;script&gt;" in out, out
    assert '<strong class=trap>TRAP:</strong>' in out, out
    assert 'href="#L3"' in out and 'href="#P1"' in out and "&amp;" in out, out


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK ({len(tests)} checks)")
