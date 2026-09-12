"""Download pinned rule documents into data/rules/ and verify them against the manifest.

    python -m scripts.fetch_rules

Fails loudly if the utility has replaced the document at its URL: a new tariff
edition is a deliberate change (new manifest entry, re-verified citations),
never a silent one.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "backend/app/domains/interconnection/rules/manifest.json"
DEST = ROOT / "data/rules"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    ok = True
    for key, entry in json.loads(MANIFEST.read_text()).items():
        path = DEST / f"{key}.pdf"
        if not path.exists():
            print(f"downloading {key} ...")
            req = urllib.request.Request(entry["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                path.write_bytes(resp.read())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            print(f"MISMATCH {key}: expected {entry['sha256']}, got {digest} — the published edition changed")
            ok = False
        else:
            print(f"ok {key} ({entry['effective']}, advice {entry['advice_letter']})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
