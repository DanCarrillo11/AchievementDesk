"""Render the real application using Qt's offscreen platform and synthetic data."""
import os
from pathlib import Path


def render(output):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from modern_ui import Desk
    from demo import DemoSession
    from library import Game
    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setStyle("Fusion")
    window = Desk(demo=True, hidden=True)
    window.library_loaded(dict(account_id="DEMO", games=[
        dict(app_id=0, name="The Last Explorer", installed=True),
        dict(app_id=1, name="Distant Worlds", installed=False),
        dict(app_id=2, name="Beyond the Horizon", installed=True),
        dict(app_id=3, name="A Quiet Adventure", installed=False),
        dict(app_id=4, name="The Long Way Home", installed=False)]))
    window.game, window.account_id, window.client = Game(0, "The Last Explorer", True), "DEMO", object()
    window.rows = DemoSession().read()
    window.game_title.setText("The Last Explorer")
    window.caption.setText("Achievements · Demo workspace")
    window.render()
    window.filter_games()
    window.set_status("Demo data · Steam is not connected")
    window.show()
    app.processEvents()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError("Could not save the interface render")
    window.toggle_achievement("EXPLORER", True)
    app.processEvents()
    if not window.grab().save(str(output.with_name(output.stem + "-pending.png"))):
        raise RuntimeError("Could not save the pending-state render")
    window.desired.clear()
    window.client = None
    window.close()
