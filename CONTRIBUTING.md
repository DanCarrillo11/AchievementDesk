# Contributing

Achievement Desk is a Windows desktop preview. Keep changes focused and describe
their observable behavior. The interface, documentation and issue reports use English.
Follow the [community conduct guidelines](CODE_OF_CONDUCT.md).

## Development setup

Use Windows x64 and Python 3.11 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py --demo
python -m unittest discover -s tests -v
```

The demo and automated tests use synthetic account data. Steam and credentials
are not required for those checks. GUI tests run offscreen.

## Changes and pull requests

1. Create a branch for one problem or feature.
2. Preserve the existing dark visual language and review-before-apply workflow.
3. Run the relevant checks; document any limits on validation.
4. Update documentation when behavior changes, then open a pull request.

Do not add live write probes, Steam credentials, bypasses for server-controlled
achievements, or claims of universal compatibility. Native calls belong in the
isolated helper. Account checks, stale-state validation, pre-write snapshots and
separate confirmed/rejected/unconfirmed outcomes must remain intact.

Use mock workers for error cases. Any deliberate live-account validation must be
separately authorized by its owner and reported without account identifiers.
Do not submit workspace.json, snapshots, history, caches or executable builds.

See [architecture](docs/ARCHITECTURE.md), [release preparation](docs/RELEASES.md)
and [third-party notices](THIRD_PARTY_NOTICES.txt). Contributions must preserve
the MIT license and the zlib notices on adapted SAM.API code.
