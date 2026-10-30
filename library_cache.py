"""Account-scoped, read-only Steam library snapshots.

Snapshots only accelerate the game list. Steam's live identity and per-game
checks remain authoritative for achievement reads and writes.
"""
import json
from pathlib import Path
import re

from library import Game
from workspace import atomic_json

CACHE_SCHEMA = 1
MAX_GAMES = 100_000
_ACCOUNT_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_ICON_HASH = re.compile(r"(?:[a-f0-9]{40})?\Z")


def cache_path(folder, account_id):
    """Reject unsafe account IDs before using them in a filesystem path."""
    if type(account_id) is not str or not _ACCOUNT_ID.fullmatch(account_id):
        raise ValueError("Invalid Steam account identifier for library cache.")
    return Path(folder) / "library-cache" / (account_id + ".json")


def _verified_games(records):
    if type(records) is not list or len(records) > MAX_GAMES:
        raise ValueError("Invalid cached Steam library.")
    ids = set()
    games = []
    for row in records:
        if type(row) is not dict or set(row) != {"app_id", "name", "installed", "icon_hash"}:
            raise ValueError("Invalid cached game metadata.")
        app_id, name = row["app_id"], row["name"]
        installed, icon_hash = row["installed"], row["icon_hash"]
        if (type(app_id) is not int or not 0 < app_id < 2**32 or app_id == 228980
                or app_id in ids or type(name) is not str or not name.strip()
                or len(name) > 1024 or type(installed) is not bool
                or type(icon_hash) is not str or not _ICON_HASH.fullmatch(icon_hash)):
            raise ValueError("Invalid cached game metadata.")
        ids.add(app_id)
        games.append(Game(app_id, name, installed, icon_hash))
    return games


def load_library_cache(folder, account_id):
    """Return None on missing, corrupt, or obsolete snapshots; [] is valid."""
    try:
        path = cache_path(folder, account_id)
        if path.stat().st_size > 24 * 1024 * 1024:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if (type(data) is not dict or data.get("schema") != CACHE_SCHEMA
                or data.get("account_id") != account_id):
            return None
        return _verified_games(data.get("games"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def save_library_cache(folder, account_id, games):
    """Persist only an entirely validated discovery, using an atomic replace."""
    records = []
    for game in games:
        if not isinstance(game, Game):
            raise ValueError("Invalid game record.")
        records.append(dict(app_id=game.app_id, name=game.name,
                            installed=game.installed, icon_hash=game.icon_hash))
    validated = _verified_games(records)
    path = cache_path(folder, account_id)
    atomic_json(path, dict(schema=CACHE_SCHEMA, account_id=account_id,
                           games=[dict(app_id=g.app_id, name=g.name,
                                       installed=g.installed, icon_hash=g.icon_hash)
                                  for g in validated]))
