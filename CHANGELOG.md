# Changelog

## 0.8.1-preview

- Replace the shield/check application icon with the user-supplied trophy and
  sparkle, recolored in light blue and soft white on charcoal for the dark UI.
- Export the committed logo master at seven Windows icon resolutions. Use the
  same branding in the header, executable, installer and README, with refreshed
  screenshots of the actual Qt interface.

## Unreleased — repository preparation

- Prepare the AchievementDesk source repository with an English README, real UI
  previews, architecture/privacy/troubleshooting guides and contribution policies.
- Add Windows test automation for Python 3.11/3.14, issue forms, dependency updates
  and a manually triggered portable-build workflow. No public downloads or release
  are published by the initial source upload.
- Exclude private account data, research folders, environments and build outputs
  from Git. Include repository documentation/configuration in future source archives.

## 0.8.0-preview

- Add an embedded achievement-set/trophy page with Steam-reported completion,
  current set progress, DLC availability, archived-achievement handling and UTC
  completion dates when provided. Missing/private/mismatched data stays unconfirmed.
- Filter the editor by set and prepare remaining eligible unlocks as drafts for
  the existing explicit review. Recheck known restrictions at submission; no new
  native write method or direct trophy manipulation is introduced.
- Keep persistent Steam completion separate from current achievement percentages.
  A 100% list or a pending draft never invents an official trophy.
- Add account-scoped compatibility evidence, library status/dots/tooltips/filters
  and a detail button. Reads never claim edit support; confirmed, rejected and
  unknown write results are recorded separately. No automatic write probes.
- Add an independent Settings preference explaining Steam completion requests:
  account/App IDs go directly to Steam Community without cookies or credentials.
  Completion results stay in memory; local compatibility evidence survives restarts.

Validation: 163 automated tests, real Qt offscreen renders and read-only Steam
completion checks for two fixed games. Portal 2 exposed two sets and account flags;
App ID 251850 exposed one set without a completion flag. No live achievements
or trophies were modified. Trophy-award timing/removal remain unverified.

Post-build validation, 2026-10-30: a user-authorized real relock of
`Theyellowhysterical` in I Have No Mouth, and I Must Scream (App ID 245390) was
acknowledged by Steam and confirmed by a new worker process. All 12 other
achievement states/timestamps were unchanged. Local history and compatibility
were updated. See `docs/validation/relock-2026-10-30.md` for scope and evidence.
The existing release binaries/archives were not changed by this validation.

## 0.7.0-preview

- Replace the separate cover-gallery dialog with a reusable page in the main
  window, with Back to achievements and Escape navigation.
- Add All / # / A–Z initial filters, composed with full-library search and
  installed/favorites/recent filters. Normalize accented Latin initials.
- Increase library pages from 24 to 100 games, using responsive compact rows
  in multiple columns and preserving full names in tooltips.
- Replace game covers with the standard small Steam list icons. Read the icon
  hash through the existing read-only metadata interface and reuse Steam's local
  image cache where possible. Use the CDN if needed, with a public app-hub
  fallback for missing metadata and backoff on rate limiting.
- Keep draft achievement changes while browsing. Reopening the current game
  returns to its loaded view; opening another game still requires discarding drafts.
- Make search/refresh/favorite shortcuts act on the visible view.

Validation: 139 automated tests; offscreen rendering of the embedded library,
letter filtering and minimum window size with real Steam icons and synthetic states.
A read-only App ID 0 check confirmed standard icon hashes without initializing
game achievement interfaces. No real achievement was modified.

## 0.6.0-preview

- Add a paginated cover gallery while retaining the compact sidebar.
- Load optional public Steam covers, achievement icons and global rarity with a
  bounded background queue, cache, neutral fallbacks and a request preference.
- Persist favorites, recent games and last selection per account; remember window
  size, library filter, sorting, hidden details, row density and reduced motion.
- Add name/date/rarity ordering without dropping pending changes.
- Replace the text-only review with achievement icons and Before/After columns.
- Record durable account-scoped activity before submission; update it only with
  verified results. Preserve unknown outcomes as unconfirmed and support export.
- Add read progress, safe read cancellation and explicit retry. Applying cannot
  be cancelled through the UI. Keep native state/write handling unchanged.
