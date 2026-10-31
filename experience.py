"""Presentation helpers. No Steam operations or account lookups."""
SORTS = ("Steam order", "Name A–Z", "Name Z–A", "Newest unlocks", "Oldest unlocks", "Rarest first", "Most common first")
FILTERS = ("All", "Locked", "Unlocked", "Pending")


def match_ranges(text, query):
    """Return literal case-insensitive matches as Python character offsets."""
    if not query:
        return []
    folded, positions = [], []
    for index, character in enumerate(text):
        value = character.casefold()
        folded.append(value)
        positions.extend([index] * len(value))
    haystack, needle = "".join(folded), query.casefold()
    matches, start = [], 0
    while (found := haystack.find(needle, start)) >= 0:
        span = (positions[found], positions[found + len(needle) - 1] + 1)
        if not matches or matches[-1] != span:
            matches.append(span)
        start = found + len(needle)
    return matches


def clean_view(value):
    value = value if isinstance(value, dict) else {}
    def bounded(name, maximum):
        item = value.get(name, 0)
        return min(maximum, max(0, item)) if type(item) is int else 0
    return dict(query=value.get("query", "")[:256] if isinstance(value.get("query"), str) else "",
                filter=value.get("filter") if value.get("filter") in FILTERS else "All",
                sort=value.get("sort") if value.get("sort") in SORTS else "Steam order",
                page=bounded("page", 10000), scroll=bounded("scroll", 1000000))


def explain_error(detail, uncertain=False):
    if uncertain:
        return "Check the result in Steam", "Some changes may have been saved. Check Steam before preparing another change."
    text = detail.casefold()
    if "account" in text and ("changed" in text or "different" in text):
        return "Your Steam account changed", "Refresh your library to reconnect to the account currently signed in."
    if "access" in text and ("game" in text or "account" in text):
        return "This game is unavailable for this account", "Check the account signed in to Steam, then refresh your library."
    if "offline" in text or "sign in" in text or "start steam" in text:
        return "Steam needs to be online", "Start Steam, sign in and connect, then try again."
    if "timed out" in text or "timeout" in text or "within 20 seconds" in text:
        return "Steam did not respond in time", "Check your connection and Steam, then retry the read."
    if "permission" in text or "denied" in text or "read-only" in text:
        return "Local data could not be saved", "Check that your local data folder is writable, then try again."
    return "The request could not be completed", "Check Steam and try again. Technical details are available below."
