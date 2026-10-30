<div align="center">
  <img src="assets/app.png" width="76" alt="Achievement Desk icon">
  <h1>Achievement Desk</h1>
  <p>A focused desktop workspace for your Steam achievements.</p>
  <p><strong>Windows x64 · Preview release · English interface</strong></p>
  <p>
    <a href="#features">Features</a> ·
    <a href="#getting-started">Getting started</a> ·
    <a href="docs/FEATURES.md">User guide</a> ·
    <a href="docs/TROUBLESHOOTING.md">Troubleshooting</a>
  </p>
</div>

![Achievement workspace](docs/screenshots/workspace.png)

*Actual application widgets with public Steam artwork and synthetic account and
achievement states. These screenshots do not show a real user's account.*

## Availability

**0.8.1-preview** is the first public Windows preview. It is not a stable 1.0.

**[Download portable ZIP](https://github.com/DanCarrillo11/AchievementDesk/releases/download/v0.8.1-preview/AchievementDesk-0.8.1-preview-Windows.zip)** ·
**[Download setup](https://github.com/DanCarrillo11/AchievementDesk/releases/download/v0.8.1-preview/AchievementDesk-0.8.1-preview-Setup.exe)**

[Release notes](https://github.com/DanCarrillo11/AchievementDesk/releases/tag/v0.8.1-preview) ·
[Source archive](https://github.com/DanCarrillo11/AchievementDesk/releases/download/v0.8.1-preview/AchievementDesk-0.8.1-preview-source.zip) ·
[SHA-256 checksums](https://github.com/DanCarrillo11/AchievementDesk/releases/download/v0.8.1-preview/SHA256SUMS.txt)

Downloads include their runtime; Python is not needed. Requires Windows x64 and
the signed-in Steam desktop client to be online for real account operations.
No Steam password or API key is requested.

## Features

- **Your library, in one window.** Search by title or App ID, browse with A–Z
  filters and 100-game pages, and keep favorites and recent games per account.
  Accessible games can appear even when they are not installed.
- **Clear achievement switches.** Prepare unlocks or relocks, search and filter
  the full list, and review every change before applying it to Steam.
- **Achievement sets and trophies.** Read Steam's reported set completion, filter
  by set and prepare remaining eligible unlocks. Unavailable data stays unconfirmed.
- **Compatibility evidence.** Distinguish readable games, confirmed changes,
  rejected operations and unconfirmed outcomes using local per-account evidence.
- **A quiet dark workspace.** Small Steam game icons, achievement artwork,
  optional rarity, compact rows, keyboard shortcuts and remembered preferences.
- **Traceable results.** Record activity and save a reference snapshot before
  writes. Confirmed, rejected, partial and unknown outcomes remain separate.

<details>
  <summary>Library and achievement-set views</summary>

![Embedded alphabetical library](docs/screenshots/library.png)

![Achievement sets and reported completion](docs/screenshots/sets-trophies.png)

</details>

## Getting started

1. Download the portable ZIP and extract the entire folder, or run the setup for
   a per-user installation with optional desktop shortcut.
2. Start Steam, sign in and stay online.
3. Open `AchievementDesk.exe` and select a game. Keep the portable executable,
   worker and `_internal/` folder together.
4. Prepare changes with the switches, choose **Review changes**, inspect the
   before/after list and explicitly choose **Apply to Steam**.

Selecting a game, searching and switching filters do not send achievement changes.
See the [user guide](docs/FEATURES.md) and [troubleshooting](docs/TROUBLESHOOTING.md).

### Run from source

Use Python 3.11+ x64. The demo uses synthetic data and never connects to Steam:

```powershell
git clone https://github.com/DanCarrillo11/AchievementDesk.git
cd AchievementDesk
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --demo
```

For your real account, start Steam and sign in, then run:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open a game, prepare changes with its switches, choose **Review changes**, then
explicitly choose **Apply to Steam**. Selecting a game, searching and switching
filters do not send achievement changes. See the [user guide](docs/FEATURES.md).

## Compatibility and completion

Game discovery establishes account access, not guaranteed edit support.
Protected or server-controlled achievements can reject client changes. Steam
client updates can also affect the versioned native interfaces this preview uses.

Steam controls completion trophies. Completing a set's available achievements can
earn completion, and previously earned completion can persist after new
achievements are added. Relocking achievements does not guarantee trophy removal.
The app never infers a Steam trophy from a 100% bar or pending changes.

Reference snapshots cannot restore historical unlock dates, trophy history or
game saves. Steam may briefly show a selected game as **Running** while its native
achievement helper is connected; the manager does not launch the game executable.

## Validation

- **173 automated checks** passed locally, using synthetic workers and Qt offscreen
  rendering. CI runs the suite on Windows with Python 3.11 and 3.14.
- The packaged 0.8.0 preview passed offscreen GUI and synthetic worker checks.
- One deliberately authorized real relock was acknowledged by Steam and confirmed
  in a fresh worker process, with all 12 other achievement states/dates unchanged.
  See the [redacted verification report](docs/validation/relock-2026-10-30.md).
- Broader real-game coverage, installation/upgrade testing and end-to-end trophy
  award timing remain work before a stable release. No universal compatibility
  or Valve approval is claimed.

## Development

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated suite requires no Steam account and performs no live achievement
writes. [Architecture](docs/ARCHITECTURE.md) explains the UI, isolated worker and
Steam adapter. [Contributing](CONTRIBUTING.md) covers changes and validation.

Build locally with `requirements-build.txt` and `AchievementDesk.spec`.
The manually triggered **Build Windows preview** workflow prepares portable/source
archives without publishing. The **Publish Windows release** workflow builds and
checks all downloads before publishing the release requested in `.github/release.json`.
See
[release preparation](docs/RELEASES.md).

## Privacy and support

Local data is stored under `%LOCALAPPDATA%\AchievementDesk`. Optional completion
checks send account/App IDs directly to Steam Community without cookies or
credentials. Artwork and completion requests can be disabled separately.
Read the [privacy guide](docs/PRIVACY.md), [troubleshooting guide](docs/TROUBLESHOOTING.md)
and [security reporting policy](SECURITY.md) before sharing logs or screenshots.

Report reproducible problems through [Issues](https://github.com/DanCarrillo11/AchievementDesk/issues).

## Credits and license

An independent Python implementation with a native adapter adapted from
[Steam Achievement Manager / SAM.API](https://github.com/gibbed/SteamAchievementManager).
Achievement Desk is not affiliated with Valve or the SAM author.

Original project code is [MIT licensed](LICENSE). Adapted SAM.API portions retain
their zlib notice. Qt/PySide6 and artwork credits are documented in
[third-party notices](THIRD_PARTY_NOTICES.txt) and [licenses](licenses/).
