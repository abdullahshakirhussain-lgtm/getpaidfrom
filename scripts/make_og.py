"""Render the link-preview images (Open Graph, 1200x630) for each language into site/static/og/<lang>.png.

    python scripts/make_og.py            # every language with an interface file
    python scripts/make_og.py es ar

Uses a locally installed Edge or Chrome in headless mode (set BROWSER to its path if it isn't found). Nothing is
downloaded: fonts and logos come from site/static/fonts and site/logos. Re-run after changing the wording.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import BRAND, logo  # noqa: E402
from i18n import I18N, LANGS, Translator  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONTS = (ROOT / "site" / "static" / "fonts").as_uri()
OUT = ROOT / "site" / "static" / "og"
CANDIDATES = [os.environ.get("BROWSER", ""),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
FACES = {"ar": "'Noto Sans Arabic'", "ur": "'Noto Nastaliq Urdu'", "bn": "'Noto Sans Bengali'", "vi": "'Segoe UI', Roboto, Arial"}


def page(lang):
    tr = Translator(lang)
    line = tr.t("meta_title_default").split(":", 1)[-1].strip()
    line = line[:1].upper() + line[1:]
    face = FACES.get(lang, "Atkinson")
    logos = "".join(f'<span class="l">{logo(s)}</span>' for s in ("paypal", "payoneer", "wise", "stripe", "upwork"))
    return f"""<!doctype html><html lang="{lang}" dir="{LANGS[lang][1]}"><meta charset="utf-8"><style>
@font-face {{ font-family: Newsreader; font-weight: 600; src: url({FONTS}/newsreader-latin-600-normal.woff2); }}
@font-face {{ font-family: Atkinson; font-weight: 700; src: url({FONTS}/atkinson-hyperlegible-next-latin-700-normal.woff2); }}
@font-face {{ font-family: 'Noto Sans Arabic'; font-weight: 700; src: url({FONTS}/noto-sans-arabic-arabic-700-normal.woff2); }}
@font-face {{ font-family: 'Noto Nastaliq Urdu'; src: url({FONTS}/noto-nastaliq-urdu-arabic-400-normal.woff2); }}
@font-face {{ font-family: 'Noto Sans Bengali'; font-weight: 700; src: url({FONTS}/noto-sans-bengali-bengali-700-normal.woff2); }}
html, body {{ margin: 0; width: 1200px; height: 630px; background: #fff; color: #15171c; overflow: hidden; }}
body {{ box-sizing: border-box; padding: 72px 84px; display: flex; flex-direction: column; justify-content: space-between; }}
.mark {{ font: 600 96px/1 Newsreader, Georgia, serif; letter-spacing: -1px; direction: ltr; text-align: left; }}
.mark i {{ display: inline-block; width: 210px; height: 30px; margin-left: 18px; background: #ffe45c; border-bottom: 7px solid #15171c; vertical-align: -6px; }}
.line {{ font: 700 54px/1.25 {face}, 'Segoe UI', sans-serif; max-width: 1000px; }}
.foot {{ display: flex; align-items: center; justify-content: space-between; border-top: 3px solid #15171c; padding-top: 26px;
         font: 700 30px/1 {face}, 'Segoe UI', sans-serif; color: #5d6370; }}
.logos {{ display: flex; gap: 26px; direction: ltr; }}
.l svg {{ width: 46px; height: 46px; }}
</style><body><div class="mark">Get paid from<i></i></div><div class="line">{line}</div>
<div class="foot"><span>{tr.t("all_193")}</span><span class="logos">{logos}</span></div></body></html>"""


def main():
    browser = next((c for c in CANDIDATES if c and Path(c).exists()), None) or shutil.which("msedge") or shutil.which("google-chrome")
    if not browser:
        sys.exit("No Edge or Chrome found; set BROWSER to the browser's path.")
    langs = sys.argv[1:] or [l for l in LANGS if l == "en" or (I18N / f"ui.{l}.json").exists()]
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            html = Path(tmp) / f"og-{lang}.html"
            html.write_text(page(lang), encoding="utf-8")
            png = OUT / f"{lang}.png"
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            f"--user-data-dir={tmp}/profile", "--window-size=1200,630", "--virtual-time-budget=3000",
                            f"--screenshot={png}", html.as_uri()], check=True, capture_output=True, timeout=120)
            print(f"{lang}: {png.relative_to(ROOT)} ({png.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
