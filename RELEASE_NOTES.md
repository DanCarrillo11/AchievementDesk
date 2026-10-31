# Achievement Desk 1.0.0

The first stable Windows x64 release of Achievement Desk: a focused desktop
workspace for managing Steam achievements with reviewed changes and clear results.

## Included

- Embedded A–Z game library with search, 100-game pages and Steam list icons.
- Account-specific saved libraries, favorites and recent games.
- Achievement switches, filters, sorting and an explicit before/after review.
- Confirmed, rejected, partial and unconfirmed results with local activity history.
- Achievement sets and Steam-reported completion, with eligible set unlock drafts.
- Dark interface, compact rows, keyboard shortcuts and remembered preferences.

## Stable release improvements

- The official update repository is configured automatically, including migration
  from empty preview settings. Stable builds ignore preview updates.
- Artwork parsing uses structured API-name associations and supports missing image
  variants without mixing achievements. Corrupt images are replaced, failed
  requests can retry, and valid cached data survives temporary Steam failures.
- The release build checks frozen startup and the synthetic worker, clean setup,
  upgrade from 0.8.2-preview, local-data retention and uninstallation before upload.
- The two downloads are verified in a draft before publication; SHA-256 hashes
  are included below. No Steam account is used by automated publication tests.

## Downloads and upgrading

- **AchievementDesk-1.0.0-Setup.exe** — per-user Windows installer.
- **AchievementDesk-1.0.0-Portable.zip** — extract the complete folder and run
  AchievementDesk.exe; keep its helper and `_internal` folder together.

Python is not required. Steam must be running, signed in and online for live
operations. Games do not need to be installed. Close Achievement Desk before
running setup over an existing installation. Extract portable updates into a new
folder. Preferences, favorites, history and library cache remain in the same
local data folder and are retained on uninstall.

## Compatibility

The owner reports successful use with their tested games. Compatibility remains
specific to the game and achievement: protected or server-controlled achievements
can reject changes. Steam controls completion trophies and their persistence;
relocking does not guarantee trophy removal. Missing/private completion remains
Unconfirmed. Reference snapshots cannot restore old unlock dates, trophies or
game saves. Steam client updates may affect the native interfaces.

No password or API key is requested. This independent app is not affiliated with
Valve or Steam Achievement Manager. Binaries are not code-signed. See the user
guide and stable release scope in the repository for details.
