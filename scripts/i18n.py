"""Translations for the site.

- Interface text: data/i18n/ui.<lang>.json (same keys as ui.en.json; {placeholders} kept).
- Content lines (short answers, warnings, reasons, verdicts, legal ways): data/i18n/strings.<lang>.tsv, one
  "<id>\t<translation>" per line, where <id> is a hash of the English text (sid()). If an English line changes, its
  id changes and the line shows up as missing, so a stale translation can never be shown.
- Search words: data/i18n/search.<lang>.json ({"stop": [...], "topics": {word: fact key}}).
- Country names: Unicode CLDR (data/i18n/cldr_<lang>_territories.json), never hand-written.

The long research text and the sources stay in English on every language (owner decision 2026-10-28).
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"

# code -> (name in its own language, text direction). English is the source and lives at the site root.
LANGS = {
    "en": ("English", "ltr"), "es": ("Español", "ltr"), "fr": ("Français", "ltr"), "pt": ("Português", "ltr"),
    "ar": ("العربية", "rtl"), "ur": ("اردو", "rtl"), "bn": ("বাংলা", "ltr"), "id": ("Bahasa Indonesia", "ltr"),
    "vi": ("Tiếng Việt", "ltr"),
}


def sid(text):
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_strings(lang):
    out = {}
    for path in sorted(I18N.glob(f"strings.{lang}*.tsv")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            key, _, text = line.partition("\t")
            if not re.fullmatch(r"[0-9a-f]{10}", key) or not text.strip():
                raise SystemExit(f"{path.name}:{n}: expected '<10-hex id>\\t<translation>'")
            out[key] = text.strip()
    return out


def country_names(lang):
    data = load_json(I18N / f"cldr_{lang}_territories.json")
    return data["main"][lang]["localeDisplayNames"]["territories"]


class Missing(Exception):
    pass


class Translator:
    """t(key, **kw) for interface text, text(english) for content lines. English is the identity."""

    def __init__(self, lang):
        self.lang = lang
        self.en_ui = {k: v for k, v in load_json(I18N / "ui.en.json").items() if not k.startswith("_")}
        self.ui_map = self.en_ui if lang == "en" else load_json(I18N / f"ui.{lang}.json")
        self.strings = {} if lang == "en" else load_strings(lang)
        self.missing = set()

    def t(self, key, **kw):
        if key not in self.ui_map:
            self.missing.add(f"ui:{key}")
            template = self.en_ui[key]
        else:
            template = self.ui_map[key]
        if LANGS.get(self.lang, ("", "ltr"))[1] == "rtl":
            # keep dates and numbers like 2026-10-25 in one left-to-right run, or the bidi algorithm flips them
            kw = {k: f"⁦{v}⁩" if re.fullmatch(r"[\d\-/.,: ]+", str(v)) else v for k, v in kw.items()}
        return template.format(**kw) if kw else template

    def text(self, english):
        if self.lang == "en" or not english:
            return english
        got = self.strings.get(sid(english))
        if got is None:
            self.missing.add(english)
            return english
        return got
