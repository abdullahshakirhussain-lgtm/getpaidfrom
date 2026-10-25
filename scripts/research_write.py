"""Merge facts into data/research/<CODE>.json, resolving each source's snapshot from its quote.

    python scripts/research_write.py <facts.json> <CODE>

<facts.json> holds {"facts": {...}, optional "status", "open_questions"}. A source whose "snapshot" is "auto" gets the
saved snapshot (data/snapshots/_research*/) whose text contains every fragment of the quote. Several matches pick the one
whose URL in research_index.jsonl equals the source URL, else the newest. No match is an error: the quote is wrong or the
page was never saved. Sources with snapshot null (browser-only reads) or a quote_type are left as they are.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_quotes import fragments, snapshot_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def index_by_snapshot():
    p = ROOT / "data" / "snapshots" / "research_index.jsonl"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out.setdefault(r["snapshot"], set()).add(r["url"])
    return out


def candidates():
    files = []
    for d in ("_research", "_research_large"):
        files += sorted((ROOT / "data" / "snapshots" / d).glob("*.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p.relative_to(ROOT)).replace("\\", "/") for p in files]


def resolve(source, files, idx):
    if source.get("quote_type"):
        # descriptions / rendered readings can't be matched by text: use the newest snapshot saved for this exact URL
        by_url = [snap for snap, urls in idx.items() if source["url"] in urls]
        if not by_url:
            raise SystemExit(f"NO SNAPSHOT recorded for URL {source['url']} (quote_type={source['quote_type']})")
        return sorted(by_url, key=lambda s: (ROOT / s).stat().st_mtime)[-1]
    frs = fragments(source["quote"])
    if not frs:
        raise SystemExit(f"quote too short to match: {source['quote']!r}")
    # same-URL snapshots win anyway, so try them first and skip the full scan when one matches
    same = [rel for rel in files if source["url"] in idx.get(rel, ())]
    for rel in same:
        try:
            if all(f in snapshot_text(rel) for f in frs):
                return rel
        except Exception:  # noqa: BLE001
            continue
    hits = []
    for rel in files:
        try:
            text = snapshot_text(rel)
        except Exception:  # noqa: BLE001 - unreadable file is simply not a match
            continue
        if all(f in text for f in frs):
            hits.append(rel)
    if not hits:
        raise SystemExit(f"NO SNAPSHOT contains quote from {source['url']}: {source['quote'][:100]!r}")
    same_url = [h for h in hits if source["url"] in idx.get(h, ())]
    return (same_url or hits)[0]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    new = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    code = sys.argv[2]
    p = ROOT / "data" / "research" / f"{code}.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"code": code, "status": "in_progress", "facts": {}}
    files, idx = candidates(), index_by_snapshot()
    for fid, f in new["facts"].items():
        for s in f.get("sources", []):
            if s.get("snapshot") == "auto":
                s["snapshot"] = resolve(s, files, idx)
            m = re.search(r"/(\d{4}-\d\d-\d\d)-[0-9a-f]+\.[a-z]+\.gz$", s.get("snapshot") or "")
            if m:  # the snapshot is the evidence, so its capture date is the retrieval date
                s["retrieved"] = m.group(1)
                print(f"{fid}: {s['url'][:70]} -> {s['snapshot']}")
        doc["facts"][fid] = f
    for k in ("status", "started", "completed", "open_questions"):
        if k in new:
            doc[k] = new[k]
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)} ({len(doc['facts'])} facts)")


if __name__ == "__main__":
    main()
