# Stable release scope — 1.0.0

Achievement Desk 1.0.0 supports its documented Windows x64 workflow: detect the
signed-in account's accessible games, read achievements, prepare drafts, review
changes and report Steam-confirmed, partial, rejected or unconfirmed results.

## Game evidence

On October 30, 2026 the owner reported that the application works correctly with
the games they tested. The report did not specify a complete game/account matrix,
so it is recorded as owner-reported use, not an independent compatibility audit.
The earlier [real relock verification](relock-2026-10-30.md) documents the exact
observed operation and unchanged neighboring achievements.

No automatic compatibility write probes are performed. Live ownership, account,
App ID and current-state checks remain required before an explicitly reviewed
write. Protected or server-controlled achievements may reject client changes.

## Publication gates

The stable release workflow must pass all of these before publishing:

- Automated synthetic/offscreen tests, including account isolation and artwork recovery.
- Exact source, application, Windows executable and installer version agreement.
- Frozen helper version and synthetic protocol tests, plus offscreen GUI startup.
- Valid archives without local account data, research folders or credentials.
- Silent clean installation and startup on a disposable Windows runner.
- Upgrade from the checksum-pinned 0.8.2-preview installer and startup afterward.
- Preserved synthetic settings, history and reference snapshots through upgrade and uninstall.
- Uninstallation removes the executables and bundled runtime.
- Uploaded asset names, sizes and SHA-256 hashes match the verified build.

Pull requests run the build/install gates without publishing. A trusted main
release-request change builds again, creates a draft, verifies its two downloads,
and only then publishes it as stable/latest. Existing published versions are not
overwritten. Tests never connect to a live Steam account or run setup on the
owner's desktop. These checks do not certify every Windows/device configuration.

## Completion and presentation

The app displays Steam-reported completion separately from current progress.
Missing, private or mismatched completion remains **Unconfirmed**. Steam controls
when trophies are awarded and whether they persist; 1.0 does not promise trophy
removal after relocking. Trophy award/removal timing has not been independently
validated by changing a live account.

Artwork is optional. Steam outages or unavailable variants may leave a neutral
icon. Structured parsing, cache validation, short failure cooldowns and manual
refresh keep presentation failures separate from achievement operations.

Code signing is not included in this release. Download hashes are published with
the release notes, and GitHub retains the source tag and build/check history.
