## 1. Baseline Artifacts

- [x] 1.1 Review the current project entrypoints, configuration files, sync orchestration, API client, writer registry, database layer, GUI worker boundary, and tests.
- [x] 1.2 Record the current architecture baseline in `proposal.md`, `design.md`, and `specs/project-analysis-baseline/spec.md`.
- [x] 1.3 Identify existing database-impacting code paths, including automatic column additions, index creation, complete-sync truncation, report-table sync, log archiving, and SQL Server staging tables.

## 2. Verification

- [x] 2.1 Run `openspec status --change analyze-current-project` and confirm all required OpenSpec artifacts are present.
- [x] 2.2 Run `openspec validate analyze-current-project` and fix any spec formatting or artifact issues.
- [x] 2.3 Run `python scripts/dry_run_cleanup.py --root .` as the relevant dry-run script for this documentation-only analysis.

## 3. Follow-up Planning

- [x] 3.1 Decide whether future work should first target SQL Server write safety, report-table protection, performance observability, or project cleanup.
- [x] 3.2 For any future SQL Server write change, document expected `sync_runs`, `sync_logs`, metrics, MERGE/staging, and failure-telemetry log changes before implementation.
- [x] 3.3 For any future database schema change, document table impact, data preservation plan, and row-count validation plan before editing code or running SQL.
