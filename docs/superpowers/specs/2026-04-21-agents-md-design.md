# AGENTS.md Design

## Goal

Create a repository-root `AGENTS.md` that gives coding agents a practical, project-specific operating contract for the Kingdee sync tool. The file should improve consistency, reduce risky edits, and capture the user's long-term preferences for code changes, database structure work, performance tuning, and verification.

## Scope

This design covers one file:

- `D:\Kingdee\AGENTS.md`

The document will govern:

- Communication style and response expectations
- Default working method for debugging, implementation, and performance analysis
- File and directory edit boundaries
- Database schema and index change rules
- Verification expectations before claiming completion
- Project-specific business constraints for forms and `FENTRYID`

This design does not introduce runtime code behavior, UI changes, or database migrations. It only defines agent instructions for future work in this repository.

## Recommended Structure

The `AGENTS.md` file should use a single-file, high-signal structure so agents can reliably find and obey it without chasing linked docs. The recommended sections are:

1. Project Overview
2. Communication Preferences
3. Default Working Method
4. Code Change Boundaries
5. Database Rules
6. Performance Investigation Rules
7. Verification Requirements
8. Forbidden Actions
9. Project-Specific Business Constraints

This keeps the highest-risk rules visible while still leaving room for normal development flexibility.

## Content Design

### Project Overview

State that the repository is a Kingdee data sync tool with three main layers:

- Kingdee API querying
- SQL Server / MySQL persistence
- Desktop GUI operations

This gives agents just enough context to interpret later rules without restating the full project history.

### Communication Preferences

The document should instruct agents to:

- Use Chinese by default
- Lead with conclusions, then provide detail
- Explain impact before database structure changes
- Keep answers concise unless deeper detail is requested

### Default Working Method

The document should define the preferred behavior for day-to-day work:

- Investigate root cause before fixing bugs or performance issues
- Prefer minimal, targeted changes over broad refactors
- Avoid unrelated cleanup while solving the current task
- Gather evidence first for slow queries, slow writes, and paging issues
- Keep progress updates short and practical

### Code Change Boundaries

The document should clearly separate normal edit zones from protected areas.

Allowed by default:

- `src/core`
- `src/services`
- `src/gui`
- `tests`
- repo-local scripts used for diagnostics or maintenance

Restricted by default:

- `config.ini`
- secrets or encrypted credentials
- destructive edits to historical logs

Config guidance:

- `config.local.ini` may be changed when needed for diagnostics or controlled tuning
- any config change should be explained in the final response

### Database Rules

This is the most important long-term section for this project. It should explicitly say:

- Index creation is allowed when backed by evidence
- Non-report business tables may be structurally adjusted
- Report tables must not be structurally changed
  - `GL_RPT_AccountBalance`
  - `stk_inventory`
- Reordering business-table columns is allowed when done safely
- Changes to primary keys, unique keys, merge keys, or major indexes must preserve data and be validated by row-count checks
- Destructive operations without migration safeguards are not allowed

It should also capture the current project reality that merge-key alignment matters for SQL Server write performance.

### Performance Investigation Rules

The document should tell agents how to approach performance work in this codebase:

- Distinguish loading-stage slowness from write-stage slowness
- For loading-stage issues, inspect pagination, rate limiting, chunking, and API request logs
- For write-stage issues, inspect prepare time, `executemany` time, and `commit` time
- Prefer logging and metrics before tuning
- Prefer fixing merge-key/index mismatches before blindly increasing concurrency

### Verification Requirements

The document should require agents to verify changes with evidence before claiming success.

For typical code changes:

- Run targeted unit tests
- Run relevant dry-runs or validation scripts if schema/config behavior is involved
- Call out any unrun verification explicitly

For database structure changes:

- Verify row counts before and after
- Verify required indexes or keys exist after the change
- Verify no temporary backup tables remain unintentionally

### Forbidden Actions

The file should clearly prohibit:

- destructive deletes without explicit approval
- unsafe schema edits on report tables
- resetting or wiping production-like data
- committing secrets or credentials
- mass reformatting unrelated files
- reverting user changes that are unrelated to the current task

### Project-Specific Business Constraints

The file should include current form-specific knowledge already established in this session:

- These tables do not require `FENTRYID` for current sync logic:
  - `prd_mo`
  - `prd_ppbom`
  - `bd_material`
  - `eng_bom`
  - `customer`
  - `bd_stock`
  - `stk_inventory`
  - `GL_RPT_AccountBalance`
- Detail-style forms that use `FENTRYID` or `FID,FENTRYID` must preserve that logic
- Large-table loading optimization is allowed, but parallel paging must avoid overlapping result windows

## Tone and Style

The final `AGENTS.md` should be:

- direct
- practical
- specific to this repository
- written as instructions, not prose documentation

It should avoid generic agent boilerplate that does not help with real work in this project.

## Risks and Mitigations

### Risk: Overly strict rules block useful work

Mitigation:

- Keep high-risk areas strict
- Keep normal code changes flexible
- Allow evidence-backed database tuning

### Risk: Database rules become too vague

Mitigation:

- Name report tables explicitly
- Name allowed structural work explicitly
- Require row-count and index validation for schema changes

### Risk: Agents ignore project-specific performance history

Mitigation:

- Include direct guidance on paging vs write bottlenecks
- Include the requirement to inspect logs before tuning

## Verification Plan

Before considering the `AGENTS.md` complete, review it against this checklist:

- It is rooted in the actual Kingdee project, not generic repo advice
- Database structure rules are explicit
- Report-table exceptions are explicit
- Performance investigation rules are explicit
- Response and collaboration preferences match the user's stated preferences
- There are no placeholders or unresolved ambiguities

## Implementation Plan for the File

After this spec is approved, create `D:\Kingdee\AGENTS.md` with the approved sections and repository-specific rules only. Do not add process overhead that does not help future work in this repo.
