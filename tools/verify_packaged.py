"""Exercise a frozen synthetic worker/GUI; optionally check a temporary install."""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_gui(executable, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(executable), "--render-demo", str(output)], check=True,
                   env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True,
                   text=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    if not output.is_file():
        raise RuntimeError("The packaged GUI did not produce its offscreen render.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("--installer", type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    worker = build / "AchievementDeskWorker.exe"
    if not worker.is_file():
        raise RuntimeError("Packaged worker is missing.")
    source_icon = (ROOT / "assets/app.ico").read_bytes()
    if hashlib.sha256((build / "_internal/assets/app.ico").read_bytes()).digest() != hashlib.sha256(source_icon).digest():
        raise RuntimeError("The bundled application icon differs from the source asset.")
    with patch.object(sys, "executable", str(worker)), patch.object(sys, "frozen", True, create=True):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_transport.py")
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            raise RuntimeError("Packaged synthetic-worker checks failed.")
    run_gui(build / "AchievementDesk.exe", ROOT / ".ci-artifacts/packaged-demo.png")
    if args.installer:
        installer = args.installer.resolve()
        with tempfile.TemporaryDirectory(prefix="AchievementDesk-install-", ignore_cleanup_errors=True) as temporary:
            destination = Path(temporary) / "application"
            subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                            "/DIR=" + str(destination), "/TASKS="], check=True, timeout=90,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            run_gui(destination / "AchievementDesk.exe", ROOT / ".ci-artifacts/installed-demo.png")
            subprocess.run([str(destination / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                           check=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic() + 10
            while (destination / "AchievementDesk.exe").exists() and time.monotonic() < deadline:
                time.sleep(.2)
            if (destination / "AchievementDesk.exe").exists():
                raise RuntimeError("Uninstall did not remove the temporary application.")
            if (destination / "AchievementDeskWorker.exe").exists() or (destination / "_internal").exists():
                raise RuntimeError("Uninstall left application runtime files behind.")
        print("Temporary silent installation, installed GUI and uninstallation checks passed.")
    print("Packaged synthetic checks passed; no native Steam account operation was used.")


if __name__ == "__main__":
    main()
