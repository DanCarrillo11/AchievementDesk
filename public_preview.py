"""Offscreen visual QA: real public artwork, explicitly synthetic account/states."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import json
import re
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from domain import Achievement
from library import Game
from library_view import history_dialog
from media import fetch, parse_icons, percentages
from modern_ui import Desk
from completion import parse_completion
from compatibility import observe_read

def render(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle("Fusion")
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
    desk = Desk(demo=True, hidden=True)
    desk.account_id = desk.library_account_id = "DEMO"
    # Public, fixed App IDs and their verified standard Steam app-list icon hashes.
    # No personal library is read by this preview.
    desk.library = [Game(620, "Portal 2", icon_hash="25a5a16b2423bf7487ac5340b5b0948cef48c5f8"),
                    Game(440, "Team Fortress 2", icon_hash="f568912870a4684f9ec76277a1a404dda6bab213"),
                    Game(400, "Portal", icon_hash="cfa928ab4119dd137e50d728e8fe703e4e970aff"),
                    Game(730, "Counter-Strike 2", icon_hash="8dbc71957312bbd3baea65848b545be9eae2a355"),
                    Game(70, "Half-Life", icon_hash="95be6d131fc61f145797317ca437c9765f24b41c"),
                    Game(220, "Half-Life 2", icon_hash="fcfb366051782b8ebf2aa297f3b746395858cb62")]
    desk.game = desk.library[0]
    desk.client = object()  # No read/apply method exists; this script cannot contact the native client.
    page = fetch("https://steamcommunity.com/stats/620/achievements/?l=english").decode("utf-8")
    icons = parse_icons(page)
    global_data = percentages(json.loads(fetch("https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid=620")))
    pattern = r'\\"api_name\\":\\"([^"\\]+)\\",\\"name\\":\\"([^"\\]+)\\",\\"description\\":\\"([^"\\]+)\\",\\"hidden\\":(true|false)'
    rows = list(re.findall(pattern, page))[:6]
    if len(rows) < 6:
        raise RuntimeError("The public Steam schema changed; inspect the parser before taking previews.")
    desk.rows = [Achievement(key, name, description, index < 2, hidden=hidden == "true") for index, (key, name, description, hidden) in enumerate(rows)]
    desk.presentation[620] = dict(icons=icons, percentages=global_data)
    # Real public set definitions; no real account completion is requested.
    desk.completions[("DEMO", 620)] = parse_completion(page, 620)
    desk.completions[("DEMO", 620)]["notice"] = "Public Steam set definitions · Synthetic account and achievement states · No trophy status requested."
    desk.workspace.save_compatibility("DEMO", 620, observe_read({}, len(desk.rows)))
    desk.media.enabled = True
    desk.game_title.setText("Portal 2")
    desk.caption.setText("Public artwork · Synthetic achievement states")
    desk.workspace.favorite("DEMO", 620)
    desk.workspace.visit("DEMO", 620)
    desk.filter_games()
    desk.render()
    desk.set_status("Demonstration workspace · No Steam account connected")
    desk.show()
    desk.browse_library()
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        desk.poll()
        app.processEvents()
        with desk.media.lock:
            pending = bool(desk.media.pending)
        if not pending and desk.callbacks.empty() and len(desk.game_icon_pixmaps) == 6 and len(desk.icon_paths) == 6:
            break
        time.sleep(.02)
    desk.poll()
    app.processEvents()
    if len(desk.game_icon_pixmaps) != 6 or len(desk.icon_paths) != 6:
        raise RuntimeError("Expected public Steam list icons/achievement images were not available.")
    desk.grab().save(str(output / "library.png"))
    desk.library_page.set_letter("P")
    app.processEvents()
    desk.grab().save(str(output / "letter-p.png"))
    desk.library_page.set_letter("All")
    desk.show_achievements()
    app.processEvents()
    desk.grab().save(str(output / "workspace.png"))
    desk.show_completion()
    app.processEvents()
    desk.grab().save(str(output / "sets-trophies.png"))
    desk.show_achievements()
    desk.toggle_achievement(desk.rows[2].key, True)
    app.processEvents()
    desk.grab().save(str(output / "pending.png"))
    dialog = desk.make_review_dialog()
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "review.png"))
    dialog.close()
    settings = desk.make_settings_dialog()
    settings.show()
    app.processEvents()
    settings.grab().save(str(output / "settings.png"))
    settings.close()
    activity = desk.workspace.start_activity("DEMO", desk.game, [dict(key=desk.rows[2].key, name=desk.rows[2].name, before=False, after=True)])
    desk.workspace.finish_activity("DEMO", activity, dict(status="demo", message="Demonstration record only. No Steam operation was performed.", confirmed=[], rejected=[], unconfirmed=[desk.rows[2].key]))
    history = history_dialog(desk)
    history.show()
    history.tree.setCurrentItem(history.tree.topLevelItem(0))
    app.processEvents()
    history.grab().save(str(output / "history.png"))
    history.close()
    desk.resize(1020, 760)
    desk.browse_library()
    app.processEvents()
    desk.grab().save(str(output / "minimum.png"))
    desk.show_completion()
    app.processEvents()
    desk.grab().save(str(output / "sets-minimum.png"))
    desk.desired.clear()
    desk.client = None
    desk.close()
    print(f"Public artwork QA complete: {len(desk.game_icon_pixmaps)} Steam list icons, {len(desk.icon_paths)} achievement images. No native Steam session or desktop control.")
