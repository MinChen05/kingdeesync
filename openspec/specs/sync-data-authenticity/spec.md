## ADDED Requirements

### Requirement: Authenticity audit compares identity and business fields
The system SHALL compare synchronized database rows with Kingdee source rows using configured identity keys, blocker fields, warning fields, value fields, and date fields before declaring data authentic.

#### Scenario: Purchase instock row is authentic
- **WHEN** a `采购入库单` row is audited
- **THEN** the system MUST match `FID` and `FENTRYID` against the Kingdee entry identity and compare bill number, entry sequence, material number, supplier, and real quantity as blocker fields
- **AND** bill date, document status, and modify date MUST be reported as warning fields when they differ

#### Scenario: Purchase order row is authentic
- **WHEN** a `采购订单` row is audited
- **THEN** the system MUST match `FID` and `FENTRYID` against the Kingdee entry identity and compare bill number, material number, supplier, and quantity as blocker fields
- **AND** document status and configured dates MUST be reported as warning fields when they differ

### Requirement: Authenticity audit classifies differences
The system SHALL classify each audited row and field into actionable statuses.

#### Scenario: Source row is missing
- **WHEN** a database row cannot be found in Kingdee by configured identity keys
- **THEN** the audit result MUST be `missing_api` and the row MUST NOT be eligible for automated rehydration

#### Scenario: Database row is missing
- **WHEN** a Kingdee target identity cannot be found in the database
- **THEN** the audit result MUST be `missing_db` and the row MUST NOT be updated as an existing-row repair

#### Scenario: Blocker dimension mismatch
- **WHEN** identity keys match but blocker fields such as material, bill number, supplier, customer, organization, entry sequence, or quantity do not match
- **THEN** the audit result MUST be `dimension_mismatch` or `identity_mismatch` and automated rehydration MUST be blocked for that row

#### Scenario: Warning field mismatch
- **WHEN** identity keys and blocker fields match but warning fields such as date or document status differ
- **THEN** the audit result MUST include field-level warnings and automated rehydration MUST NOT be blocked solely by those warnings

#### Scenario: Repairable value mismatch
- **WHEN** identity and blocker business dimensions match but a configured quantity, amount, price, or repair target field differs
- **THEN** the audit result MUST identify the field-level difference and MAY mark the row as eligible for rehydration

### Requirement: Rehydration requires authenticity gate
The system SHALL require authenticity audit evidence before and after any automated historical rehydration.

#### Scenario: Dry-run before rehydration
- **WHEN** a rehydration batch is prepared
- **THEN** the system MUST output a dry-run summary and detail report including target rows, rows that passed blockers, blocked rows, warning rows, and field-level differences

#### Scenario: Verify after rehydration
- **WHEN** a rehydration batch completes
- **THEN** the system MUST rerun authenticity audit for the same target identities and report whether all blocker fields now match Kingdee while preserving warning differences in the report
