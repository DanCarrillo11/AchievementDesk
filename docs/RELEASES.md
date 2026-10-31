# Releases

The official repository is https://github.com/DanCarrillo11/AchievementDesk.
Version 1.0.0 starts the stable release line. Application, executable, installer
and `release-request.json` versions must agree.

## Build and verify

The **Tests** workflow runs synthetic/offscreen checks on Windows with Python
3.11 and 3.14. **Build Windows release** also runs on pull requests, builds the
frozen application, exercises its synthetic helper and offscreen interface (including embedded details, search and minimum-size layouts), and
compiles the installer with the runner's Inno Setup console compiler.

On the disposable Windows runner it silently installs the checksum-pinned
1.0.0, upgrades to the candidate, verifies startup and retained synthetic
local data, uninstalls, and then checks a clean install/uninstall. No native
Steam session is used. Installer checks refuse to run outside Windows Actions.

To reproduce the portable build locally with Windows x64 and Python 3.11+:

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python -m PyInstaller --clean --noconfirm AchievementDesk.spec
python tools/verify_packaged.py dist/AchievementDesk
python tools/package_release.py dist/AchievementDesk release
$releaseRoot = (Resolve-Path release).Path
$portableFolder = Join-Path $releaseRoot 'AchievementDesk-1.1.0-Portable'
ISCC.exe "/DBuildSource=$portableFolder" "/DOutputFolder=$releaseRoot" installer.iss
python tools/publish_release.py checksums release
```

Use a fresh `release` folder. Compilation does not run setup or open the app.
Distribute the complete portable folder, including the helper, runtime and
licenses. Source archives contain only approved project files.

## Publication

1. Review the candidate pull request and its Tests/Build Windows release checks.
2. Set `release-request.json` to the exact version, `prerelease` flag and notes
   file, and merge to `main`. Its change triggers a new build of that exact commit.
3. After verification, a separate publication job receives `contents: write`.
   Pull-request build jobs only have read access. Manual runs create artifacts
   without publishing.
4. The publisher validates archives and SHA-256 checksums, creates an unpublished
   draft for the source commit, uploads exactly the portable ZIP and setup, then
   verifies server-side asset sizes and hashes before publishing.
5. Stable versions have `prerelease: false` and become **Latest**. Suffix versions
   remain prereleases. Check the public tag, both downloads and checksum notes.

Existing published releases are never reuploaded or moved to another commit.
Retries may replace files only in the same source commit's unpublished draft.
An empty failed draft can be discarded only when its exact previous source SHA
is explicitly named by `discard_empty_draft_from` in the reviewed request, it
contains no assets, and its tag has not been created. Published releases and
drafts containing downloads are never discarded by this recovery path.
GitHub supplies source archives from the release tag; the two attached files are
the end-user downloads. The notes contain their SHA-256 hashes. Build artifacts
also retain the corresponding source ZIP and checksum file for 14 days.

## Updates and upgrades

Settings defaults to `DanCarrillo11/AchievementDesk`; older empty channels migrate
to it without replacing a custom repository. Update checks run only on request
and open a GitHub release page. They never download or execute an installer.
Stable installations ignore previews by both tag and GitHub prerelease status.

Close Achievement Desk before upgrading with setup. Portable users should extract
into a new folder. Both distributions use `%LOCALAPPDATA%/AchievementDesk` for
preferences, favorites, history, library cache and reference snapshots. Uninstall
retains that folder. See the [1.0 release scope](validation/stable-1.0.0.md) for
the game evidence and remaining platform limits.
