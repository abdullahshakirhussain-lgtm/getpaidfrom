"""Build per-country files from verified sources + manual research, and validate research against the protocol.

    python scripts/country_build.py build            # writes data/countries/<CODE>.json for all 193 UN members
    python scripts/country_build.py validate PK      # validate one country's research file
    python scripts/country_build.py validate all
    python scripts/country_build.py progress         # how many countries are complete

Inputs:
  data/countries.json              193 UN members (UN page + M49, verified)
  data/sources/*.json              official platform lists (automated)
  data/mapping_audit.json          per-entry mapping verification (unresolved entries are treated as unverified)
  data/research/<CODE>.json        manual research per docs/RESEARCH_PROTOCOL.md
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CHECKLIST = ["P1_fx_receipts", "P2_fcy_account", "P3_local_gateways", "P4_paypal", "P5_payoneer_wise",
             "L1_registration", "L2_tax_id", "L3_income_tax_foreign", "L4_vat_gst", "L5_data_protection",
             "L6_consumer_ecommerce", "L7_incentives", "D1_id_document"]
STATUSES = {"verified", "conflicting", "unverified", "not_applicable"}
EVIDENCE = {"official", "secondary"}
# How to read absence from each list: inclusion lists -> "not_listed"; exclusion lists -> "not_excluded".
EXCLUSION_LISTS = {("paddle", "unsupported"), ("lemon", "purchases_blocked"), ("upwork", "restricted")}
SKIP_LISTS = {("un_members", "members")}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def platform_status(code, sources, unresolved):
    out = {}
    for sid, src in sources.items():
        for lname, lst in src["lists"].items():
            if (sid, lname) in SKIP_LISTS:
                continue
            key = f"{sid}.{lname}"
            entry = next((e for e in lst["entries"] if e["code"] == code), None)
            if (sid, code) in unresolved:
                status = {"status": "unverified", "reason": unresolved[(sid, code)]}
            elif entry:
                status = {"status": entry["meaning"]}
                for k in ("label", "footnote", "mapping_note"):
                    if entry.get(k):
                        status[k] = entry[k]
            else:
                status = {"status": "not_excluded" if (sid, lname) in EXCLUSION_LISTS else "not_listed"}
            status.update({"source_url": src["url"], "retrieved_at": src["retrieved_at"], "snapshot": src["snapshot"],
                           "evidence": src.get("evidence", "official")})
            if lst.get("caveat"):
                status["caveat"] = lst["caveat"]
            out[key] = status
    return out


def validate_research(code, research):
    errors, warnings = [], []
    facts = research.get("facts", {})
    for fid in CHECKLIST:
        if fid not in facts:
            errors.append(f"{fid}: missing")
    for fid, f in facts.items():
        st = f.get("status")
        if st not in STATUSES:
            errors.append(f"{fid}: bad status {st!r}")
            continue
        if not f.get("answer"):
            errors.append(f"{fid}: empty answer")
        srcs = f.get("sources", [])
        for i, s in enumerate(srcs):
            for k in ("url", "publisher", "retrieved", "evidence", "quote"):
                if not s.get(k):
                    errors.append(f"{fid}: source {i} missing {k}")
            if s.get("evidence") not in EVIDENCE:
                errors.append(f"{fid}: source {i} evidence must be official|secondary")
            if s.get("quote") and len(s["quote"].split()) > 80:
                warnings.append(f"{fid}: source {i} quote is long ({len(s['quote'].split())} words); trim to the proving sentence")
        official = sum(1 for s in srcs if s.get("evidence") == "official")
        # independent secondary = different websites; two quotes from one site are one source
        secondary = len({urlparse(s.get("url", "")).netloc.removeprefix("www.") for s in srcs if s.get("evidence") == "secondary"})
        if st == "verified" and not (official >= 1 or secondary >= 2):
            errors.append(f"{fid}: 'verified' needs >=1 official or >=2 independent secondary sites (has {official} official, {secondary} secondary site(s))")
        if st == "conflicting" and len(srcs) < 2:
            errors.append(f"{fid}: 'conflicting' needs >=2 sources")
        if st == "unverified" and not f.get("note"):
            errors.append(f"{fid}: 'unverified' needs a note saying what was searched")
        if st == "not_applicable" and not srcs:
            errors.append(f"{fid}: 'not_applicable' needs a source")
    return errors, warnings


def build():
    countries = load(ROOT / "data" / "countries.json")["countries"]
    sources = {p.stem: load(p) for p in sorted((ROOT / "data" / "sources").glob("*.json"))}
    unresolved = {}
    um = ROOT / "data" / "manual" / "unresolved_mappings.json"
    if um.exists():
        for key, v in load(um).items():
            sid, _raw = key.split("|", 1)
            unresolved[(sid, v["candidate_code"])] = v["why"]
            # the other candidate for an ambiguous name is equally unverified for that source
            if v["candidate_code"] == "CG":
                unresolved[(sid, "CD")] = v["why"]
    out_dir = ROOT / "data" / "countries"
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = 0
    for c in countries:
        rpath = ROOT / "data" / "research" / f"{c['code']}.json"
        research = load(rpath) if rpath.exists() else {"status": "not_started", "facts": {}}
        doc = {"code": c["code"], "un_name": c["un_name"], "m49_name": c["m49_name"], "iso3": c["iso3"], "m49": c["m49"],
               "region": c["region"], "sub_region": c["sub_region"], "ldc": c["ldc"], "lldc": c["lldc"], "sids": c["sids"],
               "un_admitted": c["admitted"], "built_at": now,
               "research_status": research.get("status", "not_started"),
               "platforms": platform_status(c["code"], sources, unresolved),
               "facts": research.get("facts", {})}
        out = out_dir / f"{c['code']}.json"
        if out.exists():
            old = load(out)
            if {k: v for k, v in old.items() if k != "built_at"} == {k: v for k, v in doc.items() if k != "built_at"}:
                continue  # unchanged: keep the old file so built_at only moves when content does
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        changed += 1
    print(f"built {len(countries)} country files in data/countries/ ({changed} changed)")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "validate":
        target = sys.argv[2]
        codes = [p.stem for p in sorted((ROOT / "data" / "research").glob("*.json"))] if target == "all" else [target]
        bad = 0
        for code in codes:
            errs, warns = validate_research(code, load(ROOT / "data" / "research" / f"{code}.json"))
            print(f"{code}: {'OK' if not errs else 'FAIL'} ({len(errs)} errors, {len(warns)} warnings)")
            for e in errs:
                print("   ERROR", e)
            for w in warns:
                print("   warn ", w)
            bad += bool(errs)
        sys.exit(1 if bad else 0)
    elif cmd == "progress":
        rs = {p.stem: load(p).get("status") for p in (ROOT / "data" / "research").glob("*.json")}
        done = [k for k, v in rs.items() if v == "complete"]
        print(f"complete: {len(done)}/193 -> {sorted(done)}; in progress: {sorted(k for k, v in rs.items() if v != 'complete')}")


if __name__ == "__main__":
    main()
