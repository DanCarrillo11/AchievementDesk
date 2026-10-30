"""Optional public Steam presentation data. Never reads accounts or writes stats."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
from workspace import atomic_json

CDN = "https://cdn.akamai.steamstatic.com"


def is_game_icon_url(url, app_id):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname in ("cdn.akamai.steamstatic.com", "shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com")
            and bool(re.fullmatch(r"/(?:community_assets|steamcommunity/public)/images/apps/" + str(int(app_id)) + r"/[a-fA-F0-9]{40}\.(?:jpg|png)", parsed.path)))


def parse_game_icon(text, app_id):
    class IconParser(HTMLParser):
        inside = False
        url = ""

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "div" and "apphub_AppIcon" in attributes.get("class", "").split():
                self.inside = True
            if tag == "img" and self.inside:
                candidate = attributes.get("src", "")
                if is_game_icon_url(candidate, app_id):
                    self.url = candidate

        def handle_endtag(self, tag):
            if tag == "div":
                self.inside = False
    parser = IconParser()
    parser.feed(text)
    return parser.url


def fetch(url, limit=5_000_000):
    request = Request(url, headers={"User-Agent": "AchievementDesk/0.8 (+Steam achievement metadata)"})
    with urlopen(request, timeout=8) as reply:
        data = reply.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Public metadata exceeded the size limit.")
        return data


def parse_icons(text):
    # Steam Community's server-rendered page embeds an escaped JSON schema.
    # Only API names and validated image filenames are used; descriptions stay native.
    result = {}
    pattern = r'\\"api_name\\":\\"([^"\\]+)\\".{0,6000}?\\"icon_achieved\\":\\"([A-Za-z0-9_.-]+)\\".{0,300}?\\"icon_unachieved\\":\\"([A-Za-z0-9_.-]+)\\"'
    for key, unlocked, locked in re.findall(pattern, text, re.S):
        if len(key) <= 256 and len(unlocked) <= 128 and len(locked) <= 128:
            result[key] = dict(unlocked=unlocked, locked=locked)
    return result


def percentages(payload):
    result = {}
    for row in payload.get("achievementpercentages", {}).get("achievements", []):
        try:
            value = float(row["percent"])
            if 0 <= value <= 100 and isinstance(row["name"], str):
                result[row["name"]] = value
        except (KeyError, TypeError, ValueError):
            continue
    return result


class Media:
    def __init__(self, folder, post, enabled=True):
        self.folder, self.post, self.enabled = Path(folder), post, enabled
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="artwork")
        self.pending, self.failed = {}, set()
        self.lock = threading.Lock()
        self.closed = False
        self.steam_cache = None
        self.checked_steam_cache = False
        self.icon_lookup_lock = threading.Lock()
        self.icon_backoff_until = 0

    def submit(self, key, job, done):
        if not self.enabled or self.closed:
            return
        with self.lock:
            if key in self.failed:
                return
            if key in self.pending:
                self.pending[key].append(done)
                return
            self.pending[key] = [done]
        def run():
            try:
                value = job()
            except Exception:
                with self.lock:
                    self.failed.add(key)
            else:
                with self.lock:
                    callbacks = self.pending.pop(key, [])
                if not self.closed:
                    for callback in callbacks:
                        self.post(lambda callback=callback: callback(value))
            if key in self.failed:
                with self.lock:
                    self.pending.pop(key, None)
        self.pool.submit(run)

    def image_path(self, url):
        return self.folder / "images" / (hashlib.sha256(url.encode()).hexdigest() + ".img")

    def image(self, url, done):
        if urlparse(url).hostname not in ("cdn.akamai.steamstatic.com", "shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com"):
            return
        path = self.image_path(url)
        if path.is_file():
            done(path)
            return
        def job():
            data = fetch(url)
            if not (data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG')):
                raise ValueError("Steam artwork was not a JPEG or PNG.")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
            return path
        self.submit(url, job, done)

    def game_icon(self, app_id, done, icon_hash=""):
        """Resolve Steam's small app-list icon, never a crop of store cover art."""
        if app_id <= 0:
            return
        if re.fullmatch(r"[a-fA-F0-9]{40}", icon_hash):
            icon_hash = icon_hash.lower()
            if not self.checked_steam_cache:
                try:
                    from library import steam_path
                    self.steam_cache = steam_path() / "appcache" / "librarycache"
                except (OSError, RuntimeError, ImportError):
                    pass
                self.checked_steam_cache = True
            if self.steam_cache:
                local = self.steam_cache / str(app_id) / (icon_hash + ".jpg")
                if local.is_file():
                    done(local)
                    return
            self.image(f"{CDN}/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg", done)
            return
        path = self.folder / f"game-icon-{app_id}.json"
        def job():
            cached = ""
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                candidate = value.get("url", "") if isinstance(value, dict) else ""
                if is_game_icon_url(candidate, app_id):
                    cached = candidate
                    if time.time() - path.stat().st_mtime < 7 * 86400:
                        return cached
            except (OSError, ValueError, TypeError):
                pass
            try:
                # Native icon hashes avoid this fallback for normal library scans.
                # Serialize fallback hub lookups and back off rather than retrying a 429.
                with self.icon_lookup_lock:
                    if self.closed or time.monotonic() < self.icon_backoff_until:
                        raise ValueError("Steam icon lookups are temporarily unavailable.")
                    try:
                        text = fetch(f"https://steamcommunity.com/app/{app_id}?l=english").decode("utf-8")
                    except HTTPError as error:
                        if error.code == 429:
                            self.icon_backoff_until = time.monotonic() + 120
                        raise
                url = parse_game_icon(text, app_id)
                if not url:
                    raise ValueError("Steam did not provide a small game icon.")
                atomic_json(path, dict(url=url))
                return url
            except Exception:
                if cached:
                    return cached
                raise
        self.submit(f"game-icon:{app_id}", job, lambda url: self.image(url, done))

    def metadata(self, app_id, done, force=False):
        if app_id <= 0:
            return
        path = self.folder / f"schema-{app_id}.json"
        def job():
            try:
                if not force and time.time() - path.stat().st_mtime < 86400:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(cached, dict) and isinstance(cached.get("icons"), dict) and isinstance(cached.get("percentages"), dict):
                        return cached
            except (OSError, ValueError):
                pass
            value = dict(icons={}, percentages={})
            try:
                value["icons"] = parse_icons(fetch(f"https://steamcommunity.com/stats/{app_id}/achievements/?l=english").decode("utf-8"))
            except Exception:
                pass
            try:
                value["percentages"] = percentages(json.loads(fetch(f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={app_id}")))
            except Exception:
                pass
            atomic_json(path, value)
            return value
        self.submit(f"metadata:{app_id}", job, done)

    def achievement_icon(self, app_id, filename, done):
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", filename):
            self.image(f"{CDN}/steamcommunity/public/images/apps/{int(app_id)}/{filename}", done)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
