# Add Lightweight Online Update

## Why

The desktop application is now close to distribution-ready. Future releases should not rely only on manual file copying because that can lead to missed updates, accidental overwrites of local configuration, and inconsistent deployed versions.

## What

- Add a first-stage manual online update capability for the Windows desktop application.
- Read a remote `latest.json` manifest and compare it with the local application version.
- Download a full release zip package over HTTPS.
- Verify the downloaded package with SHA256 before installation.
- Use an independent updater process to replace application files after the main process exits.
- Preserve local runtime files:
  - `config.local.ini`
  - `config.ini`
  - `config.ini.backup`
  - `logs/`
- Show visible update status, failure messages, and rollback outcome in the GUI.

## Out Of Scope

- No silent background installation.
- No delta or binary patch updates.
- No database schema migration.
- No SQL Server business write logic changes.
- No automatic execution of SQL scripts during update.
- No replacement of local configuration or logs.

## Impact

- Adds update checking and installation flow around the existing desktop application.
- Adds release packaging requirements for `latest.json`, zip package, and SHA256.
- Requires an independent updater executable or script in packaged releases.
- SQL Server write impact: none.
