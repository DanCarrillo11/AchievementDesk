# Privacy and local data

Achievement Desk does not request a Steam password, browser login cookie or API
key. It has no telemetry or account-upload service.

## Local files

Real-account data is stored in `%LOCALAPPDATA%\AchievementDesk`:

| Path | Contents |
| --- | --- |
| `workspace.json` | Preferences and per-account favorites, recent games and compatibility evidence |
| `history/` | Requested operations and confirmed, partial, rejected or unknown outcomes |
| `snapshots/` | Account/game identifiers, achievement states and requested changes before writes |
| `public-cache/` | Optional cached Steam artwork and public presentation metadata |

The detected library is kept in memory. Account completion responses are held in
memory. Demo mode uses a separate temporary workspace. Local reference snapshots
are evidence rather than reversible backups.

Do not publish these files or attach the entire folder to an issue. The supplied
`.gitignore` excludes them, along with private research and build outputs.

## Network requests

| Action | Destination and information |
| --- | --- |
| Native read or reviewed apply | The signed-in local Steam client; Steam handles account synchronization |
| Optional artwork and rarity | Public Steam pages/CDN/API; App IDs and artwork filenames, without account IDs |
| Optional set/completion check | Steam Community; account ID and App ID, without cookies or credentials |
| Update game catalog | `gib.me/sam/games.xml`; public App ID catalog request, without account details |
| Explicit update lookup | GitHub API for the configured public repository |
| Open Steam/release page | The default browser opens the selected link and uses its own browser/session settings |

Artwork and completion checks have independent Settings switches. A private
Steam profile or game-details setting can prevent completion verification; the
app leaves missing flags unconfirmed instead of requesting credentials.

## Removing data

Close the application before manually removing its local data folder. This
removes preferences and local evidence; it does not undo Steam changes.
The optional installer retains local data when uninstalling. Portable and
installed copies use the same local data folder.
