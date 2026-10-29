"""Production checklist for the built site (run scripts/build_site.py first). Runs in CI before every deploy.

    python tests/test_production.py

Every page: language tag, one title, a description, one h1, canonical + Open Graph pointing at the real host, an
existing preview image, a working skip link, valid JSON-LD, no internal research wording, sane size. Site-wide:
sitemap entries exist, robots.txt names the sitemap, hreflang alternates exist, every language has a not-found
page, the data downloads are complete, every search index covers every country.
"""
import csv
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import SITE_URL  # noqa: E402
from i18n import LANGS  # noqa: E402

INTERNAL = re.compile(r"\bnot captured\b|search summar|\bTRAP\b|automated collector|\bsnapshot|from this environment|"
                      r"\b[PLDW][1-7]_[a-z]|(?-i:\bTODO\b)|lorem ipsum|\{\{|\}\}|collector", re.I)
STRAY = re.compile(r">\s*(None|nan|null|undefined)\s*<")  # a template printing an empty Python/JS value
MAX_KB = 300


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.text, self.ld, self._ld, self._skip = [], [], [], None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld = []
        elif tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "script" and self._ld is not None:
            self.ld.append("".join(self._ld))
            self._ld = None
        elif tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        elif not self._skip:
            self.text.append(data)

    def find(self, tag, **attrs):
        return [a for t, a in self.tags if t == tag and all(a.get(k) == v for k, v in attrs.items())]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    problems = []
    built = [l for l in LANGS if l == "en" or (DIST / l / "index.html").exists()]
    pages = sorted(DIST.rglob("*.html"))
    host = urlsplit(SITE_URL).netloc
    for f in pages:
        rel = f.relative_to(DIST).as_posix()
        lang = rel.split("/")[0] if rel.split("/")[0] in LANGS and rel.split("/")[0] != "en" else "en"
        html = f.read_text(encoding="utf-8")
        p = Page()
        p.feed(html)
        say = lambda msg: problems.append(f"{rel}: {msg}")  # noqa: E731
        is_404 = rel == "404.html" or rel.endswith("404/index.html")
        if f'<html lang="{lang}" dir="{LANGS[lang][1]}"' not in html:
            say("wrong <html lang/dir>")
        if html.count("<title>") != 1 or re.search(r"<title>\s*</title>", html):
            say("needs exactly one non-empty <title>")
        desc = p.find("meta", name="description")
        if not desc or len(desc[0].get("content", "").strip()) < 40:
            say("missing or very short meta description")
        if len(p.find("h1")) != 1:
            say(f"{len(p.find('h1'))} h1 elements")
        canon = p.find("link", rel="canonical")
        if is_404:
            if canon:
                say("not-found page must not have a canonical link")
            if not p.find("meta", name="robots", content="noindex"):
                say("not-found page must be noindex")
        else:
            want = f"{SITE_URL}/{'' if rel == 'index.html' else rel[:-len('index.html')]}"
            if not canon or canon[0].get("href") != want:
                say(f"canonical should be {want}")
            alts = {a.get("hreflang"): a.get("href") for a in p.find("link", rel="alternate")}
            for code in built:
                href = alts.get(code)
                if not href or not (DIST / urlsplit(href).path.lstrip("/") / "index.html").exists() and not href.endswith("/" + rel.replace("index.html", "")) :
                    say(f"hreflang {code} missing or points to a missing page")
            if "x-default" not in alts:
                say("no x-default hreflang")
        og = {a.get("property"): a.get("content") for a in p.find("meta") if a.get("property", "").startswith("og:")}
        for key in ("og:title", "og:description", "og:url", "og:image", "og:locale"):
            if not og.get(key):
                say(f"missing {key}")
        if og.get("og:image") and not (DIST / urlsplit(og["og:image"]).path.lstrip("/")).exists():
            say(f"preview image not built: {og['og:image']}")
        if not p.find("a", href="#main") or 'id="main"' not in html:
            say("skip link or #main missing")
        for block in p.ld:
            try:
                json.loads(block)
            except ValueError as e:
                say(f"invalid JSON-LD: {e}")
        text = " ".join(p.text)
        m = INTERNAL.search(text)
        if m:
            say(f"internal wording on the page: {text[max(0, m.start() - 60):m.end() + 40]!r}")
        if STRAY.search(html):
            say(f"empty value printed: {STRAY.search(html).group(0)!r}")
        if re.search(r"https?://(localhost|127\.0\.0\.1)|http://" + re.escape(host), html):
            say("link to localhost or plain http on our own host")
        if f.stat().st_size > MAX_KB * 1024:
            say(f"{f.stat().st_size // 1024} KB, over {MAX_KB} KB")

    # sitemap and robots
    sm = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    if len(locs) != len(set(locs)):
        problems.append("sitemap has duplicate URLs")
    for loc in locs:
        if not loc.startswith(SITE_URL + "/"):
            problems.append(f"sitemap URL on the wrong host: {loc}")
        elif not (DIST / loc[len(SITE_URL) + 1:] / "index.html").exists():
            problems.append(f"sitemap URL with no page: {loc}")
    for d in re.findall(r"<lastmod>([^<]+)</lastmod>", sm):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            problems.append(f"bad lastmod {d}")
    robots = (DIST / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {SITE_URL}/sitemap.xml" not in robots or "Disallow: /api/" not in robots:
        problems.append("robots.txt must name the sitemap on the real host and keep /api/ out")

    # every language: not-found page, search index for every country
    n_countries = len(json.loads((DIST / "search.json").read_text(encoding="utf-8"))["countries"])
    for lang in built:
        prefix = "" if lang == "en" else f"{lang}/"
        if not (DIST / (prefix + ("404.html" if lang == "en" else "404/index.html"))).exists():
            problems.append(f"{lang}: no not-found page")
        s = json.loads((DIST / prefix / "search.json").read_text(encoding="utf-8"))
        if len(s["countries"]) != n_countries or n_countries != 193:
            problems.append(f"{lang}: search index has {len(s['countries'])} countries")

    # data downloads
    rows = list(csv.DictReader((DIST / "data" / "getpaidfrom.csv").open(encoding="utf-8-sig")))
    data = json.loads((DIST / "data" / "getpaidfrom.json").read_text(encoding="utf-8"))
    if len(rows) != 193 or len(data["countries"]) != 193:
        problems.append(f"data downloads: {len(rows)} CSV rows, {len(data['countries'])} JSON countries (want 193)")
    for c in data["countries"]:
        def strings(x):
            return [x] if isinstance(x, str) else [s for v in (x.values() if isinstance(x, dict) else x if isinstance(x, list) else []) for s in strings(v)]
        m = INTERNAL.search(" | ".join(strings(c)))
        if m:
            problems.append(f"data download, {c['code']}: internal wording {m.group(0)!r}")

    print("\n".join(problems[:80]))
    print(f"{len(pages)} pages in {len(built)} languages, {len(locs)} sitemap URLs: "
          f"{'OK' if not problems else f'{len(problems)} problems'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
