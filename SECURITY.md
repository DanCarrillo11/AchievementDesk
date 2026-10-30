# Security

The current code is a preview. A stable-support window has not been established.

## Reporting

If **Security → Report a vulnerability** is available on this repository, use
that private reporting form. Otherwise, open a public issue asking for a private
contact method without including exploit details or private information. Do not
post Steam credentials, account IDs, session cookies or your local data folder.

No fixed response time or security certification is claimed.

## Application boundaries

- The app does not ask for a Steam password, browser session or API key.
- Native achievement operations run in a separate process and check the account,
  App ID and current state before a reviewed write.
- Reference snapshots preserve evidence; they cannot restore historical unlock
  dates, trophy history or game saves.
- Artwork requests use public Steam resources. Optional completion checks send
  account/App IDs directly to Steam Community without cookies or credentials.
- Updates open a GitHub release page only when requested. They do not silently
  download or execute code.

See [privacy](docs/PRIVACY.md) for local files and network requests.
