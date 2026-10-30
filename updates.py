"""User-requested GitHub release lookup; never downloads or runs executables."""
import json
import re
from urllib.error import HTTPError
from media import fetch


def repository(value):
    value = value.strip().removeprefix("https://github.com/").rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}", value):
        raise ValueError("Enter a GitHub repository as owner/name.")
    return value


def version_key(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-.]([A-Za-z]+)(?:[.-]?(\d+))?)?", value)
    if not match:
        raise ValueError("The release tag is not a supported version.")
    a, b, c, suffix, number = match.groups()
    if suffix and suffix.lower() not in ("alpha", "preview", "beta", "rc"):
        raise ValueError("Unsupported prerelease tag.")
    rank = {"alpha": 0, "preview": 1, "beta": 2, "rc": 3}.get((suffix or "").lower(), 4)
    return int(a), int(b), int(c), rank, int(number or 0)


def check_release(repo, current):
    repo = repository(repo)
    try:
        releases = json.loads(fetch(f"https://api.github.com/repos/{repo}/releases?per_page=20"))
    except HTTPError as error:
        if error.code == 404:
            raise ValueError("The repository or its public releases could not be found.") from None
        raise
    valid = []
    for entry in releases:
        if not isinstance(entry, dict) or entry.get("draft"):
            continue
        try:
            key = version_key(entry["tag_name"])
        except (KeyError, ValueError):
            continue
        # Stable installations don't offer preview builds.
        if version_key(current)[3] == 4 and entry.get("prerelease"):
            continue
        url = entry.get("html_url", "")
        if url.lower().startswith(f"https://github.com/{repo.lower()}/releases/tag/"):
            valid.append((key, entry["tag_name"], url))
    if not valid:
        return dict(newer=False, message="No published releases are available yet.", url="")
    key, tag, url = max(valid)
    return dict(newer=key > version_key(current), message=f"Latest published version: {tag}", url=url)
