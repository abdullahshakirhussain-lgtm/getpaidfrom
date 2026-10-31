"""Upload paid Country Packs to Cloudflare KV, where only the Worker can read them.

    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python scripts/upload_packs.py          # every pack with a product id
    python scripts/upload_packs.py PK --dry-run                                                # show what would go up

Pack text is in playbook/packs/<CODE>.html, which is private and never exported to the public repo. A pack goes up only
once data/packs.json has its Gumroad product_id. The namespace is the one scripts/ensure_kv.py creates on deploy.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from ensure_kv import find, namespaces  # noqa: E402

TITLE = "getpaidfrom-packs"
WRANGLER = ["npx", "--yes", "wrangler@4"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    packs = json.loads((ROOT / "data" / "packs.json").read_text(encoding="utf-8"))
    ns_id = None if dry else find(namespaces(), TITLE)
    if not dry and not ns_id:
        sys.exit(f"No {TITLE} namespace yet: deploy once so scripts/ensure_kv.py creates it.")
    for code in args or packs:
        source = ROOT / "playbook" / "packs" / f"{code}.html"
        product = packs.get(code, {}).get("product_id")
        if not source.exists() or not product:
            print(f"{code}: skipped ({'no pack text' if not source.exists() else 'no product_id in data/packs.json'})")
            continue
        value = {"product_id": product, "updated": packs[code]["updated"], "html": source.read_text(encoding="utf-8")}
        if dry:
            print(f"{code}: would upload {len(value['html']) // 1024} KB")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack.json"
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            done = subprocess.run(WRANGLER + ["kv", "key", "put", f"pack:{code}", "--path", str(path), "--namespace-id", ns_id, "--remote"],
                                  capture_output=True, text=True, cwd=ROOT, shell=sys.platform == "win32")
        if done.returncode:
            sys.exit(f"{code}: upload failed:\n{done.stdout}\n{done.stderr}")
        print(f"{code}: uploaded {len(value['html']) // 1024} KB")


if __name__ == "__main__":
    main()
