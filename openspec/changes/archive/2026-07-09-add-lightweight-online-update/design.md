# Design: Lightweight Online Update

## Scope

The first version is a user-confirmed update flow. The application can check whether a newer version exists, download a complete release package, verify it, and hand off file replacement to an independent updater process.

The update system must not modify SQL Server business tables, run database migrations, or overwrite local configuration and logs.

## Components

### Version Source

Add a local version source such as `src/version.py` or a `VERSION` file. The GUI can display this version and `UpdateService` can compare it with the remote manifest.

### Remote Manifest

`latest.json` is the only update metadata source for the first version.

Example:

```json
{
  "version": "1.4.0",
  "channel": "stable",
  "release_date": "2026-06-24",
  "package_url": "https://example.com/releases/kingdee-sync-1.4.0.zip",
  "sha256": "hex-encoded-sha256",
  "notes": ["Fix known issues", "Improve desktop UI"]
}
```

Required validation:

- `version` must be parseable.
- `package_url` must use HTTPS.
- `sha256` must be present and match the downloaded package.

### Update Service

`UpdateService` owns non-GUI update logic:

- Fetch manifest.
- Compare versions.
- Download package to a temporary directory.
- Calculate SHA256.
- Return structured success or failure results.

It must not write SQL Server business data.

### GUI Entry

The first GUI entry can live in System Settings or an About/Update dialog:

- Show current version.
- Provide a manual "Check for updates" action.
- Show available version, release date, and notes.
- Require user confirmation before download/install.
- Show download/check/install errors clearly.

### Independent Updater

The main process must not overwrite itself. It starts an independent updater and exits.

Updater responsibilities:

1. Wait for the main process to exit.
2. Validate install directory is the expected application directory.
3. Extract the downloaded zip into a temporary directory.
4. Prevent zip-slip path traversal.
5. Back up current application files.
6. Replace application files.
7. Preserve:
   - `config.local.ini`
   - `config.ini`
   - `config.ini.backup`
   - `logs/`
8. Start the new application version.
9. Roll back from backup if replacement fails.

### Packaging

Release packaging must produce:

- Full application zip.
- SHA256 checksum.
- `latest.json` manifest.

The package must not include machine-local config files.

## Failure Handling

- Network failure: show "unable to check/download update".
- Manifest invalid: show "update metadata invalid".
- Hash mismatch: delete downloaded package and block installation.
- Updater failure: restore backup and show failure result on next launch if possible.
- No write permission: show actionable permission message.

## Security

- HTTPS package URLs only.
- SHA256 verification required.
- Preserve local config/logs.
- Reject unsafe zip paths.
- Do not run bundled SQL scripts automatically.

## Non-Goals

- Silent updates.
- Differential updates.
- Multi-channel update policy beyond reading `channel`.
- Code signing enforcement in the first version.
- Database migration orchestration.