- Add original multiresolution Windows branding, executable version metadata,
  keyboard shortcuts and an optional non-admin installer alongside the portable ZIP.
- Add explicit GitHub release lookup. No public repository/channel is configured
  or claimed to exist; no code is automatically downloaded or launched.

Validation: 123 automated tests, packaged synthetic helper checks, actual offscreen
Qt renders of the gallery/workspace/review/settings/history/minimum window, and
public-only Steam artwork/percentage checks. No real achievement was modified.

## 0.5.0-preview

- Adopt a dark companion design based on UniversalSaveEditor's current visual
  language: charcoal surfaces, blue controls, rounded panels and a top app header.
- Separate Library tools, Game tools and display Settings by scope.
- Show batch operations only when achievements are selected. Clearing selection
  preserves queued drafts; the review footer appears only for pending changes.
- Add saved-state ornaments and distinguish drafts with a blue edge and label.
- Use plain text for achievement labels, including names containing markup.
- Preserve the Steam backend, review consent, snapshots and account checks.

Validation: 95 automated tests, including 29 current Qt UI checks. Visual checks
use real widgets rendered offscreen with synthetic data, including selected rows,
pending changes, review consent, Settings and the minimum window size.
The packaged Windows frontend passed offscreen rendering; all 11 transport checks
passed against its packaged synthetic helper. No live achievement was modified.

## 0.4.0-preview

- Replace the shipped Tk frontend with a new PySide6/Qt workspace.
- Introduce a light Apple-inspired visual direction, rounded controls, quiet
  typography, a restrained sidebar and green achievement switches.
- Move library refresh, catalog updates, App ID entry and hidden details into Settings.
- Move export, achievement refresh, Steam links and batch tools into Game options.
- Show the review/discard bar only when pending changes exist; reuse visible
  row widgets to preserve keyboard focus and switch animation.
- Keep the existing Steam backend, account verification, library discovery,
  snapshots and reviewed submission workflow.
- Add offscreen rendering of actual Qt widgets with synthetic data for visual QA.

Validation: 90 automated tests, including 24 current Qt frontend tests. Actual
offscreen renders were visually inspected; no live Steam operation or interactive
desktop control was performed for this redesign.
The packaged Windows frontend also passed offscreen rendering, with 11
transport checks passing against the packaged synthetic helper.

## 0.3.0-preview

- Redesign the desktop workspace with a compact Steam-inspired navy/blue theme.
- Replace table rows with clear achievement cards and ON/OFF draft switches.
- Show descriptions, saved states, unlock dates and amber pending-change labels.
- Preserve explicit review/apply and reset drafts when a switch is returned to its saved state.
- Add 25-card pagination while keeping search, filters and the review queue global.
- Preserve multi-selection and batch preparation; enable controls only when applicable.
- Keep hidden names concealed in the review dialog unless explicitly revealed.
- Pin review confirmation/apply controls using a resizable grid layout.

Validation: 66 automated tests. UI checks used withdrawn windows and synthetic
data; no real Steam connection, desktop control or achievement write was performed
for this interface update.

## 0.2.0-preview

- Detect the active account's accessible games using a bundled public App ID
  catalog and local Steam ownership checks, including uninstalled games.
- Resolve names from Steam metadata and include IDs in library search/list entries.
- Add installed/not-installed filters, library refresh and explicit public-catalog updates.
- Keep library scans in App ID 0 without creating a game achievement interface.
- Clear old account views on library refresh; verify identity before opening or writing.
- Retain manual App ID entry for titles not yet included in the catalog.

Validation: 54 automated tests; read-only discovery found 553 accessible apps,
550 uninstalled, in the active account. No achievement was modified.

## 0.1.1-preview

- Close real Steam helper processes immediately after each read/apply operation,
  including error paths. Browsing and reviewing no longer keep a native session idle.
- Reuse the states already read during post-apply verification rather than
  automatically opening another connection.
- Recheck the signed-in account when reconnecting before applying a reviewed batch.
- Explain that Steam may show a game as Running during a native API operation;
  the manager does not launch the actual game and cannot suppress Steam's status.
- Add regression coverage for session cleanup and the absence of automatic reconnects.

Validation: 36 automated tests; packaged helper tested using synthetic data.
No live Steam operation was performed for this update.
