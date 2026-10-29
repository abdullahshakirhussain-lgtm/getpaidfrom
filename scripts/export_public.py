"""Copy the public parts of this project into the public repo checkout (default ../getpaidfrom).

    python scripts/export_public.py [TARGET_DIR]

Only the paths in INCLUDE are copied. Raw page snapshots (copies of third-party pages), logs, the playbook and
the business plan stay private. The target's own .git folder is left alone; everything else in it is replaced.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = [
    ".github/workflows/pages.yml", ".gitignore", "README.md", "requirements.txt", "wrangler.toml",
    "data/countries", "data/countries.json", "data/research", "data/sources", "data/reference", "data/manual",
    "data/mapping_audit.json", "data/display", "docs/RESEARCH_PROTOCOL.md", "docs/BLUEPRINT.md", "docs/DESIGN.md",
    "docs/TRANSLATION.md", "data/i18n",
    "scripts", "site/templates", "site/static", "site/logos", "site/indexnow-key.txt", "worker", "tests",
]
SKIP = {"__pycache__", "dist"}


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "getpaidfrom"
    target.mkdir(parents=True, exist_ok=True)
    for item in target.iterdir():
        if item.name != ".git":
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    files = 0
    for rel in INCLUDE:
        src = ROOT / rel
        if src.is_dir():
            for f in src.rglob("*"):
                if f.is_file() and not SKIP & set(f.relative_to(ROOT).parts) and not f.name.startswith("todo."):
                    dst = target / f.relative_to(ROOT)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                    files += 1
        else:
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / rel)
            files += 1
    print(f"exported {files} files to {target}")


if __name__ == "__main__":
    main()
