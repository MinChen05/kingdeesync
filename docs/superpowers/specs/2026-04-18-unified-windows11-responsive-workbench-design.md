# Unified Windows 11 Responsive Workbench Design

**Date:** 2026-04-18

**Goal**

Redesign the desktop GUI into a single, consistent Windows 11 style workbench while keeping existing business behavior intact, and guarantee that all six primary pages remain fully usable at `1366x768`.

## Context

The current GUI already contains parts of a Windows 11 shell, but the application still behaves like a mix of multiple design passes:

- The shell, pages, and stylesheet do not follow one shared layout grammar.
- Several pages still rely on fixed-width side panels, fixed-width inputs, and inconsistent scroll strategies.
- `assets/styles.css` contains overlapping legacy visual systems, including older non-Windows blocks that can still affect the rendered result.
- At `1366x768`, the most important controls can be pushed down by verbose copy, large card stacks, wide forms, or log/table regions that do not yield space gracefully.

The redesign should unify the visual language, simplify page hierarchy, and make space allocation predictable without changing the meaning of sync, schedule, settings, form selection, or history workflows.

## User Requirements

The approved requirements for this redesign are:

- Use a unified Windows 11 visual style throughout the application.
- Redesign all primary pages rather than making narrow cosmetic patches.
- Allow the left navigation to auto-collapse on smaller desktop sizes so content gets priority.
- Guarantee complete usability at `1366x768`.
- Keep functional behavior and data semantics unchanged while improving layout, information hierarchy, and interaction clarity.

## Design Principles

### 1. Single Design Language

The application must render as one Fluent / Windows 11 desktop product rather than a mix of independent page styles. Visual identity will use:

- light, clouded desktop background tones
- high-clarity white or near-white cards
- soft borders and rounded corners
- restrained accent blue for focus, primary actions, and status emphasis
- compact, native-feeling hover and pressed feedback

All legacy Apple-style or otherwise conflicting stylesheet blocks will be removed or isolated so only one active design language remains.

### 2. Workbench-First Information Hierarchy

Every page should answer the same questions in the same order:

1. Where am I?
2. What is the current state?
3. What is the primary action here?
4. What detailed content do I need next?

This leads to a shared page grammar:

- page hero
- primary action bar
- summary cards
- structured content workspace
- dense table or log regions only after primary controls

### 3. Desktop Responsiveness, Not Mobile Simulation

This project is a Windows desktop tool, so responsive behavior should optimize for small desktop windows rather than phone layouts. The minimum supported target for full usability is `1366x768`.

The design must prefer:

- automatic sidebar narrowing before shrinking main content too aggressively
- horizontal-to-vertical workspace stacking at the page level
- local scroll areas for dense regions like logs, lists, and tables
- shorter copy and more compact card compositions on smaller desktop heights

### 4. Behavior Stability

The redesign changes layout, presentation, and interaction organization only. It does not change:

- sync mode semantics
- service call targets
- scheduler behavior
- settings payload shape
- history query meaning
- form-selection persistence logic

## Shared Architecture

### Shell Layout

The main window remains a custom-frameless Windows desktop shell, but the content structure becomes more consistent:

- `Title Bar`: unchanged responsibility, still provides menu, minimize, maximize, close, and drag/snap behavior.
- `Sidebar`: adaptive navigation rail that can render in expanded or compact mode.
- `Top Command Bar`: page title context, quick actions, search, and status chips.
- `Page Host`: single stacked content host with page-specific workspaces following the same scaffold rules.

### Sidebar Behavior

The left sidebar is redesigned as an adaptive navigation rail:

- At standard desktop widths, it shows full branding, grouped navigation, and connection status cards.
- At `1366x768`, it auto-collapses to a narrower presentation that preserves page switching and status access while freeing width for content.
- The sidebar must never force the main workspace into a broken state where primary controls disappear or inputs become unusable.

### Top Command Bar Behavior

The top command bar remains global but becomes more compact:

- search field, quick actions, and status chips use tighter sizing rules
- wide one-line arrangements may wrap into a denser two-row composition when needed
- page title and subtitle remain visible without competing with utility controls

### Shared Page Scaffold

`Win11PageScaffold` becomes the single structural base for all six pages. It must support:

- hero metadata area
- dedicated primary action bar
- summary card strip
- content workspace container
- optional local scroll host
- adaptive workspace orientation hooks

