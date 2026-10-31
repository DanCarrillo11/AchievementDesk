"""Validate and publish a complete release from a trusted Windows Actions run."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workspace import VERSION
from updates import version_key


def request():
    value = json.loads((ROOT / "release-request.json").read_text(encoding="utf-8"))
    if value.get("version") != VERSION or type(value.get("prerelease")) is not bool:
        raise ValueError("Release request must match workspace.VERSION and declare prerelease status.")
    if value["prerelease"] != (version_key(VERSION)[3] < 4):
        raise ValueError("The version suffix and prerelease flag disagree.")
    value["tag"] = "v" + VERSION
    notes = (ROOT / value["notes_file"]).resolve()
    if not notes.is_relative_to(ROOT) or not notes.is_file():
        raise ValueError("Release notes must be a committed file within this repository.")
    metadata = ast.parse((ROOT / "version_info.txt").read_text(encoding="utf-8"))
    strings, versions = {}, {}
    for node in ast.walk(metadata):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "StringStruct":
            strings[ast.literal_eval(node.args[0])] = ast.literal_eval(node.args[1])
        if node.func.id == "FixedFileInfo":
            versions = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
    numeric = tuple(version_key(VERSION)[:3]) + (0,)
    if any(strings.get(k) != VERSION for k in ("FileVersion", "ProductVersion")):
        raise ValueError("Windows version strings do not match the release.")
    if versions.get("filevers") != numeric or versions.get("prodvers") != numeric:
        raise ValueError("Windows numeric versions do not match the release.")
    installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
    if (not re.search(r"^AppVersion=" + re.escape(VERSION) + r"\s*$", installer, re.M)
            or not re.search(r"^OutputBaseFilename=AchievementDesk-" + re.escape(VERSION) + r"-Setup\s*$", installer, re.M)):
        raise ValueError("Installer version does not match the release.")
    return value, notes


def asset_names():
    prefix = "AchievementDesk-" + VERSION
    return [prefix + "-Portable.zip", prefix + "-source.zip", prefix + "-Setup.exe"]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_archives(folder):
    for name in asset_names()[:2]:
        with zipfile.ZipFile(folder / name) as archive:
            if archive.testzip() is not None:
                raise ValueError("Archive failed its integrity check: " + name)
            for entry in archive.namelist():
                parts = Path(entry.replace("\\", "/")).parts
                if (entry.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", entry) or ".." in parts or
                        any(p.startswith(("work-", ".venv")) or p == ".git" for p in parts) or
                        any(p in ("history", "snapshots", "public-cache", "demo-snapshots", "library-cache", "completion-cache") for p in parts) or
                        parts[-1:] == ("workspace.json",)):
                    raise ValueError("Private or unsafe archive member: " + entry)


def verify_assets(folder):
    expected = asset_names()
    rows = {}
    for line in (folder / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in rows:
            raise ValueError("Invalid or duplicate checksum entry.")
        rows[match[2]] = match[1]
    if set(rows) != set(expected):
        raise ValueError("Checksums must describe exactly the three release downloads.")
    for name in expected:
        if not (folder / name).is_file() or digest(folder / name) != rows[name]:
            raise ValueError("Missing or changed release asset: " + name)
    inspect_archives(folder)
    return rows


def gh(*args, missing_ok=False, input_text=None):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", input=input_text)
    if result.returncode:
        if missing_ok and "404" in result.stderr:
            return None
        raise RuntimeError("GitHub command failed: " + result.stderr.strip())
    return result.stdout


def api(path, missing_ok=False, payload=None):
    args = ["api", path]
    if payload is not None:
        args += ["--method", "POST", "--input", "-"]
    data = gh(*args, missing_ok=missing_ok, input_text=json.dumps(payload) if payload is not None else None)
    return json.loads(data) if data is not None else None


def publish(folder):
    value, notes = request()
    hashes = verify_assets(folder)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    commit = os.environ.get("GITHUB_SHA", "")
    if (repo != "DanCarrillo11/AchievementDesk" or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or not re.fullmatch(r"[a-f0-9]{40}", commit)):
        raise RuntimeError("Publishing requires a trusted main-branch Actions run for this repository.")
    local_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if local_commit != commit:
        raise RuntimeError("The checked-out source does not match the release commit.")
    tag = value["tag"]
    # Keep the two end-user downloads. Checksums are also visible on the release page.
    names = [asset_names()[0], asset_names()[2]]
    body = notes.read_text(encoding="utf-8") + "\n\n## SHA-256\n\n```text\n" + "\n".join(hashes[n] + "  " + n for n in names) + "\n```\n"
    prepared_notes = folder / "published-notes.md"
    prepared_notes.write_text(body, encoding="utf-8")
    base = "repos/" + repo
    reference = api(base + "/git/ref/tags/" + tag, missing_ok=True)
    if reference and (reference["object"]["type"] != "commit" or reference["object"]["sha"] != commit):
        raise RuntimeError("An existing tag points elsewhere; it will not be moved.")
    release = api(base + "/releases/tags/" + tag, missing_ok=True)
    if release is None:
        # REST's tag endpoint only finds published releases. Drafts have pending tags.
        candidates = [r for r in api(base + "/releases?per_page=100") if r.get("tag_name") == tag]
        if len(candidates) > 1:
            raise RuntimeError("Multiple releases use this pending tag; resolve the ambiguity first.")
        release = candidates[0] if candidates else None
    if release and release.get("target_commitish") != commit:
        # A previous failed attempt may leave an empty unpublished draft. Discard
        # only the exact source explicitly named by the reviewed release request.
        if (release.get("draft") is True and release.get("assets") == [] and reference is None
                and release.get("target_commitish") == value.get("discard_empty_draft_from")):
            gh("api", "--method", "DELETE", base + "/releases/" + str(int(release["id"])))
            release = None
        else:
            raise RuntimeError("An existing release targets another commit; it will not be changed.")
    if release:
        if not release.get("draft"):
            print("This exact commit is already published: " + release["html_url"])
            return
    else:
        release = api(base + "/releases", payload=dict(tag_name=tag, target_commitish=commit,
                      name="Achievement Desk " + VERSION, body=body, draft=True, prerelease=value["prerelease"]))
        if release.get("draft") is not True or release.get("target_commitish") != commit:
            raise RuntimeError("GitHub did not create the expected source-bound draft.")
    # Replacing files is limited to an unpublished draft, supporting safe retries.
    gh("release", "upload", tag, "--repo", repo, "--clobber", *[str(folder / n) for n in names])
    uploaded = api(base + "/releases/" + str(release["id"]))
    assets = {a["name"]: a for a in uploaded.get("assets", [])}
    if set(assets) != set(names):
        raise RuntimeError("The draft does not contain exactly the intended release assets.")
    for name in names:
        asset = assets[name]
        if asset["size"] != (folder / name).stat().st_size or asset["state"] != "uploaded":
            raise RuntimeError("An uploaded asset is incomplete: " + name)
        if asset.get("digest") and asset["digest"] != "sha256:" + hashes[name]:
            raise RuntimeError("GitHub's asset checksum does not match: " + name)
    args = ["release", "edit", tag, "--repo", repo, "--draft=false",
            "--prerelease=" + str(value["prerelease"]).lower(), "--notes-file", str(prepared_notes)]
    if not value["prerelease"]:
        args.append("--latest")
    gh(*args)
    final = api(base + "/releases/" + str(release["id"]))
    if final.get("draft") or final.get("prerelease") != value["prerelease"]:
        raise RuntimeError("Release publication was not confirmed.")
    print("Published: " + final["html_url"])


def main():
    mode = sys.argv[1]
    value, _ = request()
    if mode == "validate":
        print("Validated release request: " + value["tag"])
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write("version=" + VERSION + "\ntag=" + value["tag"] + "\n")
    elif mode == "checksums":
        folder = Path(sys.argv[2]).resolve()
        lines = [digest(folder / n) + "  " + n for n in asset_names()]
        (folder / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
        verify_assets(folder)
        print("Release downloads and checksums verified.")
    elif mode == "publish":
        publish(Path(sys.argv[2]).resolve())
    else:
        raise ValueError("Unknown release operation.")


if __name__ == "__main__":
    main()
