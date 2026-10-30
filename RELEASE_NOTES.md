# Achievement Desk v0.8.1-preview

First public Windows x64 **preview** of Achievement Desk, a desktop workspace for browsing Steam games and reviewing achievement unlock/relock changes before applying them.

## Highlights

- Browse accessible Steam games with search, A–Z filters, favorites, and recent games.
- Review individual achievement changes and observe confirmed, rejected, partial, or unconfirmed results.
- Explore Steam-reported achievement sets and completion information; missing and private data remain unconfirmed.
- Updated trophy-and-sparkle application branding and a compact dark interface.
- A demo with synthetic account data is available without signing into Steam.

## Downloads

- **AchievementDesk-0.8.1-preview-Setup.exe** — per-user Windows installer.
- **AchievementDesk-0.8.1-preview-Portable.zip** — portable build (extract before launching).

The source code remains publicly available in this repository and GitHub's automatically generated source archives.

## Compatibility and safety

This is an **early preview, not a stable release**. Windows x64 and a signed-in, online Steam desktop client are required for live account operations. The application does not ask for a Steam password or API key.

The repository documents automated tests, synthetic/offscreen interface checks, and one explicitly authorized real achievement relock. That evidence does not establish general compatibility with all games. Some achievements are server-controlled or protected and may reject edits. Achievement sets and trophies are managed by Steam, not by this application.

Changes are only sent after explicit review and confirmation. Local snapshots are references, **not** backups of achievement timestamps, trophy history, or game save data. Test with caution and understand the effects before applying changes.

Achievement Desk is an independent project, unaffiliated with Valve. See the repository README, troubleshooting guide, license, and third-party notices for details.