The key change is that page-level primary actions are promoted into one stable region instead of being scattered inside page-specific cards.

### Shared Component Vocabulary

All pages should use the same component categories:

- `Hero Card`
  Purpose: identify the page, current state, and short intent.
- `Primary Action Bar`
  Purpose: keep the most important actions visible at all times.
- `Summary Card`
  Purpose: surface the top metrics or selection state for the current page.
- `Section Card`
  Purpose: group a single content responsibility with a title and brief subtitle.
- `Workspace Splitter`
  Purpose: switch between horizontal and vertical arrangements based on available width.
- `Dense Region`
  Purpose: tables, logs, and large lists that own their own scroll behavior.

## Page Designs

### Dashboard

### Purpose

Act as the operations health overview, surfacing system status, trend direction, recent risk, and high-value diagnostics without overwhelming the first screen.

### Structure

- hero with refresh action and current operational status
- compact four-card summary strip
- first workspace row: trend view plus success/risk summary
- second workspace row: recent failures plus active-form ranking

### Responsive Rules

- at larger widths, the analytical sections may remain side by side
- at `1366x768`, major analytical blocks stack vertically
- chart heights are capped so the first screen is not consumed by graphics alone
- risk signals and failures outrank secondary visualizations

### Result

The page becomes a concise health console rather than a large visual dashboard competing for vertical space.

### Sync

### Purpose

Operate as the primary action-driven workflow for manual sync execution.

### Structure

- hero showing current sync state
- primary action bar containing `Test Connection` and `Start Sync`
- summary strip with sync mode, target scope, progress, and latest result
- workspace with two major sections:
  - configuration workspace
  - execution and monitoring workspace
- log region pinned below monitoring details and locally scrollable

### Responsive Rules

- at larger widths, configuration and monitoring stay side by side
- at `1366x768`, the workspace flips to vertical stacking
- action buttons remain visible at the top of the page
- the log panel keeps a minimum usable height but cannot push primary controls below the viewport

### Result

The page reads as a focused control console: configure, validate, run, observe.

### Settings

### Purpose

Serve as a clear connection configuration center for Kingdee API and SQL Server access.

### Structure

- hero with config source and connection health summary
- primary action bar containing `Test Connection` and `Save Settings`
- summary cards for config source, target database, and recommended flow
- content body with two main grouped sections:
  - Kingdee API
  - SQL Server connection
- short operation note at the end

### Layout Rules

Each settings row follows one shared pattern:

- title
- concise note
- input control

At wider sizes the note and input may share a row. At `1366x768`, rows may convert to a single-column composition when needed so labels and fields never truncate each other.

### Result

The page becomes easier to scan, easier to edit, and less prone to width collisions.

### Forms

### Purpose

Manage the saved default sync scope with fast search, bulk selection, and clear selection feedback.

### Structure

- hero with current default-set status
- primary action bar containing `Reset`, `Save`, search, and bulk selection action
- summary cards for selected count, visible result count, and current scope summary
- dominant list region for selectable forms
- short footer summary only

### Responsive Rules

- the form list gets priority for available height
- controls above the list stay compact and fixed in the main action area
- list rows remain card-like and clickable, but row chrome is simplified to preserve density
- footer explanation remains short so it never competes with the list for space

### Result

The page shifts from explanation-heavy to list-first, which is the correct priority for the task.

### Schedule

### Purpose

Present one operational console for scheduler state, interval strategy, and runtime logging.

### Structure

- hero with current scheduler state
- primary action bar containing `Start/Stop Task` and `Save Settings`
- summary cards for auto scheduling, interval, last execution, and next execution
- workspace split into:
  - scheduling strategy and status
  - log monitoring

### Responsive Rules

- standard desktop uses left/right workspace arrangement
- `1366x768` stacks strategy above log monitor
- status and interval controls stay in the upper visible area
- log filtering and log output remain independently scrollable and cannot consume the action region

### Result

The page becomes a true scheduler control panel instead of a wide page with competing dense blocks.

### History

### Purpose

Provide filter-first inspection of past sync runs, with stable table and pagination usability.

### Structure

- hero with record-scope summary and export action
- compact filter section near the top
- summary cards for success rate, average duration, and top failure target
- large table section for results
- fixed pagination card below the table

