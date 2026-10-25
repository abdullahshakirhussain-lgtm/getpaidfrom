"""Fetch a page, save a gzipped snapshot, and print the exact sentences matching a keyword pattern.

    python scripts/snap.py <url> "<regex>" [--max 15]

Prints JSON lines: {"url", "snapshot", "sha256", "retrieved", "matches": [...]} so quotes can be copied verbatim into research files.
PDFs are supported if pypdf is installed (text extracted page by page). Pages that block scripts must not be bypassed:
use a normal visit instead and mark the evidence accordingly.
"""
import gzip
import hashlib
import io
import json
import re
import sys
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LARGE_BYTES = 2_000_000
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read(), r.headers.get("Content-Type", "")
    except Exception as e:  # noqa: BLE001 - some government sites fail TLS with urllib; retry with curl
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        res = subprocess.run(["curl", "-s", "-L", "-m", "120", "-A", UA, "-o", path, "-w", "%{http_code} %{content_type}", url],
                             capture_output=True, text=True)
        code, _, ctype = res.stdout.partition(" ")
        if code != "200":
            raise RuntimeError(f"fetch failed: urllib {e!r}; curl HTTP {code}") from e
        data = Path(path).read_bytes()
        Path(path).unlink(missing_ok=True)
        return data, ctype


def to_text(raw, ctype, url):
    if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    from bs4 import BeautifulSoup
    from grep_snap import decode_html  # same decoding rule as the quote checker
    s = BeautifulSoup(decode_html(raw), "html.parser")
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    return s.get_text(" ", strip=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    url, pattern = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 15
    raw, ctype = fetch(url)
    # Some servers send a gzip/deflate body even when not asked; store the real document, not the compressed bytes.
    for _ in range(2):
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif raw[:1] == b"\x78":
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                break
        else:
            break
    if url.lower().endswith(".pdf") and not raw.lstrip()[:5] == b"%PDF-":
        # e.g. a JavaScript bot-check page served instead of the document: never save it as evidence, never try to get past it
        head = raw[:4000].decode("utf-8", errors="replace")
        hint = "bot-protection challenge" if re.search(r"TSPD|challenge|captcha|cf_chl|Just a moment", head, re.I) else "not a PDF"
        raise SystemExit(f"refused: {url} returned {hint} ({len(raw)} bytes, {ctype!r}); use a normal visit and record snapshot null")
    sha = hashlib.sha256(raw).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gz = gzip.compress(raw)
    # Big files (scanned gazettes, whole tax codes) stay local only (git-ignored); sha256 + URL still prove and re-fetch them.
    d = ROOT / "data" / "snapshots" / ("_research_large" if len(gz) > LARGE_BYTES else "_research")
    d.mkdir(parents=True, exist_ok=True)
    ext = ".pdf.gz" if ("pdf" in ctype.lower() or url.lower().endswith(".pdf")) else ".html.gz"
    snap = d / f"{now[:10]}-{sha[:12]}{ext}"
    if not snap.exists():
        snap.write_bytes(gz)
    with (ROOT / "data" / "snapshots" / "research_index.jsonl").open("a", encoding="utf-8") as idx:
        idx.write(json.dumps({"url": url, "snapshot": str(snap.relative_to(ROOT)).replace("\\", "/"),
                              "sha256": sha, "retrieved": now}) + "\n")
    text = re.sub(r"\s+", " ", to_text(raw, ctype, url))
    sentences = re.split(r"(?<=[.!?;])\s+", text)
    rx = re.compile(pattern, re.I)
    matches = [s.strip()[:600] for s in sentences if rx.search(s)][:limit]
    print(json.dumps({"url": url, "snapshot": str(snap.relative_to(ROOT)).replace("\\", "/"), "sha256": sha,
                      "retrieved": now, "chars": len(text), "matches": matches}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
