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


def parse_icons(text, app_id=None):
    """Read exact API-name/image pairs without depending on JSON field order."""
    from completion import steam_queries
    result = {}
    def add(row):
        if not isinstance(row, dict):
            return
        key = row.get("api_name")
        if not isinstance(key, str) or not 0 < len(key) <= 256:
            return
        icons = {}
        for variant, field in (("unlocked", "icon_achieved"), ("locked", "icon_unachieved")):
            name = row.get(field)
            if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,122}\.(?:jpg|jpeg|png)", name, re.I):
                icons[variant] = name
        if icons:
            result[key] = icons
    try:
        queries = steam_queries(text)
    except (ValueError, TypeError):
        queries = []
    for key, schema in queries:
        if (not isinstance(key, list) or key[:1] != ["achievements"] or key[2:3] != ["schema_v2"]
                or not isinstance(schema, dict) or schema.get("appid") != key[1]
                or app_id is not None and schema.get("appid") != app_id):
            continue
        for group in schema.get("groups", []) if isinstance(schema.get("groups"), list) else []:
            if isinstance(group, dict) and isinstance(group.get("achievements"), list):
                for row in group["achievements"][:10000]:
                    add(row)
    if queries or 'id="valve-ssr-data"' in text or "id='valve-ssr-data'" in text:
        return result  # Never fall back to data from a different game's SSR schema.
    # Older public pages may embed plain or once-escaped JSON objects.
    # Decode each object separately so a missing icon cannot borrow the next row's.
    for raw in re.findall(r"\{[^{}]{1,20000}\}", text):
        if "api_name" not in raw:
            continue
        try:
            decoded = json.loads(raw)
        except (ValueError, TypeError):
            try:
                decoded = json.loads(json.loads('"' + raw + '"'))
            except (ValueError, TypeError):
                continue
        add(decoded)
    return result


def valid_metadata(value):
    if (not isinstance(value, dict) or value.get("format") != 2
            or not isinstance(value.get("icons"), dict) or not isinstance(value.get("percentages"), dict)
            or not isinstance(value.get("warnings", []), list)):
        return False
    for key, variants in value["icons"].items():
        if not isinstance(key, str) or not isinstance(variants, dict):
            return False
        for variant, name in variants.items():
            if (variant not in ("locked", "unlocked") or not isinstance(name, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,122}\.(?:jpg|jpeg|png)", name, re.I)):
                return False
    return all(isinstance(k, str) and type(v) in (int, float) and 0 <= v <= 100
               for k, v in value["percentages"].items())


def valid_image(data):
    """Reject error pages, corrupt downloads and unexpectedly large image sizes."""
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtGui import QImageReader
    if not (data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG')):
        return False
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    return 0 < size.width() <= 2048 and 0 < size.height() <= 2048 and not reader.read().isNull()


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
        self.pending, self.failed = {}, {}
        self.lock = threading.Lock()
        self.closed = False
        self.steam_cache = None
        self.checked_steam_cache = False
        self.icon_lookup_lock = threading.Lock()
        self.icon_backoff_until = 0

    def submit(self, key, job, done):
        if not self.enabled or self.closed:
            if not self.closed:
                self.post(lambda: done(None))
            return
        with self.lock:
            cooling = time.monotonic() < self.failed.get(key, 0)
            if not cooling and key in self.pending:
                self.pending[key].append(done)
                return
            if not cooling:
                self.pending[key] = [done]
        if cooling:
            self.post(lambda: done(None))
            return
        def run():
            try:
                value = job()
            except Exception:
                with self.lock:
                    self.failed[key] = time.monotonic() + 60
                value = None
            with self.lock:
                callbacks = self.pending.pop(key, [])
            if not self.closed:
                for callback in callbacks:
                    self.post(lambda callback=callback: callback(value))
        self.pool.submit(run)

    def image_path(self, url):
        return self.folder / "images" / (hashlib.sha256(url.encode()).hexdigest() + ".img")

    def image(self, url, done):
        if not self.enabled or self.closed:
            if not self.closed:
                self.post(lambda: done(None))
            return
        if urlparse(url).hostname not in ("cdn.akamai.steamstatic.com", "shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com"):
            return
        path = self.image_path(url)
        try:
            if path.is_file():
                if path.stat().st_size <= 5_000_000 and valid_image(path.read_bytes()):
                    done(path)
                    return
                path.unlink()
        except OSError:
            pass
        def job():
            data = fetch(url)
            if not valid_image(data):
                raise ValueError("Steam artwork was not a valid, reasonably sized JPEG or PNG.")
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
        self.submit(f"game-icon:{app_id}", job, lambda url: self.image(url, done) if url else done(None))

    def metadata(self, app_id, done, force=False):
        if app_id <= 0:
            return
        path = self.folder / f"schema-{app_id}.json"
        def job():
            cached = None
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
                if valid_metadata(candidate):
                    cached = candidate
                    lifetime = 60 if cached.get("warnings") else 86400
                    if not force and time.time() - path.stat().st_mtime < lifetime:
                        return cached
            except (OSError, ValueError):
                pass
            value = dict(format=2, icons={}, percentages={}, warnings=[])
            try:
                value["icons"] = parse_icons(fetch(f"https://steamcommunity.com/stats/{app_id}/achievements/?l=english").decode("utf-8"), app_id)
                if not value["icons"]:
                    raise ValueError("Steam did not expose achievement images.")
            except Exception:
                value["icons"] = cached.get("icons", {}) if cached else {}
                value["warnings"].append("Some achievement images are unavailable from Steam.")
            try:
                value["percentages"] = percentages(json.loads(fetch(f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={app_id}")))
            except Exception:
                value["percentages"] = cached.get("percentages", {}) if cached else {}
                value["warnings"].append("Global achievement rarity is unavailable from Steam.")
            atomic_json(path, value)
            return value
        self.submit(f"metadata:{app_id}", job, done)

    def achievement_icon(self, app_id, filename, done):
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", filename):
            self.image(f"{CDN}/steamcommunity/public/images/apps/{int(app_id)}/{filename}", done)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
