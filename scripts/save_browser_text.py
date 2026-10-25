"""Save the visible text of a page read during a normal browser visit (for sites that refuse scripts) as a snapshot.

    python scripts/save_browser_text.py <url> <text_file>

Writes data/snapshots/_research/<date>-<sha12>.txt.gz and appends research_index.jsonl with "via": "browser_text".
This is a copy of what a person sees on the page, not the raw HTML; research files should say so in the fact's notes.
"""
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    url, src = sys.argv[1], Path(sys.argv[2])
    excerpt = "--excerpt" in sys.argv
    text = src.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        raise SystemExit("refused: captured text is under 200 characters (page probably did not load)")
    how = ("built-in browser, EXCERPT: only the visible paragraphs matching the research keywords" if excerpt
           else "built-in browser, visible text (document.body.innerText)")
    raw = f"URL: {url}\nCAPTURED VIA: {how}\n\n{text}".encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = ROOT / "data" / "snapshots" / "_research" / f"{now[:10]}-{sha[:12]}.txt.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gzip.compress(raw))
    rel = str(out.relative_to(ROOT)).replace("\\", "/")
    with (ROOT / "data" / "snapshots" / "research_index.jsonl").open("a", encoding="utf-8") as idx:
        idx.write(json.dumps({"url": url, "snapshot": rel, "sha256": sha, "retrieved": now, "via": "browser_text"}) + "\n")
    print(rel)


if __name__ == "__main__":
    main()
