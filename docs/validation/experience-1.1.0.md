# Workspace experience — 1.1.0

The usability update is validated with synthetic data and Qt's offscreen platform.
No native Steam session is used for these checks.

## Covered behavior

- Individual, batch, set and discard edits can be undone before submission.
- Undo is bounded, disabled while busy, scoped to game/account, cleared on fresh
  reads/apply and filtered against current Steam restrictions.
- Ctrl+Z in a search field edits text without restoring achievement drafts.
- Embedded details do not perform backend operations. Concealed names, images
  and API IDs remain hidden, and copying their identifiers is disabled.
- Per-game view settings survive restarts separately per account; malformed
  settings recover, and a new search supersedes a pending scroll restoration.
- Unicode/literal highlighting retains plain text, including markup-like names.
- Empty-result recovery preserves drafts, and artwork refreshes preserve scroll.
- Confirmed results use notices; partial/unconfirmed outcomes remain visible
  without an automatic apply retry. Errors stay visible in the library view.
- The compact header, details and review controls fit the 1020 × 760 workspace.

Public-artwork rendering retrieves six actual Steam game-list icons and six
achievement images for synthetic account states. The new details/search views
are inspected at regular and minimum sizes. The frozen render smoke check opens
details, renders search highlights and verifies minimum-size review controls.

The release workflow gates publication on clean installation and upgrading the
checksum-pinned 1.0.0 setup, followed by startup, data-retention and uninstall
checks. Existing [game validation scope](stable-1.0.0.md) remains applicable;
this update makes no new universal game or trophy-award compatibility claim.
