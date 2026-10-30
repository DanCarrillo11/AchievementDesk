"""Local preferences and per-account activity. No Steam or Qt dependency."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

VERSION = "0.8.0-preview"
DEFAULTS = dict(reveal_hidden=False, compact=False, reduce_motion=False, online_art=True,
                achievement_sort="Steam order", library_filter="All games", width=1280, height=900,
                release_repository="", online_completion=True)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Workspace:
    def __init__(self, folder):
        self.folder = Path(folder)
        try:
            data = json.loads((self.folder / "workspace.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        self.settings = dict(DEFAULTS)
        for key, default in DEFAULTS.items():
            value = data.get("settings", {}).get(key, default) if isinstance(data.get("settings"), dict) else default
            if type(value) is type(default):
                self.settings[key] = value
        self.settings["width"] = min(3000, max(1020, self.settings["width"]))
        self.settings["height"] = min(2000, max(760, self.settings["height"]))
        self.accounts = data.get("accounts", {}) if isinstance(data.get("accounts"), dict) else {}

    def save(self):
        atomic_json(self.folder / "workspace.json", dict(schema=1, settings=self.settings, accounts=self.accounts))

    def profile(self, account):
        key = str(account or "disconnected")
        profile = self.accounts.get(key)
        if not isinstance(profile, dict):
            profile = {}
            self.accounts[key] = profile
        for name in ("favorites", "recent"):
            values = profile.get(name, [])
            profile[name] = list(dict.fromkeys(x for x in values if type(x) is int and 0 <= x < 2**32)) if isinstance(values, list) else []
        return profile

    def favorite(self, account, app_id):
        profile = self.profile(account)
        values = profile["favorites"]
        values.remove(app_id) if app_id in values else values.append(app_id)
        self.save()
        return app_id in values

    def compatibility(self, account, app_id):
        values = self.profile(account).get("compatibility", {})
        value = values.get(str(app_id), {}) if isinstance(values, dict) else {}
        return value if isinstance(value, dict) else {}

    def save_compatibility(self, account, app_id, evidence):
        profile = self.profile(account)
        if not isinstance(profile.get("compatibility"), dict):
            profile["compatibility"] = {}
        profile["compatibility"][str(app_id)] = evidence
        self.save()

    def visit(self, account, app_id):
        profile = self.profile(account)
        profile["recent"] = [app_id] + [x for x in profile["recent"] if x != app_id][:29]
        profile["last_game"] = app_id
        self.save()

    def history_path(self, account):
        account = str(account)
        if not account or len(account) > 32 or not account.isalnum():
            raise ValueError("Invalid account identifier.")
        return self.folder / "history" / (account + ".json")

    def history(self, account):
        if not account:
            return []
        try:
            result = json.loads(self.history_path(account).read_text(encoding="utf-8"))
            return [x for x in result if isinstance(x, dict)][:1000] if isinstance(result, list) else []
        except (OSError, ValueError):
            return []

    def start_activity(self, account, game, changes):
        entry = dict(id=uuid.uuid4().hex, created_utc=datetime.now(timezone.utc).isoformat(),
                     app_id=game.app_id, game=game.name, status="unconfirmed", changes=changes,
                     message="Started. A confirmed result has not been recorded.")
        atomic_json(self.history_path(account), [entry] + self.history(account)[:999])
        return entry["id"]

    def finish_activity(self, account, activity_id, result):
        entries = self.history(account)
        for entry in entries:
            if entry.get("id") == activity_id:
                entry.update({key: result[key] for key in ("status", "confirmed", "rejected", "unconfirmed", "snapshot", "message") if key in result})
                break
        atomic_json(self.history_path(account), entries)


def order_achievements(records, mode):
    if mode == "Name A–Z":
        return sorted(records, key=lambda x: x["name"].casefold())
    if mode == "Name Z–A":
        return sorted(records, key=lambda x: x["name"].casefold(), reverse=True)
    if mode in ("Newest unlocks", "Oldest unlocks"):
        return sorted(records, key=lambda x: (not bool(x.get("unlock_time")),
            -x.get("unlock_time", 0) if mode == "Newest unlocks" else x.get("unlock_time", 0)))
    if mode in ("Rarest first", "Most common first"):
        return sorted(records, key=lambda x: (x.get("rarity") is None,
            (x.get("rarity") or 0) * (-1 if mode == "Most common first" else 1)))
    return records
