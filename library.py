"""Read installed-game manifests; never reads Steam passwords or login tokens."""
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Game:
    app_id: int
    name: str
    installed: bool = False
    icon_hash: str = ""


def steam_path():
    import winreg
    for hive, key, name in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                path = Path(winreg.QueryValueEx(handle, name)[0])
                if path.is_dir():
                    return path
        except OSError:
            pass
    raise RuntimeError("Steam was not found. Install and sign in to the Steam desktop client.")


def manifest_game(text):
    app = re.search(r'"appid"\s+"(\d+)"', text)
    name = re.search(r'"name"\s+"((?:\\.|[^"\\])*)"', text)
    if not app or not name:
        return None
    value = int(app[1])
    if not 0 < value < 2**32:
        return None
    return Game(value, name[1].replace(r'\"', '"').replace(r'\\', '\\'), installed=True)


def discover_owned(session, candidates, installed=(), progress=None):
    """Read ownership only. Never initialize a game's achievement interface."""
    local = {game.app_id: game for game in installed}
    ids = sorted({int(value) for value in candidates if type(value) is int and 0 < value < 2**32} | local.keys())
    result = []
    session.verify_identity()
    for index, app_id in enumerate(ids):
        if index % 512 == 0:
            session.verify_identity()
            if progress:
                progress(index, len(ids), len(result))
        if app_id == 228980 or not session.owns(app_id):
            continue
        name = session.app_name(app_id)
        if not name:
            name = local[app_id].name if app_id in local else f"Steam App {app_id}"
        icon_reader = getattr(session, "app_icon", None)
        icon_hash = icon_reader(app_id) if icon_reader else ""
        result.append(Game(app_id, name, app_id in local, icon_hash))
    session.verify_identity()
    if progress:
        progress(len(ids), len(ids), len(result))
    return sorted(result, key=lambda game: (game.name.casefold(), game.app_id))


def installed_games(root=None):
    root = Path(root) if root else steam_path()
    paths = {root}
    try:
        text = (root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8")
        for value in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', text):
            paths.add(Path(value.replace(r'\\', '\\')))
    except OSError:
        pass
    games = {}
    for path in paths:
        for manifest in (path / "steamapps").glob("appmanifest_*.acf"):
            try:
                game = manifest_game(manifest.read_text(encoding="utf-8"))
                if game and game.app_id != 228980:  # Steamworks Common Redistributables
                    games[game.app_id] = game
            except (OSError, UnicodeError):
                continue
    return sorted(games.values(), key=lambda game: game.name.casefold())
