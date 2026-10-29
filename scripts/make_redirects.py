"""Build a redirect-only copy of the site for the old GitHub Pages address.

    python scripts/make_redirects.py site/dist _redirect_site https://getpaidfrom.getpaidfrom.workers.dev

Every page that exists in the built site gets a tiny page at the same path that sends the reader (and search
engines: canonical link + immediate meta refresh) to the same page on the live host. Unknown paths go to the
live home page. The workflow deploys this to GitHub Pages while the site itself is served by Cloudflare, so the
old copy can no longer compete with the live one in search results.
"""
import html
import shutil
import sys
from pathlib import Path

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Moved</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={url}">
<script>location.replace({js} + location.hash)</script>
</head><body><p>This page has moved to <a href="{url}">{url}</a>.</p></body></html>
"""


def page(url):
    safe = html.escape(url, quote=True)
    return PAGE.format(url=safe, js='"' + url.replace("\\", "\\\\").replace('"', '\\"') + '"')


def main():
    dist, out, host = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].rstrip("/")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    n = 0
    for f in dist.rglob("index.html"):
        rel = f.parent.relative_to(dist).as_posix()
        target = out / f.relative_to(dist)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(f"{host}/{rel + '/' if rel != '.' else ''}"), encoding="utf-8")
        n += 1
    (out / "404.html").write_text(page(f"{host}/"), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{n} redirect pages to {host}")


if __name__ == "__main__":
    main()
