# Achievement Desk v0.8.2-preview — Faster Steam library loading

This Windows x64 preview adds an **account-specific library cache**, so Achievement Desk does not rescan thousands of Steam App IDs on every launch.

## What's new

- **Remember discovered games:** after a successful first full scan, Achievement Desk saves each game's Steam App ID, name, installed status, and icon hash locally.
- **Faster launches:** subsequent starts verify the current Steam account and load its saved game list instead of repeating the full catalog scan.
- **Manual refresh:** choose **Library tools → Refresh library**, or press **Ctrl+R** on the library page, to check for newly acquired, removed, installed, or uninstalled games.
- **Separate accounts:** each Steam account has its own snapshot, preventing one account's library from appearing under another.
- **Safer storage:** snapshots are validated and written atomically. Invalid or damaged snapshots trigger rediscovery; failed refreshes do not overwrite the prior valid snapshot.
- **No achievement changes:** the cache only stores display metadata. Ownership checks and achievement reads/writes still go through Steam.

## Downloads

- **AchievementDesk-0.8.2-preview-Setup.exe** — Windows per-user installer.
- **AchievementDesk-0.8.2-preview-Portable.zip** — portable Windows x64 application; extract the complete folder before launching.

The first launch still needs to scan the Steam game catalog. Steam must be running and signed in so the app can verify which account owns the saved library.

## Compatibility and safety

This is an **early preview, not a stable release**. Windows x64 and an online, signed-in Steam desktop client are required for live account operations; no Steam password or API key is requested. A saved game listing is not proof that a game still belongs to the current account or that its achievements are editable.

The automated suite covers the account-scoped cache, corrupted snapshots, explicit refresh, and UI behavior, but it does not prove compatibility with every Steam game or test a full installer upgrade on your computer. The app is independent and unaffiliated with Valve.

Achievement changes continue to require explicit review and confirmation. Some protected or server-controlled achievements may reject writes. Reference snapshots do not restore historical unlock dates, trophy history, or game saves.
