# Tasks

## 1. Version And Manifest

- [x] Add local version source.
- [x] Define `latest.json` schema and validation rules.
- [x] Add tests for version comparison and manifest validation.

## 2. Update Service

- [x] Implement manifest fetch with timeout and clear errors.
- [x] Implement HTTPS-only package URL validation.
- [x] Implement package download to temporary path.
- [x] Implement SHA256 verification.
- [x] Add tests for no update, update available, network failure, invalid manifest, and hash mismatch.

## 3. GUI Flow

- [x] Add current version display.
- [x] Add manual "Check for updates" entry.
- [x] Add update available dialog or panel with version, date, and notes.
- [x] Add visible failure feedback.
- [x] Add GUI tests for update states with mocked `UpdateService`.

## 4. Independent Updater

- [x] Implement updater command arguments.
- [x] Wait for main process exit before replacement.
- [x] Extract zip safely and reject path traversal.
- [x] Preserve `config.local.ini`, `config.ini`, `config.ini.backup`, and `logs/`.
- [x] Back up current application files before replacement.
- [x] Restore backup on failure.
- [x] Add dry-run tests for preserve and rollback behavior.

## 5. Packaging

- [x] Update packaging script to produce a full release zip.
- [x] Generate SHA256 checksum.
- [x] Generate or document `latest.json`.
- [x] Ensure local config files are excluded from release packages.
- [x] Update `DEPLOY.md` with release publishing steps.

## 6. Verification

- [x] Run ruff.
- [x] Run update service tests.
- [x] Run updater dry-run tests.
- [x] Run relevant GUI tests.
- [x] Confirm SQL Server write impact is none.
