"""Find (or create once) the KV namespaces for email-alert sign-ups and paid packs, and write their ids into wrangler.toml.

    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python scripts/ensure_kv.py

Run in CI before `wrangler deploy` (see .github/workflows/pages.yml). Idempotent: the same namespace is reused on
every deploy, so nothing is lost to a fresh namespace.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACES = {"SIGNUPS_KV_ID": "getpaidfrom-signups", "PACKS_KV_ID": "getpaidfrom-packs"}
WRANGLER = ["npx", "--yes", "wrangler@4"]


def run(*args):
    out = subprocess.run(WRANGLER + list(args), capture_output=True, text=True, cwd=ROOT, shell=sys.platform == "win32")
    if out.returncode:
        sys.exit(f"wrangler {' '.join(args)} failed:\n{out.stdout}\n{out.stderr}")
    return out.stdout


def namespaces():
    text = run("kv", "namespace", "list")
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        sys.exit(f"Unexpected `kv namespace list` output:\n{text}")
    return json.loads(text[start:end + 1])


def find(items, title):
    return next((n["id"] for n in items if n.get("title") == title or n.get("title", "").endswith(title)), None)


def main():
    cfg = ROOT / "wrangler.toml"
    text = cfg.read_text(encoding="utf-8")
    for placeholder, title in NAMESPACES.items():
        ns_id = find(namespaces(), title)
        if not ns_id:
            run("kv", "namespace", "create", title)
            ns_id = find(namespaces(), title)
        if not ns_id or not re.fullmatch(r"[0-9a-f]{32}", ns_id):
            sys.exit(f"Could not find or create the {title} KV namespace.")
        text = text.replace(f'id = "{placeholder}"', f'id = "{ns_id}"')
        print(f"{title} KV namespace: {ns_id}")
    cfg.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
