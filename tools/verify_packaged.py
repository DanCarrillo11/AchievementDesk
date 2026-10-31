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
from workspace import VERSION


def run_gui(executable, output, environment=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(executable), "--render-demo", str(output)], check=True,
                   env=dict(environment or os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True,
                   text=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    if not output.is_file():
        raise RuntimeError("The packaged GUI did not produce its offscreen render.")


def check_installation(installer, previous=None):
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_OS") != "Windows":
        raise RuntimeError("Installer checks run only on GitHub's disposable Windows runner.")
    with tempfile.TemporaryDirectory(prefix="AchievementDesk-install-", ignore_cleanup_errors=True) as temporary:
        destination = Path(temporary) / "application"
        data = Path(temporary) / "user-data" / "AchievementDesk"
        data.mkdir(parents=True)
        retained = {"workspace.json": b'{"settings":{"compact":true,"release_repository":""}}',
                    "history/release-smoke.json": b'[{"status":"unconfirmed","synthetic":true}]',
                    "snapshots/release-smoke.json": b'{"synthetic":true}'}
        for name, content in retained.items():
            path = data / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        environment = dict(os.environ, LOCALAPPDATA=str(data.parent))
        def verify_retained():
            for name, content in retained.items():
                if (data / name).read_bytes() != content:
                    raise RuntimeError("Installation changed retained local data: " + name)
        def install(path, label):
            subprocess.run([str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                            "/DIR=" + str(destination), "/GROUP=Achievement Desk Release Smoke", "/TASKS=",
                            "/LOG=" + str(ROOT / (".ci-artifacts/" + label + ".log"))],
                           check=True, timeout=120, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
            run_gui(destination / "AchievementDesk.exe", ROOT / (".ci-artifacts/" + label + ".png"), environment)
            verify_retained()
            print(label + " installed files: " + ", ".join(sorted(p.name for p in destination.iterdir())))
        def uninstall():
            # Inno can allocate a new numbered uninstaller during an upgrade.
            uninstallers = sorted(destination.glob("unins*.exe"))
            if not uninstallers:
                raise RuntimeError("Installer did not create an uninstaller in " + str(destination))
            subprocess.run([str(uninstallers[-1]), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                           check=True, timeout=90, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic() + 15
            while (destination / "AchievementDesk.exe").exists() and time.monotonic() < deadline:
                time.sleep(.2)
            if any((destination / n).exists() for n in ("AchievementDesk.exe", "AchievementDeskWorker.exe", "_internal")):
                raise RuntimeError("Uninstall left application runtime files behind.")
            verify_retained()
        if previous:
            install(previous, "previous-install")
            install(installer, "upgraded-install")
            uninstall()
        install(installer, "clean-install")
        uninstall()
    print("Clean install, upgrade, offscreen startup, retained data and uninstall checks passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--previous-installer", type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    worker = build / "AchievementDeskWorker.exe"
    if not worker.is_file():
        raise RuntimeError("Packaged worker is missing.")
    reported = subprocess.run([str(worker), "--version"], check=True, capture_output=True, text=True,
                              timeout=20, creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    if reported != "Achievement Desk " + VERSION:
        raise RuntimeError("The packaged runtime has a different version: " + reported)
    source_icon = (ROOT / "assets/app.ico").read_bytes()
    if hashlib.sha256((build / "_internal/assets/app.ico").read_bytes()).digest() != hashlib.sha256(source_icon).digest():
        raise RuntimeError("The bundled application icon differs from the source asset.")
    with patch.object(sys, "executable", str(worker)), patch.object(sys, "frozen", True, create=True):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_transport.py")
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            raise RuntimeError("Packaged synthetic-worker checks failed.")
    run_gui(build / "AchievementDesk.exe", ROOT / ".ci-artifacts/packaged-demo.png")
    if args.installer:
        check_installation(args.installer.resolve(), args.previous_installer.resolve() if args.previous_installer else None)
    print("Packaged synthetic checks passed; no native Steam account operation was used.")


if __name__ == "__main__":
    main()
