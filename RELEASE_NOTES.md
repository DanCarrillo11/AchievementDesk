# Achievement Desk 1.2.0 — Clear loading and numbered pages

## Fixed achievement loading

Opening a game now shows **Loading achievements…** with an indeterminate progress
indicator and the selected game name. Pending, cancelled and failed reads are
separate from a successful empty response. **No achievements returned** appears
only when Steam finishes a successful read with no achievements. Unknown apply
results ask for a reload rather than presenting a false empty game.

Refreshing an already loaded game keeps its rows visible and disables switches
until the operation finishes. Actions for a previously open game stay disabled
while a different game is being read.

## Numbered game-library pages

- Jump directly to a page inside the current letter, search and library filter.
- The current page is highlighted. First/last pages and nearby numbers stay
  visible; ellipses keep long ranges compact.
- Previous/Next navigation and the range/page count remain available.
- Each page still contains up to 100 games. Searching/filtering recalculates the
  page numbers and starts at page 1; browsing preserves pending achievement drafts.

## Downloads and upgrade

- **AchievementDesk-1.2.0-Setup.exe** — per-user Windows x64 installer.
- **AchievementDesk-1.2.0-Portable.zip** — extract the complete folder and run
  AchievementDesk.exe; keep its helper and `_internal` folder together.

Close the previous app before upgrading. Setup can update the existing install;
portable users should extract into a fresh folder. Local preferences, favorites,
history and library cache stay in the same data folder. Python is not required.

Automated checks cover slow/failed/cancelled reads, real empty responses, unknown
outcomes, filtered page jumps and small-window layouts. The release workflow also
checks frozen startup, clean installation, upgrade from checksum-pinned 1.1.0,
retained local data and uninstallation. These checks use synthetic data and do
not change a live Steam account.

Existing compatibility limits apply: protected/server-controlled achievements
can reject writes, and Steam controls completion trophies. Reference snapshots
cannot restore historical dates or trophy history. Binaries are unsigned.
