"""Check that every quote in a research file really appears in its saved snapshot.

    python scripts/check_quotes.py PK        # or: all

Matching ignores case, spacing and punctuation (PDF extraction breaks words and hyphens). A quote may skip text with
"..." or "…"; each remaining fragment of 12+ letters/digits must appear in the snapshot. Square brackets are kept as
fragment boundaries (laws use them for amendments). Editorial text we add goes in curly braces {like this} and is not
checked. Sources with "quote_type": "description" (e.g. "X is absent from this list"), "rendered_reading" (read from a
rendered page image because text extraction scrambles it) or no snapshot are reported, not matched.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grep_snap import text_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
_cache = {}


def norm(s):
    # keep letters/digits of every script (Bangla, Arabic, ...); drop spacing, punctuation and combining marks.
    # NFKD first so composed "ô" and decomposed "o"+"̂" (pages differ) compare equal once marks are dropped.
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[\W_]+", "", "".join(ch for ch in s if not unicodedata.combining(ch)))


def snapshot_text(rel):
    if rel not in _cache:
        _cache[rel] = norm(text_of(str(ROOT / rel)))
    return _cache[rel]


def fragments(quote):
    q = re.sub(r"\{[^}]*\}", "|", quote)
    return [norm(f) for f in re.split(r"\.\.\.|…|\[|\]|\|", q) if len(norm(f)) >= 12]


def check(code):
    doc = json.loads((ROOT / "data" / "research" / f"{code}.json").read_text(encoding="utf-8"))
    bad = 0
    for fid, f in doc["facts"].items():
        for i, s in enumerate(f.get("sources", [])):
            tag = f"{code} {fid} source {i}"
            if s.get("quote_type") in ("description", "rendered_reading"):
                print(f"  skip  {tag}: {s['quote_type']} (not machine-matchable; see the fact's notes)")
                continue
            if not s.get("snapshot"):
                print(f"  skip  {tag}: no snapshot ({s.get('url')})")
                continue
            text = snapshot_text(s["snapshot"])
            missing = [fr for fr in fragments(s["quote"]) if fr not in text]
            if missing:
                bad += 1
                print(f"  FAIL  {tag}: {len(missing)} fragment(s) not in {s['snapshot']}: {missing[0][:80]}")
    print(f"{code}: {'OK' if not bad else 'FAIL'} ({bad} unmatched quotes)")
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    target = sys.argv[1]
    codes = [p.stem for p in sorted((ROOT / "data" / "research").glob("*.json"))] if target == "all" else [target]
    sys.exit(1 if sum(check(c) for c in codes) else 0)


if __name__ == "__main__":
    main()
