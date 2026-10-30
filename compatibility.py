"""Account-scoped evidence, never a speculative global compatibility blacklist."""
from datetime import datetime, timezone

FILTERS = ("Not checked", "Achievements readable", "Changes confirmed", "Changes rejected", "Changes unconfirmed", "No achievements", "Read unavailable")


def observe_read(previous, count):
    return dict(previous, read="readable" if count else "empty", achievement_count=count,
                read_utc=datetime.now(timezone.utc).isoformat())


def observe_result(previous, result, changes):
    value = dict(previous)
    confirmed = set(result.get("confirmed", []))
    for change in changes:
        if change["key"] in confirmed:
            value["unlock_seen" if change["after"] else "relock_seen"] = True
    value.update(last_result=result.get("status", "unconfirmed"), rejected=len(result.get("rejected", [])),
                 unconfirmed=len(result.get("unconfirmed", [])), write_utc=datetime.now(timezone.utc).isoformat())
    return value


def status(evidence):
    if evidence.get("read") == "failed":
        return "Read unavailable", "#d8b477"
    if evidence.get("read") == "empty":
        return "No achievements", "#9999a5"
    if evidence.get("last_result") == "unconfirmed" or evidence.get("unconfirmed", 0):
        return "Changes unconfirmed", "#d8b477"
    if evidence.get("rejected", 0):
        return "Changes rejected", "#d8b477"
    if evidence.get("unlock_seen") or evidence.get("relock_seen"):
        return "Changes confirmed", "#86c9a2"
    if evidence.get("read") == "readable":
        return "Achievements readable", "#93c5ff"
    return "Not checked", "#777782"


def details(evidence):
    title, _ = status(evidence)
    lines = [title]
    if "achievement_count" in evidence:
        lines.append(f"Last successful read: {evidence['achievement_count']} achievements.")
    if evidence.get("read_utc"):
        lines.append("Read checked: " + evidence["read_utc"][:19].replace("T", " ") + " UTC")
    lines.append("Unlock observed: " + ("Yes" if evidence.get("unlock_seen") else "Not yet verified"))
    lines.append("Relock observed: " + ("Yes" if evidence.get("relock_seen") else "Not yet verified"))
    if evidence.get("write_utc"):
        lines.append("Change checked: " + evidence["write_utc"][:19].replace("T", " ") + " UTC")
    if evidence.get("rejected", 0):
        lines.append(f"Last operation: {evidence['rejected']} changes rejected by Steam.")
    if evidence.get("last_result") == "unconfirmed" or evidence.get("unconfirmed", 0):
        lines.append("Last operation could not be fully confirmed. Check Steam before retrying.")
    lines.append("Evidence is local to this account. A readable game or a confirmed change does not guarantee every achievement can be edited.")
    return "\n".join(lines)
