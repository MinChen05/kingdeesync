# desktop-update Specification

## Purpose
Defines the desktop application's manual online update behavior, including manifest validation, verified package download, independent file replacement, local runtime file preservation, rollback visibility, and the guarantee that update installation does not perform SQL Server business writes or database schema migrations.

## Requirements
### Requirement: Manual Update Check

The desktop application SHALL provide a user-triggered way to check for updates without starting an installation automatically.

#### Scenario: User checks and no update exists

- **GIVEN** the local version is equal to or newer than the remote manifest version
- **WHEN** the user checks for updates
- **THEN** the application shows that the current version is up to date
- **AND** no package is downloaded

#### Scenario: User checks and an update exists

- **GIVEN** the remote manifest contains a newer version
- **WHEN** the user checks for updates
- **THEN** the application shows the new version, release date, and release notes
- **AND** installation requires explicit user confirmation

### Requirement: Manifest Validation

The update service SHALL read update metadata from `latest.json` and reject unsafe or incomplete metadata.

#### Scenario: Manifest package URL is not HTTPS

- **GIVEN** `latest.json` contains a non-HTTPS `package_url`
- **WHEN** the update service validates the manifest
- **THEN** the manifest is rejected
- **AND** no package is downloaded

#### Scenario: Manifest is missing SHA256

- **GIVEN** `latest.json` does not contain `sha256`
- **WHEN** the update service validates the manifest
- **THEN** the manifest is rejected
- **AND** no package is downloaded

### Requirement: Package Integrity Verification

The update service SHALL verify the downloaded package SHA256 before installation.

#### Scenario: SHA256 matches

- **GIVEN** the package hash matches the manifest hash
- **WHEN** verification completes
- **THEN** the package may be handed to the updater

#### Scenario: SHA256 does not match

- **GIVEN** the package hash does not match the manifest hash
- **WHEN** verification completes
- **THEN** installation is blocked
- **AND** the user sees a clear integrity failure message

### Requirement: Independent File Replacement

The application SHALL use an independent updater process to replace application files.

#### Scenario: Main process is running

- **GIVEN** the main desktop application is running
- **WHEN** the user confirms installation
- **THEN** the main application launches the updater process
- **AND** exits before files are replaced

#### Scenario: Replacement succeeds

- **GIVEN** the updater has a verified package
- **WHEN** the updater replaces application files
- **THEN** it starts the new application version

#### Scenario: Replacement fails

- **GIVEN** the updater fails while replacing application files
- **WHEN** rollback is possible
- **THEN** it restores the previous version from backup
- **AND** reports a visible failure result

### Requirement: Preserve Local Runtime Files

The updater SHALL preserve local configuration and log files during update.

#### Scenario: Local config exists

- **GIVEN** `config.local.ini`, `config.ini`, or `config.ini.backup` exists in the install directory
- **WHEN** the updater installs a new package
- **THEN** those files remain unchanged

#### Scenario: Logs exist

- **GIVEN** a `logs/` directory exists in the install directory
- **WHEN** the updater installs a new package
- **THEN** the `logs/` directory remains unchanged

### Requirement: No Database Migration

The online update flow SHALL NOT execute SQL Server business writes or database schema migrations.

#### Scenario: Update installs a package

- **GIVEN** a verified update package is installed
- **WHEN** the update flow completes
- **THEN** no SQL Server business table writes are performed by the update flow
- **AND** no database migration script is executed automatically
