"""State and change planning. Importing this module never connects to Steam."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    description: str
    unlocked: bool
    unlock_time: int = 0
    hidden: bool = False


@dataclass(frozen=True)
class Change:
    key: str
    before: bool
    after: bool


def plan_changes(rows, desired):
    known = {a.key: a for a in rows}
    if len(known) != len(rows):
        raise ValueError("Duplicate achievement identifiers received from Steam.")
    changes = []
    for key, state in desired.items():
        if key not in known or type(state) is not bool:
            raise ValueError("Invalid achievement selection. Reload the game.")
        if known[key].unlocked != state:
            changes.append(Change(key, known[key].unlocked, state))
    return changes


def validate_changes(rows, changes):
    known = {a.key: a for a in rows}
    seen = set()
    if not changes or len(changes) > 5000:
        raise ValueError("Select between 1 and 5,000 changes.")
    for c in changes:
        if c.key in seen or c.key not in known:
            raise ValueError("Unknown or duplicate achievement. Reload the game.")
        if type(c.before) is not bool or type(c.after) is not bool or c.before == c.after:
            raise ValueError("Invalid change state.")
        if known[c.key].unlocked != c.before:
            raise ValueError("An achievement changed since your review. Reload before applying.")
        seen.add(c.key)


def write_snapshot(folder, app_id, account_id, rows, changes):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    path = folder / f"{app_id}-{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.json"
    payload = dict(schema=1, app_id=app_id, account_id=str(account_id),
                   created_utc=now.isoformat(), achievements=[asdict(a) for a in rows],
                   requested_changes=[asdict(c) for c in changes],
                   note="Reference snapshot only. Original unlock times and trophies cannot be restored by this file.")
    # Exclusive creation: a failed snapshot must stop the operation before mutations.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return path


def apply_changes(backend, changes, snapshot_folder, expected_account):
    """Refresh, validate, snapshot, submit once and report partial/unknown results."""
    if str(backend.account_id) != str(expected_account):
        raise ValueError("Steam account changed. Reload and review again.")
    rows = backend.read()
    validate_changes(rows, changes)
    snapshot = write_snapshot(snapshot_folder, backend.app_id, backend.account_id, rows, changes)
    accepted, rejected = [], []
    for change in changes:
        if backend.set_state(change.key, change.after):
            accepted.append(change)
        else:
            rejected.append(change.key)
    if not accepted:
        return dict(status="rejected", confirmed=[], rejected=rejected,
                    unconfirmed=[], snapshot=str(snapshot), message="Steam refused every requested change.",
                    achievements=[asdict(a) for a in rows])
    # Steam may persist local changes on exit too: never claim rollback on failure.
    try:
        backend.store()
        latest = backend.read()
        current = {a.key: a.unlocked for a in latest}
    except Exception as exc:
        return dict(status="unconfirmed", confirmed=[], rejected=rejected,
                    unconfirmed=[c.key for c in accepted], snapshot=str(snapshot),
                    message=f"Persistence could not be confirmed: {exc}. Check Steam before retrying.")
    confirmed = [c.key for c in accepted if current.get(c.key) == c.after]
    unconfirmed = [c.key for c in accepted if current.get(c.key) != c.after]
    return dict(status="confirmed" if not rejected and not unconfirmed else "partial",
                confirmed=confirmed, rejected=rejected, unconfirmed=unconfirmed,
                snapshot=str(snapshot), message="Steam acknowledged the save; achievement states were read again.",
                achievements=[asdict(a) for a in latest])
