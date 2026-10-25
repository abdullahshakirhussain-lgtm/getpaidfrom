"""Build the canonical country list (the 193 UN member states) from two official UN sources, with no library or memory involved.

Source A: UN member states page (https://www.un.org/en/about-us/member-states)
          - member name, date of admission, and the ISO alpha-2 code embedded in each card's flag CSS class (flags-xx)
Source B: UN Statistics Division M49 standard (https://unstats.un.org/unsd/methodology/m49/overview/)
          - English name, M49 numeric code, ISO alpha-2, ISO alpha-3, region/sub-region, LDC / LLDC / SIDS flags

A country is accepted only if the code from A exists in B. Any disagreement stops the build.
pycountry (the normalization library) is used only as a third cross-check and is never the source of truth.

Output: data/countries.json (+ gzipped snapshots of both pages in data/snapshots/)
"""
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import fetch  # noqa: E402
from countries import UnknownCountry, normalize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UN_URL = "https://www.un.org/en/about-us/member-states"
M49_URL = "https://unstats.un.org/unsd/methodology/m49/overview/"
CLDR_URL = "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-localenames-full/main/en/territories.json"
CLDR_PKG = "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/cldr-localenames-full/package.json"


def snapshot(sid, raw, now):
    sha = hashlib.sha256(raw).hexdigest()
    d = ROOT / "data" / "snapshots" / sid
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{now[:10]}-{sha[:12]}.html.gz"
    if not p.exists():
        p.write_bytes(gzip.compress(raw))
    return sha, str(p.relative_to(ROOT)).replace("\\", "/")


def parse_un(raw):
    s = BeautifulSoup(raw.decode("utf-8", errors="replace"), "html.parser")
    out = []
    for card in s.select("div.card.country"):
        h = card.find("h2")
        flag = card.select_one("div.flags")
        codes = [c[len("flags-"):].upper() for c in (flag.get("class", []) if flag else []) if c.startswith("flags-")]
        m = re.search(r"Date of Admission:\s*([0-9-]+)", card.get_text(" ", strip=True))
        out.append({"un_name": h.get_text(" ", strip=True) if h else None,
                    "flag_code": codes[0] if len(codes) == 1 else None,
                    "admitted": m.group(1) if m else None})
    return out


def parse_m49(raw):
    s = BeautifulSoup(raw.decode("utf-8", errors="replace"), "html.parser")
    t = s.find("table", id="downloadTableEN")
    if t is None:
        raise RuntimeError("M49 English table (id=downloadTableEN) not found")
    rows = {}
    for r in t.find_all("tr"):
        c = [x.get_text(" ", strip=True) for x in r.find_all("td")]
        # Column layout observed 2026-10-17: global(0,1) region(2,3) sub-region(4,5) intermediate(6,7)
        # country(8) M49(9) ISO2(10) ISO3(11) LDC(12) LLDC(13) SIDS(14)
        if len(c) >= 12 and re.fullmatch(r"[A-Z]{2}", c[10] or ""):
            rows[c[10]] = {"m49_name": c[8], "m49": c[9], "iso2": c[10], "iso3": c[11],
                           "region": c[3], "sub_region": c[5], "intermediate_region": c[7] or None,
                           "ldc": (len(c) > 12 and c[12] == "x"), "lldc": (len(c) > 13 and c[13] == "x"),
                           "sids": (len(c) > 14 and c[14] == "x")}
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    un_raw, m49_raw = fetch(UN_URL), fetch(M49_URL)
    un_sha, un_snap = snapshot("un_members", un_raw, now)
    m49_sha, m49_snap = snapshot("un_m49", m49_raw, now)
    members, m49 = parse_un(un_raw), parse_m49(m49_raw)

    problems, countries = [], []
    if len(members) != 193:
        problems.append(f"UN page has {len(members)} member cards, expected 193")
    if len(m49) < 240:
        problems.append(f"M49 table parsed only {len(m49)} rows with ISO codes (expected ~249)")
    for mem in members:
        code = mem["flag_code"]
        if not code:
            problems.append(f"{mem['un_name']}: no single flag code on the UN card")
            continue
        row = m49.get(code)
        if row is None:
            problems.append(f"{mem['un_name']}: flag code {code} not found in M49")
            continue
        try:
            lib_code = normalize(mem["un_name"])[0]
        except UnknownCountry:
            lib_code = None
        countries.append({"code": code, "un_name": mem["un_name"], "admitted": mem["admitted"], **{k: v for k, v in row.items() if k != "iso2"},
                          "verification": {"un_flag_code": code, "m49_iso2": row["iso2"],
                                           "library_code": lib_code, "library_agrees": lib_code == code}})
    codes = [c["code"] for c in countries]
    if len(set(codes)) != len(codes):
        problems.append("duplicate codes among UN members")
    if problems:
        print("FAILED, nothing written:\n  " + "\n  ".join(problems))
        sys.exit(1)

    out = {"built_at": now, "count": len(countries),
           "sources": [{"id": "un_members", "url": UN_URL, "sha256": un_sha, "snapshot": un_snap, "evidence": "official"},
                       {"id": "un_m49", "url": M49_URL, "sha256": m49_sha, "snapshot": m49_snap, "evidence": "official"}],
           "countries": sorted(countries, key=lambda c: c["un_name"])}
    # Reference names (Unicode CLDR English territory names incl. alt variants) used only to VERIFY name->code mappings.
    cldr_raw = fetch(CLDR_URL)
    cldr_sha, cldr_snap = snapshot("cldr_en_territories", cldr_raw, now)
    cldr_version = json.loads(fetch(CLDR_PKG).decode("utf-8")).get("version")
    terr = json.loads(cldr_raw.decode("utf-8"))["main"]["en"]["localeDisplayNames"]["territories"]
    ref = {"source": CLDR_URL, "version": cldr_version, "sha256": cldr_sha, "snapshot": cldr_snap, "retrieved_at": now,
           "names": {k: v for k, v in terr.items() if re.fullmatch(r"[A-Z]{2}(-alt-[a-z]+)?", k)}}
    (ROOT / "data" / "reference").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "reference" / "cldr_en_territories.json").write_text(json.dumps(ref, indent=1, ensure_ascii=False), encoding="utf-8")
    out["sources"].append({"id": "cldr_en_territories", "url": CLDR_URL, "version": cldr_version, "sha256": cldr_sha,
                           "snapshot": cldr_snap, "evidence": "standard", "use": "name-to-code verification only"})
    (ROOT / "data" / "countries.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    disagree = [c for c in countries if not c["verification"]["library_agrees"]]
    print(f"OK: {len(countries)} UN member states; UN flag code matches M49 ISO2 for all.")
    print(f"Library cross-check disagreements (informational, sources win): {[(c['un_name'], c['code'], c['verification']['library_code']) for c in disagree]}")
    names_differ = [(c["un_name"], c["m49_name"]) for c in countries if c["un_name"].lower() != c["m49_name"].lower()]
    print(f"{len(names_differ)} members where the two UN sources spell the name differently (linked by code):")
    for a, b in names_differ:
        print(f"   UN page: {a!r:45} M49: {b!r}")


if __name__ == "__main__":
    main()
