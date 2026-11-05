# SteamAchievementManager 1.3.0

Achievement Desk is now named **SteamAchievementManager**. The window, Settings,
executable, worker, installer and shortcuts use the new name.

## Library refresh

A blue circular-arrow button beside **All games** rereads the Steam library to
discover newly added or removed games and update installation status. It uses
the existing full-refresh action, including draft confirmation and busy-state
handling. **Library tools → Refresh library** remains available.

## Downloads

- **SteamAchievementManager-1.3.0-Setup.exe** installs for the current Windows user.
- **SteamAchievementManager-1.3.0-Portable.zip** contains the complete application.
  Extract it into a fresh folder and run **SteamAchievementManager.exe**, keeping
  **SteamAchievementManagerWorker.exe** and `_internal` beside it.

## Upgrade from Achievement Desk

Close the previous application and run the new installer. It uses the existing
installation identity, replaces the old executable names and creates renamed
shortcuts. Existing preferences, favorites, activity history, reference snapshots
and library cache stay under `%LOCALAPPDATA%\AchievementDesk`.

The official repository is now `DanCarrillo11/SteamAchievementManager`.
GitHub redirects the previous repository URL, so existing installations can
still discover releases through their saved update settings.

Release checks cover the renamed frozen application and worker, synthetic
library/achievement operations, minimum-size layouts, clean installation and
upgrade from checksum-pinned Achievement Desk 1.2.0 on a disposable Windows
runner. The release includes the existing loading states, numbered library pages,
reviewed achievement changes, completion information and documented game limits.
