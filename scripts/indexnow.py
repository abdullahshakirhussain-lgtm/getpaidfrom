"""Tell IndexNow (Bing, Yandex, Naver, Seznam, Yep) which pages changed in this deploy.

    python scripts/indexnow.py OLD_SITEMAP NEW_SITEMAP

Compares <lastmod> per URL between the live sitemap before deploy and the new one, and submits only new or changed
URLs (re-submitting unchanged pages can be treated as spam). Skips when the site has no own host root (e.g. a
github.io project path), because the key file must sit at the host's root.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
KEY = (ROOT / "site" / "indexnow-key.txt").read_text(encoding="utf-8").strip()


def entries(path):
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {loc: mod for loc, mod in re.findall(r"<loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?", text)}


def main():
    old, new = entries(sys.argv[1]), entries(sys.argv[2])
    changed = [u for u, mod in new.items() if old.get(u) != mod or u not in old]
    if not changed:
        print("IndexNow: nothing changed")
        return
    host = urlparse(next(iter(new))).netloc
    if urlparse(next(iter(new))).path.strip("/"):  # first URL is the home page; a path means no own root
        print(f"IndexNow: skipped, site is not at the root of {host}")
        return
    body = json.dumps({"host": host, "key": KEY, "keyLocation": f"https://{host}/{KEY}.txt", "urlList": changed[:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: submitted {len(changed)} URLs, HTTP {r.status}")
    except urllib.error.HTTPError as e:  # don't fail the deploy over a ping
        print(f"IndexNow: HTTP {e.code} {e.read()[:200]!r}")


if __name__ == "__main__":
    main()
