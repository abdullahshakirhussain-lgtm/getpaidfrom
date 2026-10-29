"""Add numbered translations to data/i18n/strings.<lang>.tsv.

  python scripts/i18n_put.py es batch.txt

batch.txt has one "N: translation" per line, where N is the line number in data/i18n/source.tsv (which
scripts/i18n_todo.py writes). Lines already translated are replaced. Run scripts/i18n_check.py afterwards.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import I18N  # noqa: E402


def main():
    lang, batch = sys.argv[1], Path(sys.argv[2])
    sys.stdout.reconfigure(encoding="utf-8")
    source = [line.split("\t", 1) for line in (I18N / "source.tsv").read_text(encoding="utf-8").splitlines()]
    out = I18N / f"strings.{lang}.tsv"
    have = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                k, _, v = line.partition("\t")
                have[k] = v
    n_new = 0
    for raw in batch.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        m = re.fullmatch(r"(\d+): (.+)", raw.strip())
        if not m or not 1 <= int(m.group(1)) <= len(source):
            sys.exit(f"bad line: {raw[:80]}")
        k = source[int(m.group(1)) - 1][0]
        n_new += k not in have
        have[k] = m.group(2).strip()
    order = {k: i for i, (k, _) in enumerate(source)}
    out.write_text("".join(f"{k}\t{v}\n" for k, v in sorted(have.items(), key=lambda kv: order.get(kv[0], 10**9))), encoding="utf-8")
    print(f"{lang}: +{n_new} new, {len(have)}/{len(source)} translated")


if __name__ == "__main__":
    main()
