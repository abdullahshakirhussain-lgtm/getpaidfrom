"""Re-check the evidence behind the site and report what changed (run weekly by .github/workflows/recheck.yml).

    python scripts/recheck.py                  # platform lists + this week's quarter of the quoted sources
    python scripts/recheck.py --lists          # platform country lists only
    python scripts/recheck.py --quotes all     # every quoted source (slow)

1. Platform country lists (PayPal, Stripe, Wise via Payouts, Lemon Squeezy, ...): re-collected with collect.py and
   compared with the committed data/sources files; any country added, removed or relabelled is reported.
2. Quoted research sources: the live page is fetched again and every quote is matched the same way the quote checker
   matches snapshots. A quote that no longer appears means the rule may have changed and the fact needs review.
   Pages that refuse automated access, or whose robots.txt disallows it, are reported as unreachable and left alone
   (never worked around).

Writes recheck-report.md and exits 0; the workflow turns the report into a GitHub issue when there is something to review.
"""
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402
from check_quotes import fragments, norm  # noqa: E402
from snap import fetch, to_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "recheck-report.md"
UA_NAME = "GetPaidFromRecheck"
_robots = {}


def allowed(url):
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        # read robots.txt the same way as the page (urllib's own reader treats a 403 on robots.txt as "disallow all")
        rp = urllib.robotparser.RobotFileParser()
        try:
            raw, ctype = fetch(base + "/robots.txt")
            body = raw.decode("utf-8", "replace")
            rp = rp if "html" not in ctype.lower() and "<html" not in body[:500].lower() else None
            if rp:
                rp.parse(body.splitlines())
        except Exception:  # noqa: BLE001 - no readable robots.txt: no rule to follow
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return rp is None or rp.can_fetch(UA_NAME, url)


def check_lists():
    lines, changed = [], 0
    for sid in collect.SOURCES:
        old_path = ROOT / "data" / "sources" / f"{sid}.json"
        old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {"lists": {}}
        old_map = {(name, e["code"]): e["meaning"] for name, l in old["lists"].items() for e in l["entries"]}
        try:
            new = collect.collect(sid)  # overwrites the working copy only; nothing is committed by the workflow
        except Exception as e:  # noqa: BLE001
            lines.append(f"- **{sid}**: could not re-collect ({str(e).splitlines()[0][:200]})")
            continue
        new_map = {(name, e["code"]): e["meaning"] for name, l in new["lists"].items() for e in l["entries"]}
        added = sorted(k for k in new_map if k not in old_map)
        removed = sorted(k for k in old_map if k not in new_map)
        relabelled = sorted(k for k in new_map if k in old_map and new_map[k] != old_map[k])
        if added or removed or relabelled:
            changed += 1
            lines.append(f"- **{sid}** ({new['url']}): " + "; ".join(filter(None, [
                f"added {', '.join(c for _, c in added)}" if added else "",
                f"removed {', '.join(c for _, c in removed)}" if removed else "",
                f"relabelled {', '.join(f'{c} {old_map[(n, c)]}→{new_map[(n, c)]}' for n, c in relabelled)}" if relabelled else ""])))
        else:
            lines.append(f"- {sid}: no change")
    return changed, lines


def quoted_sources():
    by_url = defaultdict(list)
    for f in sorted((ROOT / "data" / "research").glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for fid, fact in doc["facts"].items():
            for s in fact.get("sources", []):
                if s.get("quote_type") in ("description", "rendered_reading") or not s.get("quote") or not s.get("url"):
                    continue
                by_url[s["url"]].append((f.stem, fid, s["quote"]))
    return by_url


def check_url(url, uses):
    if not allowed(url):
        return "blocked", url, uses, "robots.txt disallows automated access"
    try:
        raw, ctype = fetch(url)
        text = norm(to_text(raw, ctype, url))
    except Exception as e:  # noqa: BLE001
        return "unreachable", url, uses, str(e).splitlines()[0][:160]
    missing = [(c, fid) for c, fid, q in uses if any(fr not in text for fr in fragments(q))]
    return ("changed" if missing else "ok"), url, missing or uses, ""


def check_quotes(shard):
    by_url = quoted_sources()
    urls = sorted(by_url)
    if shard != "all":
        week = dt.date.today().isocalendar()[1]
        urls = [u for u in urls if int(hashlib.sha1(u.encode()).hexdigest(), 16) % 4 == week % 4]
    results = defaultdict(list)
    by_host = defaultdict(list)
    for u in urls:
        by_host[urllib.parse.urlsplit(u).netloc].append(u)

    def host_worker(host_urls):  # one host at a time, politely spaced
        out = []
        for u in host_urls:
            out.append(check_url(u, by_url[u]))
            time.sleep(2)
        return out

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(host_worker, by_host.values()):
            for status, url, uses, note in res:
                results[status].append((url, uses, note))
    return len(urls), results


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    today = dt.date.today().isoformat()
    parts = [f"# Source re-check {today}", ""]
    attention = 0
    if "--quotes" not in sys.argv:
        changed, lines = check_lists()
        attention += changed
        parts += ["## Platform country lists", "", *lines, ""]
    if "--lists" not in sys.argv:
        shard = sys.argv[sys.argv.index("--quotes") + 1] if "--quotes" in sys.argv else "week"
        n, res = check_quotes(shard)
        attention += len(res["changed"])
        parts += [f"## Quoted sources ({n} pages checked{'' if shard == 'all' else ', a quarter of all sources this week'})", "",
                  f"- quote still on the page: {len(res['ok'])}", f"- quote no longer found: **{len(res['changed'])}**",
                  f"- unreachable: {len(res['unreachable'])}", f"- robots.txt disallows: {len(res['blocked'])}", ""]
        if res["changed"]:
            parts += ["### Facts to review (the quoted text is no longer on the page)", ""]
            parts += [f"- {url}: " + ", ".join(f"{c} {fid}" for c, fid in uses) for url, uses, _ in res["changed"]]
            parts.append("")
        if res["unreachable"]:
            parts += ["### Unreachable this week (retry next cycle; not worked around)", ""]
            parts += [f"- {url}: {note}" for url, _, note in res["unreachable"][:60]]
            parts.append("")
    REPORT.write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts[:40]))
    print(f"\n{attention} item(s) need attention; report in {REPORT.name}")
    (ROOT / "recheck-attention.txt").write_text(str(attention), encoding="utf-8")


if __name__ == "__main__":
    main()
