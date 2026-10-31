# Achievement Desk

A Windows desktop application for reading and managing Steam achievements through
your locally signed-in Steam client. Interface and documentation are in English.

**Version: 1.1.0.** Not affiliated with Valve. This is an independent
Python implementation, with a Steam adapter adapted from SAM.API's interface
layouts and connection approach. See THIRD_PARTY_NOTICES.txt.

![Achievement workspace](screenshots/workspace.png)

*Real application widgets and public Steam artwork, shown with synthetic account
and achievement states. This is not a screenshot of anyone's Steam account.*

## What's included

- An embedded, searchable game library with an All / # / A–Z index, compact rows
  and 100 games per page. No separate library window.
- Small square Steam game-list icons, sourced from client metadata/cache and CDN.
- An embedded achievement-set view with Steam-reported completion/trophies,
  DLC/archive availability, set filtering and remaining unlocks prepared for review.
- Account-scoped compatibility evidence for every library entry: not checked,
  readable, confirmed/rejected/unconfirmed changes, no achievements or read unavailable.
- Per-account favorites and recently opened games, remembered between sessions.
- Real achievement icons and global completion percentages when Steam provides them.
- Sort by name, unlock date or global rarity; missing data stays last.
- A before/after review table and explicit consent before submitting changes.
- Local activity history with confirmed, partial, rejected and unconfirmed outcomes.
- Saved preferences, window size, comfortable/compact rows and reduced motion.
- Read progress, read cancellation and retry actions; applying changes cannot be cancelled.
- Application icon, application version metadata and keyboard shortcuts.
- Portable distribution, optional per-user installer and on-demand GitHub release lookup.

## Optional installation

Run **AchievementDesk-1.1.0-Setup.exe** to install for the current Windows
user, with a Start menu shortcut and optional desktop shortcut. Administrator
access is not required. The app does not open automatically after installation
unless you select that option. Uninstalling retains local preferences and history.
The portable ZIP remains available and uses the same local data folder.

## Run the portable build

