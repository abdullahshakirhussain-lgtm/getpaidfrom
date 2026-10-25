"""Cross-check parsed source files against facts read manually from the same official pages on 2026-10-16.

If a platform genuinely changes its list, this test fails on purpose: re-read the page, confirm the change,
then update the expectation here (and the change goes into the updates feed).

    python tests/test_crosscheck.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# code -> expected meaning (None = must be absent). Read manually from the official pages on 2026-10-16.
EXPECT = {
    ("stripe", "available"): {"LK": None, "PK": None, "BD": None, "EG": None,
                              "NG": "extended_network_via_paystack", "KE": "extended_network_via_paystack",
                              "IN": "preview_contact_sales", "US": "merchant_signup_available"},
    ("polar", "payouts"): {"LK": "payout_supported", "PK": "payout_supported", "BD": "payout_supported",
                           "NG": "payout_supported", "EG": "payout_supported", "KE": "payout_supported"},
    ("dodo", "accepted"): {"LK": "seller_accepted", "PK": None, "KE": None, "BD": None, "NG": None, "EG": None},
    ("dodo", "grandfathered"): {"BD": "grandfathered_only", "NG": "grandfathered_only", "EG": "grandfathered_only",
                                "PK": None, "KE": None, "UA": "grandfathered_only", "MA": "grandfathered_only"},
    ("whop", "payouts"): {"LK": "payout_supported", "PK": "payout_supported", "BD": "payout_supported",
                          "EG": "payout_supported", "KE": "payout_supported", "NG": None},
    ("lemon", "bank_payouts"): {"LK": "payout_supported_bank", "PK": "payout_supported_bank", "BD": "payout_supported_bank",
                                "NG": "payout_supported_bank", "EG": "payout_supported_bank", "KE": "payout_supported_bank"},
    # Etsy help page read 2026-10-16: '*' = Etsy Payments via a Payoneer Payment Account. Sri Lanka not on the list.
    ("etsy", "eligible"): {"PK": "seller_payments_eligible_via_payoneer", "EG": "seller_payments_eligible_via_payoneer",
                           "IN": "seller_payments_eligible_via_payoneer", "US": "seller_payments_eligible",
                           "LK": None, "BD": None, "NG": None, "KE": None},
    # Paddle help page read 2026-10-16: unsupported (sanctions) list; none of our 6 test countries appear on it.
    ("paddle", "unsupported"): {"AF": "seller_unsupported", "RU": "seller_unsupported", "ZW": "seller_unsupported",
                                "XC-CRIMEA": "seller_unsupported", "LK": None, "PK": None, "BD": None, "NG": None,
                                "EG": None, "KE": None},
    # PayPal developer 'Countries and supported features' table read 2026-10-17 (printed row by row).
    ("paypal_payouts", "eligible"): {"KE": "paypal_payouts_send_receive", "IN": "paypal_payouts_receive_only",
                                     "US": "paypal_payouts_fully_localized", "LK": None, "PK": None, "BD": None,
                                     "NG": None, "EG": None},
    # PayPal worldwide page: Pakistan and Bangladesh have no PayPal market; the other four do.
    ("paypal_worldwide", "markets"): {"LK": "paypal_market_listed", "NG": "paypal_market_listed", "EG": "paypal_market_listed",
                                      "KE": "paypal_market_listed", "PK": None, "BD": None},
    # Google Play merchant table rows read 2026-10-17: Sri Lanka ✔ merchant; Afghanistan ✘ merchant.
    ("gplay", "merchant_registration"): {"LK": "merchant_registration", "PK": "merchant_registration", "AF": None},
}


def main():
    fails = 0
    for (sid, lst), expect in EXPECT.items():
        data = json.loads((ROOT / "data" / "sources" / f"{sid}.json").read_text(encoding="utf-8"))
        got = {e["code"]: e["meaning"] for e in data["lists"][lst]["entries"]}
        for code, meaning in expect.items():
            actual = got.get(code)
            if actual != meaning:
                fails += 1
                print(f"FAIL {sid}.{lst} {code}: expected {meaning}, got {actual}")
    print("crosscheck:", "OK" if not fails else f"{fails} mismatch(es)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
