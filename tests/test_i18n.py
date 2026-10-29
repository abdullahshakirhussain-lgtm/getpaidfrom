"""Check every translation against the current English (numbers, codes, names, negation, placeholders).

    python tests/test_i18n.py

Fails on any accuracy problem in an existing translation. Lines that are simply missing (the English changed)
only print a warning: the build leaves that language out until it is complete, and the warning says so.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from i18n import I18N, LANGS  # noqa: E402
from i18n_todo import english_lines, load_views  # noqa: E402


def main():
    lines = english_lines(load_views())
    (I18N / "source.tsv").write_text("".join(f"{k}\t{v}\n" for k, v in lines.items()), encoding="utf-8")
    failed = []
    for lang in LANGS:
        if lang == "en" or not (I18N / f"ui.{lang}.json").exists():
            continue
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "i18n_check.py"), lang],
                           capture_output=True, text=True, encoding="utf-8")
        problems = [p for p in r.stdout.splitlines() if p and not p.startswith(" ") and ": not translated:" not in p
                    and not p.startswith(f"{lang}: ")]
        missing = sum(": not translated:" in p for p in r.stdout.splitlines())
        print(r.stdout.splitlines()[-1] if r.stdout else f"{lang}: no output")
        if missing:
            print(f"  warning: {lang} has {missing} untranslated lines and will be left out of the build")
        if problems:
            failed.append(lang)
            print("\n".join(r.stdout.splitlines()[:40]))
    if failed:
        sys.exit(f"translation problems in: {', '.join(failed)}")
    print("OK")


if __name__ == "__main__":
    main()
