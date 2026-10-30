"""One isolated Steam connection per game, JSON messages over stdin/stdout."""
from dataclasses import asdict
import json
import sys
from domain import Change, apply_changes


def run(app_id, demo=False):
    session = None
    try:
        if demo:
            from demo import DemoSession
            session = DemoSession(app_id)
        else:
            from native import SteamSession
            session = SteamSession(app_id)
        rows = session.read()
        reply = dict(ok=True, app_id=app_id, account_id=str(session.account_id),
                     achievements=[asdict(a) for a in rows])
        print(json.dumps(reply), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
                command = request.get("command")
                if command == "close":
                    break
                if command == "read":
                    reply = dict(ok=True, app_id=app_id, account_id=str(session.account_id),
                                 achievements=[asdict(a) for a in session.read()])
                elif command == "apply":
                    changes = [Change(**c) for c in request["changes"]]
                    result = apply_changes(session, changes, request["snapshot_folder"], request["account_id"])
                    reply = dict(ok=True, result=result)
                else:
                    raise ValueError("Unknown worker command.")
            except Exception as exc:
                reply = dict(ok=False, error=str(exc))
            print(json.dumps(reply), flush=True)
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc))), flush=True)
    finally:
        if session:
            session.close()


def run_library(refresh=False):
    """Identify Steam first; reuse this account's snapshot unless refreshed."""
    import os
    from pathlib import Path
    from catalog import catalog_ids
    from library import discover_owned, installed_games
    from library_cache import load_library_cache, save_library_cache
    from native import SteamLibrarySession
    session = None
    try:
        data_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.cwd()))) / "AchievementDesk"
        session = SteamLibrarySession()
        session.verify_identity()
        account_id = str(session.account_id)
        games = None if refresh else load_library_cache(data_dir, account_id)
        cached = games is not None
        if games is None:
            ids = catalog_ids(data_dir)
            local = installed_games()
            def progress(scanned, total, found):
                print(json.dumps(dict(progress=True, scanned=scanned, total=total, found=found)), flush=True)
            games = discover_owned(session, ids, local, progress)
            # A completed scan is still usable when the cache cannot be written.
            try:
                save_library_cache(data_dir, account_id, games)
            except (OSError, ValueError):
                pass
        session.verify_identity()
        result = dict(ok=True, account_id=account_id, cached=cached,
                      games=[asdict(game) for game in games])
    except Exception as exc:
        result = dict(ok=False, error=str(exc))
    finally:
        if session:
            session.close()
    print(json.dumps(result), flush=True)
