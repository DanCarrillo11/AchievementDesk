# Release preparation

The source repository is https://github.com/DanCarrillo11/AchievementDesk.
The first public Windows preview is requested through `release-request.json`.
The release workflow creates the downloadable Windows packages only after the
build and tests complete. No stable version is claimed.

## Repository checks

The Tests workflow runs synthetic and offscreen checks on Windows with Python
3.11 and 3.14. It does not connect to a live Steam account. The separate **Build Windows preview** workflow supports manual runs that produce
reviewable artifacts but no public release. A change to `release-request.json`
on `main` triggers the same build and additionally publishes a prerelease.
It packages the portable and source ZIPs, compiles the Inno Setup installer, and
computes SHA-256 checksums for verification. Only the Portable ZIP and
setup executable are attached to public releases.

## Reproduce

Use a Windows x64 environment, Python 3.11+ and Inno Setup 6.7.3's console compiler:

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -q
python -m PyInstaller --clean --noconfirm AchievementDesk.spec
python tools/package_release.py dist/AchievementDesk release
$releaseRoot = (Resolve-Path release).Path
$portableFolder = Join-Path $releaseRoot 'AchievementDesk-0.8.1-preview-Portable'
ISCC.exe "/DBuildSource=$portableFolder" "/DOutputFolder=$releaseRoot" installer.iss
```

Use absolute paths for BuildSource and OutputFolder when the compiler is run from
another directory. Compilation runs in the console and does not launch the installer
or application. The complete portable folder is required, including its helper,
Qt runtime and license texts. The installer includes the same complete folder.

`workspace.VERSION`, `version_info.txt` and `installer.iss` must describe the same
release before packaging. Generate SHA-256 checksums for the final archives/setup.
The optional installer installs per user and retains preferences/history on uninstall.

## Public release channel

1. Review the source commit, release notes and the completed Windows checks.
2. With approval to publish, set `release-request.json` to the exact version in
   `workspace.VERSION`, `version_info.txt` and `installer.iss`, and commit it to
   `main`. The workflow builds and publishes that version as a GitHub prerelease.
3. Confirm that the release has exactly two uploaded assets: the Windows portable
   ZIP and the setup executable. Its tag is `v<version>`. GitHub also generates its
   own source archives automatically; these are not uploaded release assets.
4. Set that repository's `owner/name` in Settings → Updates and check it.

The checker reads at most 20 recent public releases. It skips drafts and invalid
version tags, and skips prereleases for stable installations. It opens GitHub's
release page only when the user chooses to; no downloaded code is executed by it.

## Validation scope

Tests use synthetic workers and offscreen Qt. Public presentation QA reads only
public Steam pages/CDN/API data, without using the native Steam account connection.
Optional runtime completion checks read the account's Steam Community page
without cookies or credentials; private/missing completion stays unconfirmed.
No automatic write probe is used for compatibility. The separately authorized
real relock is documented in [validation evidence](validation/relock-2026-10-30.md).

Artwork is not bundled with the executable; the screenshots show public artwork
and explicitly synthetic states. A public source layout change can remove optional
icons or rarity temporarily; the native state and reviewed write workflow remain
independent of those presentation requests.

The Achievement Desk installer is compiled, inspected and checksummed. Its interactive installation
and uninstallation have not been exercised on the user's desktop.
