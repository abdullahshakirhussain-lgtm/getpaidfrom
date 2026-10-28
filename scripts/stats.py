"""Page views (last N days) and the number of email-alert sign-ups, from Cloudflare.

    python scripts/stats.py [DAYS]

Needs in .env (never committed): CF_ACCOUNT_ID and CF_STATS_TOKEN, a token with
"Account Analytics: Read" and "Workers KV Storage: Read". Nothing is personal: views are counted per page and
visitor country only (worker/index.js); sign-ups are counted, not printed.
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.cloudflare.com/client/v4"


def env():
    vals = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"')
    missing = [k for k in ("CF_ACCOUNT_ID", "CF_STATS_TOKEN") if not vals.get(k)]
    if missing:
        sys.exit(f"Add {', '.join(missing)} to .env (see this script's docstring).")
    return vals["CF_ACCOUNT_ID"], vals["CF_STATS_TOKEN"]


def call(token, url, data=None):
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def sql(account, token, query):
    text = call(token, f"{API}/accounts/{account}/analytics_engine/sql", query.encode())
    return json.loads(text).get("data", [])


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    account, token = env()
    since = f"timestamp > NOW() - INTERVAL '{days}' DAY"
    total = sql(account, token, f"SELECT SUM(_sample_interval) AS views FROM getpaidfrom_views WHERE {since} FORMAT JSON")
    print(f"Page views, last {days} days: {int(total[0]['views'] or 0) if total else 0}")
    for title, col in (("Top pages", "blob1"), ("Visitor countries", "blob2"), ("Referring sites", "blob3")):
        rows = sql(account, token, f"SELECT {col} AS k, SUM(_sample_interval) AS v FROM getpaidfrom_views WHERE {since} "
                                   f"GROUP BY k ORDER BY v DESC LIMIT 15 FORMAT JSON")
        print(f"\n{title}:")
        for r in rows:
            print(f"  {int(r['v']):>7}  {r['k'] or '(none)'}")
    spaces = json.loads(call(token, f"{API}/accounts/{account}/storage/kv/namespaces?per_page=100"))["result"]
    ns = next((n["id"] for n in spaces if n["title"].endswith("getpaidfrom-signups")), None)
    if ns:
        count, cursor = 0, ""
        while True:
            page = json.loads(call(token, f"{API}/accounts/{account}/storage/kv/namespaces/{ns}/keys?limit=1000&cursor={cursor}"))
            count += len(page["result"])
            cursor = page.get("result_info", {}).get("cursor") or ""
            if not cursor:
                break
        print(f"\nEmail-alert sign-ups: {count}")


if __name__ == "__main__":
    main()
