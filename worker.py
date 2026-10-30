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


def run_library():
    """Read the signed-in account's access for catalog IDs; never request stats."""
    import os
    from pathlib import Path
    from catalog import catalog_ids
    from library import discover_owned, installed_games
    from native import SteamLibrarySession
    session = None
    try:
        data_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.cwd()))) / "AchievementDesk"
        ids = catalog_ids(data_dir)
        local = installed_games()
        session = SteamLibrarySession()
        def progress(scanned, total, found):
            print(json.dumps(dict(progress=True, scanned=scanned, total=total, found=found)), flush=True)
        games = discover_owned(session, ids, local, progress)
        result = dict(ok=True, account_id=str(session.account_id), games=[asdict(game) for game in games])
    except Exception as exc:
        result = dict(ok=False, error=str(exc))
    finally:
        if session:
            session.close()
    print(json.dumps(result), flush=True)
