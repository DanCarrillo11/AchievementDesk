# Build with: python -m PyInstaller --clean --noconfirm AchievementDesk.spec
import os

# Build against the Windows runtime, not unrelated DLLs from tools on PATH.
# In particular, Poppler's ICU has incompatible exports under the same filename.
original_path = os.environ.get('PATH', '')
os.environ['PATH'] = os.pathsep.join(
    part for part in original_path.split(os.pathsep)
    if 'poppler' not in part.lower()
)
a = Analysis(['app.py'], pathex=[], binaries=[], datas=[('assets/catalog.json', 'assets'), ('assets/app.ico', 'assets'), ('licenses', 'licenses')], hiddenimports=[],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml'])
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AchievementDesk',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, icon='assets/app.ico', version='version_info.txt')
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AchievementDeskWorker',
             debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
             console=True, icon='assets/app.ico')
coll = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name='AchievementDesk')
