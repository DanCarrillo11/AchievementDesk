# Achievement Desk 1.1.0 — A clearer workspace

This stable update improves everyday browsing, reviewing and navigating while
retaining the dark interface and explicit approval before Steam changes.

## What's new

- **Compact game header:** Steam list icon, game name and progress use less space.
- **Embedded achievement details:** open a row's information button, double-click
  it or use Alt+Enter to see full descriptions, artwork, rarity, dates and Copy ID.
- **Undo pending edits:** Undo or Ctrl+Z restores individual edits, selected
  batches, set preparations and discarded drafts before submission. Search fields
  retain their normal text undo. Read/apply/account/game boundaries clear history.
- **Remember your place:** search, filter, sort, page and scroll position restore
  separately per game/account after a verified read. Drafts are not saved.
- **Literal search highlights:** matching text is highlighted in games and
  achievement titles/descriptions; Clear filters recovers empty results.
- **Quieter feedback:** confirmed saves use brief inline notices. Errors and
  uncertain results keep clear explanations, with technical details on demand.
  Progress and errors also remain visible in the library view.
- **Visual polish:** stronger secondary-text contrast, consistent small controls,
  wrapped metadata and layouts verified at 1020 × 760 with the details panel open.

## Downloads and upgrading

- **AchievementDesk-1.1.0-Setup.exe** — per-user Windows x64 installer.
- **AchievementDesk-1.1.0-Portable.zip** — extract the complete folder and start
  AchievementDesk.exe; keep its helper and `_internal` folder together.

Close Achievement Desk before running setup over the existing installation.
Extract portable updates into a new folder. Existing preferences, favorites,
library cache, activity and reference snapshots remain in the same local data
folder. Python is not required. Live Steam operations require the signed-in
desktop client to be online; games need not be installed.

## Verification and compatibility

Automated checks cover undo boundaries, hidden detail privacy, account-scoped
view restoration, literal highlighting, nonblocking results and small-window
layouts. Publication also verifies the frozen interface/helper, a clean setup,
upgrade from the checksum-pinned 1.0.0 installer, retained local data and uninstall.
Screenshots use actual app widgets/public artwork with synthetic account states.

Steam continues to control protected achievements and completion trophies. Undo
edits only unsubmitted drafts; it cannot reverse saved Steam changes, restore old
unlock dates or remove trophy history. Missing/private completion stays
Unconfirmed. Binaries are unsigned. Achievement Desk is independent of Valve and
Steam Achievement Manager.
