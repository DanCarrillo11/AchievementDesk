"""Fetch and normalize public App IDs for the distributable catalog snapshot."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import CATALOG_URL, parse_xml
import urllib.request

root = Path(__file__).resolve().parents[1]
with urllib.request.urlopen(CATALOG_URL, timeout=20) as response:
    ids = parse_xml(response.read(8 * 1024 * 1024 + 1))
output = root / "assets" / "catalog.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(dict(schema=1, source=CATALOG_URL,
    retrieved_utc=datetime.now(timezone.utc).isoformat(), app_ids=ids), separators=(",", ":")), encoding="utf-8")
print(f"Bundled {len(ids)} public App IDs. No account information was queried.")
