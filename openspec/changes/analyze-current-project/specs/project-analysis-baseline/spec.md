## ADDED Requirements

### Requirement: Architecture Baseline
The project analysis baseline SHALL document the current module boundaries, runtime entrypoints, and primary data flow for the Kingdee data sync tool.

#### Scenario: Reader needs the project map
- **WHEN** a maintainer opens the baseline
- **THEN** they can identify the CLI/GUI entrypoints, configuration layer, Kingdee API client, sync orchestration, form runner, writer registry, SQL Server upsert path, repositories, and GUI worker boundary

### Requirement: Database Impact Boundary
The project analysis baseline SHALL explicitly distinguish this documentation-only change from future changes that alter SQL Server tables, indexes, primary keys, unique keys, or report-related structures.

#### Scenario: Baseline is created
- **WHEN** the OpenSpec change artifacts are reviewed
- **THEN** they state that no database schema or production data is changed by this analysis

#### Scenario: Existing DDL risk is reviewed
- **WHEN** maintainers plan a future SQL Server write change
- **THEN** the baseline provides a list of existing code areas that may create indexes, add columns, truncate tables, archive logs, or use staging tables

### Requirement: Verification Baseline
The project analysis baseline SHALL record the relevant validation commands and dry-run expectations for future work on this repository.

#### Scenario: Future change starts from the baseline
- **WHEN** a maintainer uses the analysis before implementing changes
- **THEN** they can see the expected minimum checks for unit tests, OpenSpec validation, cleanup dry-run, and SQL Server write-log expectations when applicable
