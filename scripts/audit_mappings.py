"""Audit every country-name -> code mapping used in data/sources/*.json, so no mapping rests on memory.

A mapping is VERIFIED only by one of these, in order:
  1. embedded_code : the platform's own page carries the code (Stripe register?country=XX, PayPal /xx/home, Polar flag emoji)
  2. m49_exact     : the raw name equals the official UN name or the M49 English name (case/whitespace/apostrophe-insensitive)
  3. m49_rule      : equals an official name after a fixed, documented rewrite ('&'->'and', 'St.'->'Saint', drop 'The'/'Island')
  4. cldr          : equals a Unicode CLDR English territory name or alt variant (data/reference/cldr_en_territories.json)
  5. manual        : listed in data/manual/mapping_verifications.json with a source URL and a note
Anything else is UNVERIFIED and the audit fails. Non-UN entries (territories) are reported but only matter if used later.

    python scripts/audit_mappings.py
"""
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
FLAG = re.compile(r"([\U0001F1E6-\U0001F1FF])([\U0001F1E6-\U0001F1FF])")


def canon(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def fold(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def rule(s):
    # Fixed, documented rewrites only: accents folded, '&'->'and', 'St.'->'Saint', leading 'The'/trailing '(The)' dropped,
    # trailing ' Island' dropped, trailing all-caps abbreviation in brackets dropped (e.g. '(ROK)'), the word 'the' ignored.
    s = re.sub(r"\s*\([A-Z]{2,5}\)\s*$", "", s)
    s = fold(canon(s))
    s = s.replace("&", "and")
    s = re.sub(r"\bst\.\s", "saint ", s)
    s = re.sub(r"^the\s+|\s*\(the\)$", "", s)
    s = re.sub(r"\s+island$", "", s)
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def bracket_official(raw, official):
    """'Burma (Myanmar)': accept when the text inside the brackets is itself an official name."""
    m = re.search(r"\(([^)]+)\)\s*$", raw)
    return official.get(rule(m.group(1))) if m else None


def embedded_codes(sid, snapshot):
    """Return {raw_name: code} for names whose code is embedded in the platform page itself."""
    raw = gzip.decompress((ROOT / snapshot).read_bytes()).decode("utf-8", errors="replace")
    s = BeautifulSoup(raw, "html.parser")
    out = {}
    if sid == "stripe":
        for li in s.select("ul.GlobalCountryList li.GlobalCountryListItem"):
            a = li.find("a")
            name = li.get_text("|", strip=True).split("|")[0]
            m = re.search(r"[?&]country=([A-Z]{2})", a.get("href", "")) if a else None
            if m:
                out[name] = m.group(1)
    elif sid == "paypal_worldwide":
        from bs4.element import NavigableString
        for sp in s.select("[data-testid=country-list-item-name]"):
            a = sp.find_parent("a")
            name = "".join(str(c) for c in sp.descendants if isinstance(c, NavigableString)).strip()
            m = re.fullmatch(r"/([a-z]{2})/home", a.get("href", "")) if a else None
            if m and name:
                out[name] = m.group(1).upper()
    elif sid == "polar":
        for li in s.find_all("li"):
            t = li.get_text(" ", strip=True)
            m = FLAG.match(t)
            if m:
                code = "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in m.groups())
                out[t] = code
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    countries = json.loads((ROOT / "data" / "countries.json").read_text(encoding="utf-8"))["countries"]
    official = {}
    for c in countries:
        for n in (c["un_name"], c["m49_name"]):
            official.setdefault(canon(n), c["code"])
            official.setdefault(rule(n), c["code"])
    un_codes = {c["code"] for c in countries}
    cldr = {}
    for k, v in json.loads((ROOT / "data" / "reference" / "cldr_en_territories.json").read_text(encoding="utf-8"))["names"].items():
        cldr.setdefault(canon(v), k[:2])
        cldr.setdefault(rule(v), k[:2])
    manual_path = ROOT / "data" / "manual" / "mapping_verifications.json"
    manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
    unresolved_path = ROOT / "data" / "manual" / "unresolved_mappings.json"
    unresolved = json.loads(unresolved_path.read_text(encoding="utf-8")) if unresolved_path.exists() else {}

    report, unverified, nonun = [], [], []
    for f in sorted((ROOT / "data" / "sources").glob("*.json")):
        src = json.loads(f.read_text(encoding="utf-8"))
        sid = src["source"]
        emb = embedded_codes(sid, src["snapshot"])
        for lname, lst in src["lists"].items():
            for e in lst["entries"]:
                raw, code = e["raw"], e["code"]
                base = re.sub(r"\s*\(see PayPal restriction note\)$", "", raw)
                how = None
                if raw in emb or base in emb:
                    got = emb.get(raw, emb.get(base))
                    how = "embedded_code" if got == code else f"CONFLICT embedded={got}"
                elif official.get(canon(base)) == code:
                    how = "m49_exact"
                elif official.get(rule(base)) == code:
                    how = "m49_rule"
                elif bracket_official(base, official) == code:
                    how = "m49_bracket"
                elif cldr.get(canon(base)) == code or cldr.get(rule(base)) == code:
                    how = "cldr"
                elif f"{sid}|{raw}" in manual:
                    how = "manual"
                elif f"{sid}|{raw}" in unresolved:
                    how = "unresolved_excluded"
                if code not in un_codes:
                    nonun.append((sid, raw, code))
                    if how is None:
                        how = "non_un_unverified"
                if how is None or how.startswith("CONFLICT"):
                    unverified.append((sid, lname, raw, code, how))
                report.append({"source": sid, "list": lname, "raw": raw, "code": code, "verified_by": how})

    (ROOT / "data" / "mapping_audit.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("verification methods:", dict(Counter(r["verified_by"] for r in report)))
    print(f"non-UN entries (territories/regions, excluded from the 193 unless verified): {len(set((c for _, _, c in nonun)))} codes")
    if unverified:
        print(f"\nUNVERIFIED UN-member mappings ({len(unverified)}):")
        for u in unverified:
            print("  ", u)
        sys.exit(1)
    excluded = [r for r in report if r["verified_by"] == "unresolved_excluded"]
    print(f"All UN-member mappings verified by an official source, except {len(excluded)} logged as unresolved and excluded: "
          + ", ".join(f"{r['source']}:{r['raw']}" for r in excluded))


if __name__ == "__main__":
    main()
