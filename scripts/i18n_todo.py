"""List the English lines a language still needs, for translators.

  python scripts/i18n_todo.py es            -> data/i18n/todo.es.tsv  ("<id>\t<English>", only the missing ones)
  python scripts/i18n_todo.py es --all      -> every line, translated or not

Translations go in data/i18n/strings.es.tsv as "<id>\t<Spanish>". Then run scripts/i18n_check.py es.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import load_views, localize, ways_line  # noqa: E402
from i18n import I18N, Translator, country_names, sid  # noqa: E402


def english_lines(views):
    """Every content line the site would translate, in first-seen order."""
    class Recorder(Translator):
        def __init__(self):
            super().__init__("en")
            self.lang, self.seen = "xx", {}

        def text(self, english):
            if english:
                self.seen.setdefault(sid(english), english.strip())
            return english

        def t(self, key, **kw):
            return super().t(key, **kw)

    rec = Recorder()
    names = {v["code"]: v["name"] for v in views}
    for v in views:
        ways_line(localize(v, rec, names), rec)
    return rec.seen


def main():
    lang = sys.argv[1]
    lines = english_lines(load_views())
    (I18N / "source.tsv").write_text("".join(f"{k}\t{v}\n" for k, v in lines.items()), encoding="utf-8")  # what i18n_check reads
    have = Translator(lang).strings if (I18N / f"ui.{lang}.json").exists() else {}
    todo = lines if "--all" in sys.argv else {k: v for k, v in lines.items() if k not in have}
    out = I18N / f"todo.{lang}.tsv"
    out.write_text("".join(f"{k}\t{v}\n" for k, v in todo.items()), encoding="utf-8")
    print(f"{lang}: {len(lines)} lines, {len(lines) - len(todo) if '--all' not in sys.argv else len(have)} translated, "
          f"{len(todo)} written to {out.relative_to(I18N.parent.parent)} ({sum(len(v) for v in todo.values())} characters)")


if __name__ == "__main__":
    main()
