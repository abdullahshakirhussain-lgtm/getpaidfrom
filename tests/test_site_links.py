"""Check every internal link and in-page anchor in the built site (run scripts/build_site.py first).

    python tests/test_site_links.py
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

DIST = Path(__file__).resolve().parent.parent / "site" / "dist"


def main():
    broken, checked = [], 0
    for page in DIST.rglob("*.html"):
        if page.name == "404.html":  # its links are absolute to the live site on purpose
            continue
        rel = page.relative_to(DIST).as_posix()
        html = page.read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([^"]+)"', html))
        for href in re.findall(r'href="([^"]+)"', html):
            if href.startswith(("http:", "https:", "data:", "mailto:")):
                continue
            checked += 1
            if href.startswith("#"):
                if href[1:] not in ids:
                    broken.append((rel, href))
                continue
            path = urlparse(urljoin(f"http://x/{rel}", href)).path.lstrip("/")
            target = DIST / path
            if path == "" or target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append((rel, href))
    print(f"{checked} internal links checked, {len(broken)} broken")
    for b in broken[:20]:
        print("  BROKEN", *b)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
