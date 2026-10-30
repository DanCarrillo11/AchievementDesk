"""Read Steam's published set definitions and reported completion, without cookies.

Never infers a persistent Steam trophy from the current achievement percentage.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
from datetime import datetime, timezone


def steam_queries(text):
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inside, self.parts = False, []

        def handle_starttag(self, tag, attrs):
            if tag == "script":
                self.inside = dict(attrs).get("id") == "valve-ssr-data"

        def handle_endtag(self, tag):
            if tag == "script":
                self.inside = False

        def handle_data(self, text):
            if self.inside:
                self.parts.append(text)
    parser = Parser()
    parser.feed(text)
    if not parser.parts:
        raise ValueError("Steam did not expose achievement-set data on this page.")
    payload = json.loads("".join(parser.parts))
    found = []

    def walk(value, depth=0):
        if depth > 24:
            return
        if isinstance(value, dict):
            if "queryKey" in value and value.get("state", {}).get("status") == "success":
                found.append((value["queryKey"], value["state"].get("data")))
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)
        elif isinstance(value, str) and value.startswith(("{", "[")):
            try:
                walk(json.loads(value), depth + 1)
            except ValueError:
                pass
    walk(payload)
    return found


def parse_completion(text, app_id, account_id=None):
    schema, user = None, None
    for key, data in steam_queries(text):
        if not isinstance(key, list) or key[:2] != ["achievements", app_id] or not isinstance(data, dict):
            continue
        if key[2:3] == ["schema_v2"] and data.get("appid") == app_id:
            schema = data
        if (account_id is not None and key[2:] == ["user_achievements", str(account_id)]
                and str(data.get("steamid")) == str(account_id) and data.get("appid") == app_id):
            user = data
    if schema is None or not isinstance(schema.get("groups"), list):
        raise ValueError("Steam's achievement-set format is unavailable or has changed.")
    if user and (schema.get("schema_hash") is None or user.get("schema_hash") != schema.get("schema_hash")):
        user = None  # Never associate completion from a different set definition.
    raw_user_groups = user.get("groups", {}) if user else {}
    if isinstance(raw_user_groups, list):
        raw_user_groups = {str(g.get("groupid")): g for g in raw_user_groups if isinstance(g, dict)}
    if not isinstance(raw_user_groups, dict):
        raw_user_groups = {}
    groups, known_ids, known_keys = [], set(), set()
    for raw in schema["groups"][:40]:
        if not isinstance(raw, dict) or type(raw.get("id")) is not int or raw["id"] in known_ids:
            raise ValueError("Invalid or duplicate achievement-set identifier.")
        if raw.get("developeronly") is True or raw.get("ispublic") is not True:
            continue
        known_ids.add(raw["id"])
        entries = []
        for achievement in raw.get("achievements", []):
            key = achievement.get("api_name") if isinstance(achievement, dict) else None
            if not isinstance(key, str) or not key or len(key) > 256 or key in known_keys:
                raise ValueError("Invalid or duplicate achievement in Steam's set definitions.")
            known_keys.add(key)
            entries.append(dict(key=key, archived=achievement.get("archived") is True))
        flags = raw_user_groups.get(str(raw["id"]), {})
        if not isinstance(flags, dict) or flags.get("groupid") != raw["id"]:
            flags = {}
        completed = flags.get("is_completed")
        achievable = flags.get("is_achievable")
        groups.append(dict(id=raw["id"], name=str(raw.get("name") or "Base game achievements")[:200],
            dlc_app_id=raw.get("dlcappid", 0), archived=raw.get("archived") is True,
            achievements=entries, completed=completed if type(completed) is bool else None,
            achievable=achievable if type(achievable) is bool else None,
            time_completed=flags.get("time_completed", 0) if type(flags.get("time_completed", 0)) is int else 0))
    result = dict(app_id=app_id, groups=groups, schema_hash=schema.get("schema_hash"),
                  checked_utc=datetime.now(timezone.utc).isoformat(), reported=bool(user))
    if any(g["completed"] is None for g in groups):
        result["notice"] = "Some completion states were not reported by Steam. Unconfirmed does not mean the trophy has not been earned."
    return result


def unlock_restriction(data, key):
    """Only definite restrictions; absence of data never means incompatibility."""
    for group in data.get("groups", []):
        entry = next((a for a in group["achievements"] if a["key"] == key), None)
        if entry is None:
            continue
        if group["archived"] or entry["archived"]:
            return "Archived by the developer"
        if group["achievable"] is False:
            return "Steam reports this set cannot be earned by this account"
        if group["dlc_app_id"] and group["achievable"] is not True:
            return "Steam has not confirmed access to the required DLC"
    return ""


def set_progress(group, rows):
    current = {row.key: row for row in rows}
    required = [a["key"] for a in group["achievements"] if not a["archived"]]
    return sum(bool(current.get(key) and current[key].unlocked) for key in required), len(required), sum(key not in current for key in required)


def read_completion(app_id, account_id, fetch):
    """Only app/account identifiers go to Steam. No credential or cookie access."""
    if type(app_id) is not int or not 0 < app_id < 2**32 or not str(account_id).isdigit() or len(str(account_id)) != 17:
        raise ValueError("Invalid Steam game or account identifier.")
    try:
        text = fetch(f"https://steamcommunity.com/profiles/{account_id}/stats/{app_id}/achievements/?l=english").decode("utf-8")
        return parse_completion(text, app_id, account_id)
    except Exception:
        # Private/unavailable profiles may still have public set definitions.
        text = fetch(f"https://steamcommunity.com/stats/{app_id}/achievements/?l=english").decode("utf-8")
        value = parse_completion(text, app_id)
        value["notice"] = "Steam did not expose account completion. Your profile or game details may be private."
        return value


class CompletionService:
    def __init__(self, post):
        self.post, self.closed = post, False
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="completion")

    def load(self, app_id, account_id, done):
        def job():
            from media import fetch
            try:
                value = read_completion(app_id, account_id, fetch)
            except Exception:
                value = dict(app_id=app_id, groups=[], error="Steam completion is unavailable. Retry later; no trophy status was assumed.")
            if not self.closed:
                self.post(lambda: done(value))
        if not self.closed:
            self.pool.submit(job)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