### Responsive Rules

- filter controls may reflow into multiple rows at smaller widths
- the query action remains visible and reachable
- table retains a stable visible region
- pagination is never pushed off-screen by filter or summary content

### Result

The page prioritizes search and inspection instead of allowing support content to crowd out the data grid.

## Responsive System

### Supported Desktop Breakpoints

- `>= 1440`:
  standard desktop layout, two-column page workspaces preferred
- `1366x768`:
  minimum guaranteed desktop layout, compact shell and stacked page workspaces where needed

Below `1366x768`, the system should degrade gracefully, but this redesign only guarantees complete usability at `1366x768`.

### Global Rules

### Width

- fixed-width controls should become preferred widths instead of hard constraints wherever possible
- side panels may have recommended widths, but must release space under the minimum supported desktop width
- wide content areas must prefer stacking over squeezing

### Height

- large explanations should not occupy prime vertical space
- logs, tables, and long lists own local scroll containers
- the first visible screen must prioritize action controls and current state

### Scroll Strategy

- dense regions use internal scrolling
- pages may still scroll overall when necessary, but only after primary controls remain visible
- logs and tables should not force users to scroll past primary actions before interacting

## Visual System

### Tokens

The redesigned visual system uses one shared Windows 11 token model for:

- accent color
- neutral surfaces
- borders and separators
- input states
- status states
- card radii
- compact spacing

`src/gui/design_tokens.py` remains the logical home for these shared definitions, while `assets/styles.css` applies them consistently.

### Style Cleanup

`assets/styles.css` will be normalized so that:

- old conflicting Apple-style blocks are removed or fully de-scoped
- Windows 11 selectors are the only active page design system
- component scopes are explicit to avoid global overrides leaking into page-specific widgets

### Motion

Motion should remain subtle:

- hover and focus transitions
- pressed-state clarity
- no decorative or theatrical animation

The tool should feel stable and native, not flashy.

## Data Flow and Interaction Behavior

This redesign changes presentation, not business flow. Existing service interactions remain intact:

- `SyncPage` still reads available forms and sync preferences from the sync service, then runs the same worker flow.
- `SettingsPage` still loads and saves the same settings snapshot and tests the same connections.
- `FormConfigPage` still persists the same default form selection data.
- `SchedulePage` still reads and writes the same scheduler config and controls the same scheduler service.
- `HistoryPage` still queries and exports the same history dataset.
- `DashboardPage` still reads the same reporting and history aggregates.

The user-facing difference is that those flows are surfaced in a more consistent and space-efficient order.

## Error Handling

The redesign must preserve current UI safety behavior:

- failed loads still show feedback instead of crashing the shell
- save or action failures still surface through existing feedback channels
- status chips, helper text, and result summaries should remain visually consistent even in error states

Additional layout work must not introduce fragile resize assumptions that cause runtime exceptions when switching pages or resizing the window.

## Testing Strategy

### Smoke Tests

GUI smoke tests should validate the redesigned shell and key pages at `1366x768`, including:

- page hero is present
- primary action controls exist and are visible
- key form inputs remain visible
- table, log, and list regions still render usable content hosts
- compact sidebar behavior still allows navigation

### Offscreen Validation

The main shell and page widgets should be instantiable in an offscreen test environment at `1366x768` without layout breakage or construction failures.

### Regression Focus

Tests should focus on the failure modes that motivated this redesign:

- action buttons clipped or pushed out of the viewport
- pagination controls not reachable
- logs consuming the page and hiding top controls
- fixed-width settings fields colliding with labels
- side panels taking so much width that primary content becomes unusable

## Out of Scope

The following items are explicitly out of scope for this design:

- business logic refactors unrelated to UI structure
- service-layer behavior changes
- new sync features or scheduler capabilities
- mobile layouts
- bitmap asset generation
- replacing the custom frameless shell model

## Acceptance Criteria

The redesign is complete when all of the following are true:

- the shell and six main pages render as one Windows 11 design system
- `1366x768` is fully usable across dashboard, sync, settings, forms, schedule, and history
- the sidebar can compact automatically to protect content width
- primary actions remain visible on every main page
- tables, logs, and long lists retain usable visible areas
- legacy conflicting page styles no longer affect the rendered experience
- existing business workflows behave the same as before
