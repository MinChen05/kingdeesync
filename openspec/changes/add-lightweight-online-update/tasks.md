# Tasks

## 1. Version And Manifest

- [x] Add local version source.
- [x] Define `latest.json` schema and validation rules.
- [x] Add tests for version comparison and manifest validation.

## 2. Update Service

- [ ] Implement manifest fetch with timeout and clear errors.
- [ ] Implement HTTPS-only package URL validation.
- [ ] Implement package download to temporary path.
- [ ] Implement SHA256 verification.
- [ ] Add tests for no update, update available, network failure, invalid manifest, and hash mismatch.

## 3. GUI Flow

- [ ] Add current version display.
- [ ] Add manual "Check for updates" entry.
- [ ] Add update available dialog or panel with version, date, and notes.
- [ ] Add visible failure feedback.
- [ ] Add GUI tests for update states with mocked `UpdateService`.

## 4. Independent Updater

- [ ] Implement updater command arguments.
- [ ] Wait for main process exit before replacement.
- [ ] Extract zip safely and reject path traversal.
- [ ] Preserve `config.local.ini`, `config.ini`, `config.ini.backup`, and `logs/`.
- [ ] Back up current application files before replacement.
- [ ] Restore backup on failure.
- [ ] Add dry-run tests for preserve and rollback behavior.

## 5. Packaging

- [ ] Update packaging script to produce a full release zip.
- [ ] Generate SHA256 checksum.
- [ ] Generate or document `latest.json`.
- [ ] Ensure local config files are excluded from release packages.
- [ ] Update `DEPLOY.md` with release publishing steps.

## 6. Verification

- [ ] Run ruff.
- [ ] Run update service tests.
- [ ] Run updater dry-run tests.
- [ ] Run relevant GUI tests.
- [ ] Confirm SQL Server write impact is none.
