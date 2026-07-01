---
phase: 03-industry-display-in-cli-web-ui
plan: 02
subsystem: web-ui
tags: [angular, typescript, industry-momentum, candidates-table, tdd]
status: complete

requires:
  - 03-01-SUMMARY.md  # CLI scan output with industry columns
  - 02-02-SUMMARY.md  # schema v7 + industry momentum computation

provides:
  - Signal interface with 4 industry fields (api.service.ts)
  - candidates.component industry columns (Industry/Mom/Trend/Rank%)
  - mom-pos/mom-neg/industry-group-cell CSS classes

affects:
  - web/ui/src/app/services/api.service.ts
  - web/ui/src/app/pages/candidates/candidates.component.*

tech_stack:
  added: []
  patterns:
    - "Angular template strict-equality null guard: s.field == null ? '—' : s.field === 1 ? '↑' : '↓'"
    - "TDD RED/GREEN: spec references non-existent methods to pin behavior before implementation"
    - "Render test requires loading=false to reveal *ngIf-gated table content"

key_files:
  modified:
    - web/ui/src/app/services/api.service.ts       # Signal interface gains 4 industry fields
    - web/ui/src/app/pages/candidates/candidates.component.ts   # industryMom/industryRank formatters
    - web/ui/src/app/pages/candidates/candidates.component.html # 4 th headers + 4 td cells
    - web/ui/src/app/pages/candidates/candidates.component.css  # mom-pos/mom-neg/industry-group-cell
    - web/ui/src/app/pages/candidates/candidates.component.spec.ts  # 8 new formatter+render tests

decisions:
  - "Trend column uses s.industry_above_50ma === 1 strict equality; integer 0 renders ↓ not —"
  - "industryMom uses >= 0 for prefix so zero renders +0.0% (not ambiguous)"
  - "Rank% cell renders as 'Top N%' string per UI-SPEC copywriting contract"
  - "Render test must set component.loading=false; ngOnInit sets loading=true before API resolves"

metrics:
  duration: 5m
  completed: 2026-07-01
  tasks_completed: 2
  files_modified: 5
---

# Phase 03 Plan 02: Angular Candidates Industry Columns Summary

Web-UI half of IND-07: four industry columns (Industry, Mom, Trend, Rank%) added to Angular Candidates table between Conf and Entry, with color-coded momentum and proper NULL handling.

## What Was Built

Extended the Angular Candidates page with four display-only industry columns sourced from the 4 industry fields already stored in `scanner.db` schema v7 and returned via `SELECT *` in the existing API endpoint. No SQL, no API, and no schema changes were needed.

**Signal interface (`api.service.ts`):** Added `industry_group: string | null`, `industry_momentum: number | null`, `industry_above_50ma: number | null`, `industry_rank_pct: number | null` after `notes`.

**Component (`candidates.component.ts`):** Added `industryMom(s)` — returns `+5.2%` / `-3.1%` / `—`; added `industryRank(s)` — returns integer string or `—`. Both mirror the existing `rr` / `stopPct` null-guard pattern.

**Template (`candidates.component.html`):** Four sortable `<th>` headers (Industry, Mom, Trend, Rank%) inserted after Conf column. Four matching `<td>` cells: industry-group-cell with title tooltip for truncated names; Mom cell with `[class.mom-pos]` / `[class.mom-neg]`; Trend cell with `=== 1 ? '↑' : '↓'` strict equality; Rank% cell as `Top N%`.

**CSS (`candidates.component.css`):** `.mom-pos { color: #4caf89 }`, `.mom-neg { color: #c46060 }`, `.industry-group-cell` with 160px max-width ellipsis truncation.

**Spec (`candidates.component.spec.ts`):** 8 new tests — formatter tests for `industryMom` (positive, negative, null, zero) and `industryRank` (integer, null, rounding), plus a render test confirming Industry/Rank% headers appear in the DOM.

## Task Results

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Signal interface + RED tests | 0510c60 | api.service.ts, spec.ts |
| 2 | Formatters + columns + CSS (GREEN) | 4739d31 | component.ts, .html, .css, spec.ts |

## Verification

- `ng test` (ChromeHeadless): 18/18 SUCCESS
- `ng build`: exits 0, no TypeScript errors
- `npx tsc --noEmit`: clean after Task 2
- RED state confirmed: 7 TypeScript TS2339 errors before Task 2 implementation
- Acceptance criteria grep checks: all 4 interface fields present, both formatters present, all 3 CSS classes present, `=== 1` strict equality confirmed in template

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Render test missing `loading = false`**
- **Found during:** Task 2 ng test run
- **Issue:** The render test set `component.signals` and called `fixture.detectChanges()` but the table is guarded by `*ngIf="!loading && signals.length > 0"`. Since `ngOnInit` calls `load()` which sets `loading = true` (and the HttpClientTestingModule never flushes the request), the table remained hidden and the `Industry`/`Rank%` headers were never in the DOM.
- **Fix:** Added `component.loading = false` before `fixture.detectChanges()` in the render test.
- **Files modified:** `candidates.component.spec.ts`
- **Commit:** 4739d31 (included in Task 2 commit)

## Threat Surface Scan

No new API endpoints, no auth paths, no write paths. The `industry_group` field is rendered via Angular interpolation `{{ }}` and `[title]` binding — both auto-escaped; no `innerHTML` / `bypassSecurityTrust` used (T-03-03 mitigated per plan threat model).

## Self-Check: PASSED

All 5 modified files confirmed present on disk. Both task commits (0510c60, 4739d31) confirmed in git log.
