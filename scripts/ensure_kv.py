"""Find (or create once) the KV namespace that stores email-alert sign-ups, and write its id into wrangler.toml.

    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python scripts/ensure_kv.py

Run in CI before `wrangler deploy` (see .github/workflows/pages.yml). Idempotent: the same namespace is reused on
every deploy, so sign-ups are never lost to a fresh namespace.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "getpaidfrom-signups"
WRANGLER = ["npx", "--yes", "wrangler@4"]


def run(*args):
    out = subprocess.run(WRANGLER + list(args), capture_output=True, text=True, cwd=ROOT)
    if out.returncode:
        sys.exit(f"wrangler {' '.join(args)} failed:\n{out.stdout}\n{out.stderr}")
    return out.stdout


def namespaces():
    text = run("kv", "namespace", "list")
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        sys.exit(f"Unexpected `kv namespace list` output:\n{text}")
    return json.loads(text[start:end + 1])


def find(items):
    return next((n["id"] for n in items if n.get("title") == TITLE or n.get("title", "").endswith(TITLE)), None)


def main():
    ns_id = find(namespaces())
    if not ns_id:
        run("kv", "namespace", "create", TITLE)
        ns_id = find(namespaces())
    if not ns_id or not re.fullmatch(r"[0-9a-f]{32}", ns_id):
        sys.exit("Could not find or create the sign-ups KV namespace.")
    cfg = ROOT / "wrangler.toml"
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(re.sub(r'id = "SIGNUPS_KV_ID"', f'id = "{ns_id}"', text), encoding="utf-8")
    print(f"sign-ups KV namespace: {ns_id}")


if __name__ == "__main__":
    main()
