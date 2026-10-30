"""Shared public App IDs, never an account-specific list or authentication data."""
import json
import os
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET

CATALOG_URL = "https://gib.me/sam/games.xml"
MAX_BYTES = 8 * 1024 * 1024
MAX_APPS = 250000


def parse_xml(data):
    if len(data) > MAX_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("The game catalog is too large or contains unsupported declarations.")
    root = ET.fromstring(data)
    if root.tag != "games":
        raise ValueError("Unrecognized game catalog format.")
    ids = set()
    for node in root.findall("game"):
        if node.get("type") == "junk":
            continue
        text = (node.text or "").strip()
        if not text.isdecimal():
            raise ValueError("The game catalog contains an invalid App ID.")
        value = int(text)
        if not 0 < value < 2**32:
            raise ValueError("The game catalog contains an out-of-range App ID.")
        ids.add(value)
        if len(ids) > MAX_APPS:
            raise ValueError("Unexpected game catalog size.")
    if not ids:
        raise ValueError("The game catalog is empty.")
    return sorted(ids)


def read_catalog(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Game catalog is too large.")
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = data.get("app_ids") if isinstance(data, dict) else None
    if not isinstance(ids, list) or not ids or len(ids) > MAX_APPS:
        raise ValueError("Invalid game catalog.")
    if any(type(value) is not int or not 0 < value < 2**32 for value in ids):
        raise ValueError("Invalid App ID in game catalog.")
    return sorted(set(ids))


def catalog_ids(cache_dir):
    """Use the latest explicitly downloaded catalog, falling back to the bundle."""
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets" / "catalog.json"
    cached = Path(cache_dir) / "catalog.json"
    for path in (cached, bundled):
        try:
            return read_catalog(path)
        except (OSError, ValueError, UnicodeError):
            continue
    raise RuntimeError("No valid game catalog found. Extract the complete application or update the catalog.")


def update_catalog(cache_dir):
    """Explicit catalog update; sends no account ID or library to the public host."""
    request = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "AchievementDesk/0.2.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.geturl() != CATALOG_URL:
            raise ValueError("The catalog host redirected unexpectedly; the existing catalog was kept.")
        ids = parse_xml(response.read(MAX_BYTES + 1))
    folder = Path(cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "catalog.new"
    # Content is public IDs only. Replace only after full parsing and validation.
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(dict(schema=1, source=CATALOG_URL, app_ids=ids), stream, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, folder / "catalog.json")
    return len(ids)
