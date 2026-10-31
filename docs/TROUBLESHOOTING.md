# Troubleshooting

## Steam connection or library unavailable

Start the Windows Steam client, sign in and stay online. After changing accounts
or acquiring games, choose **Library tools → Refresh library**. Detection checks
account access against a public App ID catalog and installed manifests; it does
not prove that every game's achievements can be edited.

For a missing game, update the public catalog and refresh the library, or use
**Open game by App ID**. A successful access check is still required. Games do
not have to be installed. Games without achievements can return an empty list.

## Steam briefly shows a game as Running

The achievement helper connects using that game's App ID. Steam can show Running
while that connection exists even though no game executable was launched.
Reads/applies release the helper afterward. Close old app versions before using
this one, and allow Steam a moment to update its displayed state.

## Changes rejected or unconfirmed

Some achievements are server-controlled or otherwise restricted. Archived
achievements cannot be newly unlocked; DLC sets require eligible account access.
The application does not bypass these restrictions or edit underlying game stats.

If an apply result is partial or unconfirmed, inspect Steam before retrying.
Cached changes can persist later; do not assume rollback. The activity history
records the requested operation and its known outcome. A game can re-award a
relocked achievement from its own save or statistics when played again.

## Trophy missing or completion unconfirmed

Open **Sets & trophies** and choose **Refresh from Steam**. The overview's
achievement percentage is separate from Steam's persistent set completion.
Private profiles/game details, unavailable public data or changed schema versions
can prevent a confirmed trophy flag. No password or API key is needed or requested.

Steam controls awards and persistence. A previously completed set can stay
completed after new achievements are added. Relocking achievements does not
guarantee trophy removal. **Prepare remaining unlocks** creates drafts for the
normal review process; it does not directly award a trophy.

## Compatibility status is Not checked

Open the game to check readability. Confirmed write evidence is recorded only
after an actual reviewed operation, separately for unlock/relock directions.
The app does not test compatibility by silently changing achievements.
Hover a library entry or click its compatibility status for the evidence.

## Artwork or rarity unavailable

Steam may omit images/percentages or temporarily limit requests. Neutral icons
are expected when data is missing. Check the artwork preference and use
**Game tools → Refresh artwork & rarity**. Achievement editing does not depend
on optional artwork requests.

## Portable or installation problems

Download setup or the portable ZIP from the official
[releases page](https://github.com/DanCarrillo11/AchievementDesk/releases/latest).
Extract the entire portable archive, keeping `AchievementDesk.exe`,
`AchievementDeskWorker.exe` and `_internal/` together. Setup installs for the
current user. Python is not required for either download. See
[release preparation](RELEASES.md) for source builds and verification details.

## Reporting a problem

Include the application version, Windows version, Steam stable/beta channel,
public game App ID, exact error and minimal reproduction steps. Remove account
IDs, personal paths, credentials and private library details from evidence.
See [security reporting](../SECURITY.md) for sensitive issues.


## Missing achievement artwork

Secret achievement images stay concealed until **Settings → Show hidden
achievement details** is enabled. For other missing images, enable public
artwork in Settings and choose **Game tools → Refresh artwork & rarity**.
Failed image requests release their pending state; normal retries use a short
cooldown, while manual refresh clears it. Corrupt cached images are downloaded
again, and an unavailable locked/unlocked image is left neutral. Images are
optional and do not determine whether Steam accepts an achievement change.

## Updating from a preview

Close Achievement Desk and run the new setup. For portable updates, extract to a
new folder instead of mixing runtime files from different versions. Your data
stays under `%LOCALAPPDATA%/AchievementDesk`. The official update channel is
configured automatically; use **Settings → Updates → Check for updates**.