1. Extract the entire Windows ZIP into a writable folder.
2. Start Steam, sign in and stay online.
3. Open **AchievementDesk.exe**. Keep **AchievementDeskWorker.exe** and
   **_internal/** together with it.
4. Wait for your Steam library to be detected. Click a game (installed or not)
   to load its achievements. Enter also activates a keyboard-selected game.
5. Use each achievement's switch: **ON** for unlocked, **OFF** for locked.
   The switch changes your draft; a blue label identifies the pending operation
   and shows the current saved state. Switching back removes that pending change.
6. Choose **Review changes**, inspect the game, account and all pending changes,
   then explicitly choose **Apply to Steam**.

Changes are never sent by selecting rows, searching, switching filters or merely
loading achievement data. The manager does not launch the game's executable.
Close the game itself before using the manager.

## A quieter workspace

The dark Qt interface follows UniversalSaveEditor's current visual language:
neutral charcoal surfaces, blue accents, a shared-style header and rounded panels.
Each achievement shows its name, description and unlock date when available.
The switch shows the desired state; a blue pending label distinguishes an
unsubmitted change from the current saved state.

The normal workspace shows only the library, search/filters and achievement
switches. The review bar appears only when changes are queued. Secondary tools
are available from menus:

- **Library tools** (bottom of the sidebar): refresh library, open by App ID
  and update the game catalog.
- **Game tools** (above the open game's overview): refresh achievements, export
  the saved state and open the official Steam page.
- **Settings** (top-right header): display details, density, reduced motion,
  optional public artwork, update checks, About and keyboard shortcuts.
- **All games** (below library search): all, installed, not installed, favorites or recent.
- **Browse library**: an embedded alphabetical game list with search, filters,
  paging and favorites. All shows every initial; # includes numbers/other scripts.
  Accented Latin initials are matched to their base letter (e.g. É → E).
  A letter filters the whole matching library, not just the current page.
- **Back to achievements** / **Esc**: return to the current game without losing
  pending changes. Opening the same game reuses its loaded achievement view.
- **Favorite**: add/remove the current game from the account's favorites.
- **Sort**: Steam order, name, unlock date or rarity. Unknown rarity/dates stay last.
- **Activity history**: requested changes and recorded outcomes for the connected account.
- **N selected** (beside the Achievements heading, only after selecting rows):
  prepare batch unlocks/locks or clear the selection without discarding drafts.

Changes across searches and pages stay in the same review queue. **Discard**
returns every switch to the last saved state without connecting to Steam.
Use search or the locked/unlocked/pending filters to narrow the list. Filters
for Locked and Unlocked refer to the saved state, not an unsubmitted draft.

Lists are paginated at 25 achievements per page to keep large games responsive.
Searching and filtering cover the full loaded list, not just the current page.
Click a row to select it, or Ctrl+click to select multiple. **Unlock selected**
and **Lock selected** in the selection menu prepare changes for the selection.
Tab and Space can also be used to operate the achievement switches.

Hidden achievement names and descriptions stay concealed unless **Show hidden
achievement details** is enabled in Settings, including in the review dialog.

### Workspace improvements in 1.1

The compact header shows the selected game's small Steam icon, name and progress,
leaving more space for achievement rows. Each row's information button, a double
click or **Alt+Enter** on a selected row opens a read-only details panel inside
the editor. It shows the full description, larger image, saved/pending state,
date when supplied, rarity and a copyable API ID. Hidden details and IDs stay
concealed until enabled in Settings. Close the panel with its × button, or Esc
while focus is inside it.

**Undo** above the list and **Ctrl+Z** restore the previous pending edit. One
selection batch or set preparation is one undo step. Discarded drafts can also
be undone. Undo never submits a Steam operation and is cleared on a fresh read,
account/game switch or apply. Steam restrictions are checked again when restoring
drafts. In a text field, Ctrl+Z undoes typing instead.

Search matches are highlighted literally in titles/descriptions and game lists,
including Unicode text; game text is not interpreted as HTML. An empty filtered
result offers **Clear filters**, preserving the pending review queue.

The last search, filter, sort, page and scroll offset are stored per account and
game (up to 200 recent game views). They restore after the account is verified
and achievements are read. Draft changes and undo history are not persisted.
Successful saves use a brief inline notice with **View activity**. Partial,
rejected or uncertain outcomes remain visible with counts and require attention.
Technical messages are under **Show details**; status/progress and errors remain
visible while browsing the library too.

### Artwork, preferences and history

Images are loaded only for visible games and achievement pages, with four
background workers and a local cache. Downloads are decoded before caching.
Corrupt cache entries are replaced; failed requests can retry after a short
cooldown. A failed refresh retains valid cached metadata. Missing variants
never borrow another achievement's artwork, and secret images stay concealed. Game icons use the existing read-only client
metadata query for the standard icon hash, then Steam's local library cache or
its public CDN. They are small list icons, not resized store covers. Missing hashes
can fall back to the public app hub's small icon; rate-limited hub requests back
off without blocking the library. The app also uses public global achievement
pages and GetGlobalAchievementPercentagesForApp. It sends App IDs,
not account IDs or credentials, for presentation requests. No API key is needed.
If Steam does not expose an image or percentage, the app uses a neutral fallback.
These public web formats can change; **Game tools → Refresh artwork & rarity**
clears failed-request cooldowns and fetches fresh metadata. Missing image tooltips
explain how to retry. Incomplete metadata is cached briefly so a failed first
request cannot hide images for a full day.
Disable public artwork/rarity requests in Settings to use only local/native data.

Favorites, recent games and the last selected game are scoped to the Steam account.
The last selection is highlighted after discovery; it does not automatically open
a game-specific achievement session. Preferences and window size are local.

Activity is recorded before submission and starts as **unconfirmed**. Only the
worker's verified result updates that record. A crash or lost reply leaves it
unconfirmed; it is never presented as a successful Steam save. History is limited
to the most recent 1,000 activities per account and can be exported as JSON.
Cancelling a read never cancels an apply operation or sends achievement changes.

Local data lives under `%LOCALAPPDATA%\AchievementDesk`: `workspace.json`,
`history/`, `public-cache/` and `snapshots/`. Nothing from these folders is included
in a distributable. Synthetic demo mode uses a temporary, separate workspace.

### Updates

Settings can check public GitHub releases from a configured `owner/repository`.
It compares version tags, ignores drafts, and offers a release-page link. It never
automatically downloads or runs an installer. Stable builds do not offer previews.

**Source repository:** https://github.com/DanCarrillo11/AchievementDesk.
The stable release channel is configured by default. Older empty settings migrate
to this repository; a custom repository setting is preserved. Checks are manual,
and stable installations ignore preview tags even if a release is mislabelled.
See [Release instructions](RELEASES.md).

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+B | Browse library |
| Ctrl+F | Search current view |
| Ctrl+D | Favorite selected/current game |
| Ctrl+H | Activity history |
| Ctrl+R | Refresh current view |
| Ctrl+Enter | Review pending changes |
| Ctrl+Z | Undo pending edit, or typing in a text field |
| Alt+Enter | Open selected achievement details |
| Tab / Space | Navigate / toggle switches |
| Ctrl+click | Select multiple achievements |
| F1 | Show shortcut help |
| Esc (in library) | Return to achievements |

### Achievement sets, trophies and compatibility

Open a game, then choose **Sets & trophies** below its overview. The embedded
page shows Steam's public set definitions, current achievement progress and the
completion flags Steam reports for this account. **Show achievements** filters
the editor to a set; **All sets** clears that filter. **Prepare remaining unlocks**
only creates drafts for the existing review and explicit apply workflow.
Archived achievements and sets are excluded from unlocks. DLC sets require
Steam to confirm account availability before their unlocks can be prepared.

Steam controls trophy awards. Completed sets can stay completed after new
achievements are added; relocking achievements does not guarantee trophy removal.
Current progress and pending drafts never create a trophy flag in this app.
**Unconfirmed** means Steam did not supply a usable flag, including private
profiles, missing data or different schema versions. It never means "not earned".
Use **Refresh from Steam** after changes; Steam's public data may update later.

Completion checks use Steam Community's server-rendered achievement data. They
send your Steam account ID and App ID directly to Steam, without cookies,
credentials or an API key. They are separate from artwork requests and can be
disabled in Settings. Account completion is held in memory, never bundled or
uploaded to another service. Public page formats can change; failures leave
completion unconfirmed and keep the native achievement editor available.

The library's status, dots, tooltips and filters show evidence for the signed-in
account. Opening a game checks readability; only verified apply results record
unlock/relock support. The status button below the game overview shows details.
Games that have not been opened remain **Not checked**. Discovery does not open
every game's achievement session or test writes. A successful operation does not
guarantee every achievement is editable; rejections and unknown results stay
visible. Evidence is saved locally per account and survives restarts.

### Steam's "Running" status

Steam associates each native achievement connection with the selected App ID,
so it may briefly show that game as **Running** even though the game executable
has not opened. The application does not provide a way to suppress that status.

Since 0.1.1, achievement connections exist only while reading, refreshing or applying.
Each helper exits before its result is displayed, including on errors. Searching,
filtering, queueing and reviewing use the loaded snapshot without staying connected.
The verified post-apply rows are reused without opening another session. Steam's
UI may take a moment to notice a closed session. Close older versions of Achievement
Desk before using this one; their persistent connections are not managed by it.

Library detection uses a separate connection with no selected game (App ID 0).
It checks access and names only, never initializes a game's achievement interface,
and cannot use the achievement read/write methods. The connection is released
before the library results are displayed.

To explore synthetic data without contacting Steam, run:

```powershell
.\AchievementDesk.exe --demo
```

## Automatic library detection

The sidebar now checks the signed-in Steam account's access against a bundled
catalog of more than 90,000 public App IDs, plus installed-game manifests.
Games do not need to be installed to appear. Search by game name or App ID;
use **All games**, **Installed** or **Not installed** in Library filter.
An installed manifest from another account is not sufficient to pass the access check.

Choose **Refresh library** after switching Steam accounts or acquiring games.
The old account's library and achievement view are cleared before a new scan.
The account is checked again before loading achievements and before applying edits.
The per-account library is saved locally under `library-cache/` after a successful
scan and loaded only after Steam verifies the active account. Explicit refresh
rescans ownership and installation status. It is never shipped or saved in the
shared public catalog; cached listings do not authorize achievement changes.

The bundled catalog is a snapshot of the public App ID list used by SAM:
https://gib.me/sam/games.xml. Choose **Update game catalog** in Library tools to fetch its current
version, then **Refresh library**. A failed download leaves the existing catalog
intact; an invalid cached catalog falls back to the bundled snapshot. Only public
App IDs are downloaded. Your Steam ID, library and achievements are not sent to
that host. This is an external third-party catalog, not a Valve service.

New games or titles missing from that catalog can still be opened manually by
App ID. Games with missing local metadata are shown as **Steam App <ID>**.
The list represents access reported by Steam; it is not proof of editable achievements.
Games without achievements may appear and will return an empty achievement list.

The app does not ask for credentials or an API key.
Game-provided achievement descriptions follow Steam's game/interface language.

## What is implemented

- Read achievement names, descriptions, API IDs, states and unlock dates.
- Search; filter locked, unlocked or pending rows; conceal hidden details.
- Queue individual or multiple selected achievements for unlocking or locking.
- Review all pending changes, including changes hidden by filters.
- Check the App ID, account, online connection and current states before writing.
- Save a local reference snapshot before any mutation; abort if it cannot be saved.
- Submit a batch once, wait for Steam's acknowledgement and read states again.
- Report confirmed, rejected, partial and unconfirmed outcomes separately.
- Export the current state as JSON and open the official achievement page.
- Run a completely separate synthetic demo mode.
- Connect to Steam only for individual operations and release the session afterward.
- Detect accessible installed and uninstalled games for the current Steam account.

## Current limits

Achievement sets and Steam-reported completion are supported in the Qt frontend.
There is no independent trophy unlock/remove switch. The overview percentage is
the flat achievement list; official completion appears separately in Sets & trophies.
Private profiles can prevent completion verification. End-to-end trophy awarding
and removal have not been validated by changing the user's live account.

Protected/server-controlled achievements may reject client changes. No attempt
is made to bypass those restrictions. Some games may award an achievement again
from their own saves or statistics. Game statistics are not edited here.

Snapshots are references, **not reversible backups**. They cannot restore old
unlock timestamps, trophy history or game state. The app has no automatic
snapshot-import or replay function. A failed/timeout response can follow partial
changes, and Steam can persist cached changes later. Check Steam before retrying.

The native adapter uses versioned Steam client interfaces, not a supported
cross-game Steam Web API. Steam updates can break compatibility. Native calls run
in a separate helper process so an interface failure does not crash the window.

Game artwork and achievement icons are downloaded on demand, rather than bundled. No claim of
universal game compatibility or platform approval is made.

## Local data

Reference snapshots are saved under:

```text
%LOCALAPPDATA%\AchievementDesk\snapshots
```

Demo snapshots use a separate `demo-snapshots` folder. Snapshots contain the Steam
account ID, game ID, achievement states and requested changes. They remain local;
the app has no telemetry or upload service. **Apply to Steam** sends changes
through Steam. Opening the official page opens the default browser.

## Development

Python 3.11+ x64 on Windows and PySide6 Essentials (see requirements.txt).
The Steam backend uses the standard library and loads `steamclient64.dll` from
Steam's install folder. No Valve DLL or Windows font is distributed with the app.
The portable build includes the Qt runtime; end users do not install Python or Qt.

The active frontend is `modern_ui.py` with components in `design.py`. The older
Tk prototype (`ui.py` and `widgets.py`) is retained in source for reference and
regression coverage; it is not launched or bundled in the portable build.

```powershell
python -m pip install -r requirements.txt
python app.py --demo
python app.py
python -m unittest discover -s tests -v
```

Build (PyInstaller 6.22.3 was used):

```powershell
python -m pip install pyinstaller==6.22.3
python tools/build_assets.py
python -m PyInstaller --clean --noconfirm AchievementDesk.spec
```

Copy README.md, LICENSE and THIRD_PARTY_NOTICES.txt alongside the generated
executables when distributing. Distribute the complete `dist/AchievementDesk`
folder, not the front-end executable alone. PyInstaller's shared files retain
their bundled license information under `_internal`.

## Validation evidence

- The automated suite covers: plans, stale state, account mismatch, snapshot
  failures, rejected/partial/unconfirmed operations, manifest discovery and the
  worker protocol using synthetic data, withdrawn-window UI checks and on-demand
  connection cleanup after success, failure and account changes, catalog parsing
  and fallback, library discovery and routing of uninstalled games, draft switches,
  switch-back/discard behavior, disabled switches, pagination and full-list search.
  This includes account-scoped favorites/history, durable preferences, cancellation,
  retry, public metadata parsing/cache, sort behavior, embedded navigation, A–Z
  filtering, 100-game pagination, minimum-size layout, icon sources and review/release checks.
  New completion checks cover persistent completion with incomplete current progress,
  unknown/private flags, wrong-account/schema rejection, DLC/archive restrictions,
  draft-only set actions, stale asynchronous responses and account-scoped compatibility.
- Actual Qt interface renders were inspected using synthetic data on Qt's
  offscreen platform. Qt visual checks did not use the interactive desktop.
- The packaged 0.8.0 Windows frontend rendered successfully offscreen, and
  all 11 transport checks passed with the packaged synthetic helper.
- The final packaged public-preview check retrieved 6 real Steam list icons and 6
  achievement images, rendered every new view offscreen and used no native Steam
  session. Executable version metadata was inspected. The optional Achievement
  Desk installer was compiled but was not run on the user's desktop.
- A read-only native check against one installed game returned 13 achievements.
- The user reported a successful real unlock in I Have No Mouth, and I Must Scream
  with version 0.1.0. This is user-reported evidence for one case, not broad coverage.
- Version 0.1.1's lifecycle changes were validated with automated tests and the
  packaged synthetic worker, without connecting to the user's live Steam session.
- Version 0.2.0's read-only library scan detected 553 accessible apps in the active
  account, including 550 not installed. Those are observed counts for one account,
  not a guarantee of universal catalog coverage. No personal library is included
  in either distributable.
- A user-authorized real relock was confirmed after the 0.8.0 build: achievement
  `Theyellowhysterical` in I Have No Mouth, and I Must Scream (App ID 245390).
  Steam acknowledged the save; a new worker process read it as locked with a zero
  unlock timestamp. All 12 other achievement states and timestamps were unchanged.
  This verifies one operation, not universal compatibility. See the
  [redacted verification report](validation/relock-2026-10-30.md).
- End-to-end trophy awards/removal remain unverified.
- Read-only 0.8.0 checks retrieved Portal 2's two public sets and account completion
  flags. App ID 251850 returned one set without a completion flag, correctly left
  unconfirmed. No credential or cookie was read and no achievement was changed.
- Earlier automated and build checks did not modify live achievements or trophies.
  The subsequent user-authorized real relock is documented separately above.

## Roadmap

1. Expand deliberate real-operation validation across additional games and accounts.
2. Validate trophy-award timing on a deliberately selected game, separately from
   current achievement progress and without assuming that relocking removes trophies.
3. Expand real compatibility evidence across game-specific achievement restrictions.
4. Expand Windows hardware/display coverage while maintaining the stable update channel.

## References

- [Valve: Stats and Achievements](https://partner.steamgames.com/doc/features/achievements)
- [Valve: ISteamUserStats](https://partner.steamgames.com/doc/api/ISteamUserStats)
- [Valve: Achievement Sets announcement](https://steamcommunity.com/games/593110/announcements/detail/710037059469839142)
- [Steam Achievement Manager](https://github.com/gibbed/SteamAchievementManager)

Source license: MIT, except the adapted SAM.API portions, which retain their zlib
notice and conditions. Steam and game names are their owners' trademarks.
