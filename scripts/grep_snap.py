"""Search an already-saved snapshot and print the text around each match (no re-download).

    python scripts/grep_snap.py data/snapshots/_research/<file>.pdf.gz "<regex>" [--chars 600] [--max 10]

Use it to read a whole provision (e.g. a tax section) after snap.py has saved the page.
"""
import gzip
import io
import re
import sys
from pathlib import Path


def decode_html(raw):
    # UTF-8 when valid; otherwise Windows-1252 (superset of ISO-8859-1, used by e.g. planalto.gov.br).
    # Letting bs4 guess picked Central-European code pages and turned "à" into "ŕ".
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # A page that is UTF-8 apart from a few stray bytes must not be re-read as cp1252 (that garbles all non-Latin text).
        lenient = raw.decode("utf-8", errors="replace")
        if lenient.count("�") <= max(5, len(lenient) // 2000):
            return lenient
        return raw.decode("cp1252", errors="replace")


def text_of(path):
    raw = gzip.decompress(Path(path).read_bytes())
    if path.endswith(".txt.gz"):
        return raw.decode("utf-8", errors="replace")
    if path.endswith(".pdf.gz"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
    from bs4 import BeautifulSoup
    s = BeautifulSoup(decode_html(raw), "html.parser")
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    return s.get_text(" ", strip=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path, pattern = sys.argv[1], sys.argv[2]
    width = int(sys.argv[sys.argv.index("--chars") + 1]) if "--chars" in sys.argv else 600
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10
    text = re.sub(r"\s+", " ", text_of(path))
    for i, m in enumerate(re.finditer(pattern, text, re.I)):
        if i >= limit:
            break
        print(f"--- match {i + 1} at {m.start()} ---")
        print(text[max(0, m.start() - width // 4): m.start() + width])


if __name__ == "__main__":
    main()
