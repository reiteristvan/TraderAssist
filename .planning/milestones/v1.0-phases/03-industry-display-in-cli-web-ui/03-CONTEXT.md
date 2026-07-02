# Phase 3: Industry Display in CLI + Web UI - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 surfaces the 4 industry fields already stored in the DB (schema v9) to the user in two places: the `scan.py` CLI scan output table and the Angular candidates signal table. No new computation, no schema changes, no API query changes — all 4 columns flow through automatically via `SELECT *`.

**In scope:**
- Extend `_print_scan_results()` in `scan.py` to include all 4 industry columns with formatted display values
- Extend the `Signal` TypeScript interface in `api.service.ts` with all 4 industry fields
- Add 4 industry columns to the Angular candidates table (`candidates.component.html`)
- Apply momentum color coding and CSS truncation in the Angular component

**Out of scope:**
- Winner/loser analysis — Phase 4
- Industry as a gate — v2 contingent on backtest evidence
- Changes to the API signals query — `SELECT *` already returns industry columns
- New DB columns or schema changes
- History page, journal page, or backtest report UI changes

</domain>

<decisions>
## Implementation Decisions

### Field Selection
- **D-01:** Surface **all 4 industry fields** in both CLI and Angular UI: `industry_group`, `industry_momentum`, `industry_above_50ma`, `industry_rank_pct`

### CLI Display Format
- **D-02:** `industry_momentum` displays as a **signed percent with 1 decimal**: `+5.2%` for positive, `-3.1%` for negative. NULL → `—`
- **D-03:** `industry_above_50ma` displays as **arrow symbols**: `1` → `↑`, `0` → `↓`, NULL → `—`
- **D-04:** `industry_rank_pct` displays as **`Top N%`**: e.g. `Top 18%`. NULL → `—`
- **D-05:** **Column order in `_print_scan_results()`**: after `confidence`, before price columns. Final order: `ticker | strategy | score | confidence | industry_group | industry_momentum | industry_above_50ma | industry_rank_pct | close | suggested_stop | suggested_target | risk_reward`

### Angular Table Layout
- **D-06:** Industry columns inserted **after the Conf column**, matching the CLI order. New table sequence: `Ticker | Strategy | Score | Conf | Industry | Mom | ↑↓ | Rank% | Entry | Stop | Stop% | Target | R/R | ATH zone`
- **D-07:** `industry_momentum` column uses **color coding**: green for positive values, red for negative. Displayed as `+5.2%`. NULL → `—`
- **D-08:** **Horizontal scroll** handles table width increase (10 → 14 columns). `cand-table-wrap` already has `overflow-x: auto` — no layout changes needed
- **D-09:** `industry_group` is **truncated to ~20 chars with CSS** (`max-width`, `overflow: hidden`, `text-overflow: ellipsis`). Full name shown on hover via `title` attribute

### NULL Handling (Both Surfaces)
- **D-10:** Any NULL industry field shows `—` in both CLI and Angular UI. Never show `0`, `0.0`, or empty string for NULL industry data

### Claude's Discretion
- Exact CSS class names for momentum color (e.g., `.positive-mom` / `.negative-mom` or reuse `.good-rr` pattern)
- Whether `industry_above_50ma` column header in Angular is `↑↓` or `50MA` or `Trend`
- Exact pandas format string for CLI columns (f-string vs `.apply()` lambda)
- Column sort support for new industry columns in `candidates.component.ts` (add to existing sort logic following the same pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning & Requirements
- `.planning/ROADMAP.md` §Phase 3 — Goal, success criteria (4 numbered), mode, and UI hint
- `.planning/REQUIREMENTS.md` §IND-07 — The single requirement mapped to Phase 3

### Codebase Extension Points
- `scan.py:189–200` — `_print_scan_results()`: column list and `to_string()` print pattern to extend
- `web/ui/src/app/services/api.service.ts:12–36` — `Signal` interface: where 4 industry fields must be added
- `web/ui/src/app/pages/candidates/candidates.component.html` — candidates table: where 4 column headers and cells are added
- `web/ui/src/app/pages/candidates/candidates.component.ts` — sort logic: extend with industry column keys
- `web/api/db/index.js:109–137` — `getLatestSignals()`: uses `SELECT *` so industry columns already flow through; **no changes needed**

### Prior Phase Context
- `.planning/phases/01-industry-classification-etf-data-layer/01-CONTEXT.md` — D-01 through D-07: ETF map decisions, QualityInfo field naming, resolution chain

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_print_scan_results()` (`scan.py:189`) — builds `cols` list and calls `df[display_cols].to_string(index=False)`. Extend `cols` list; add format preprocessing step before the `to_string()` call to apply D-02/D-03/D-04 formatting
- `candidates.component.html` — existing `.cand-table` with `<th (click)="sort(...)">` pattern; all new columns follow the same clickable-header convention
- `.badge` / `.badge-high` / `.badge-medium` CSS pattern (confidence display) — reference for adding a momentum color class pattern (new classes needed; do not reuse badge classes)
- `s.ath_zone ?? '—'` pattern in candidates.component.html — exact NULL display pattern for `—` in Angular templates; replicate for all 4 industry fields

### Established Patterns
- `Signal` interface in `api.service.ts` — all fields use `| null` for nullable values (not `| undefined`). Industry fields should follow: `industry_group: string | null`, `industry_momentum: number | null`, `industry_above_50ma: number | null`, `industry_rank_pct: number | null`
- `SELECT *` in `getLatestSignals()` and `getSignalHistory()` — API already returns all DB columns; TypeScript interface only needs to be extended, no SQL changes required
- `scan.py` uses `sys.stdout.reconfigure(encoding='utf-8')` at startup (line 22) — UTF-8 arrow symbols (`↑↓`) are safe to use in CLI output

### Integration Points
- `db.getLatestSignals()` → `signals/latest` endpoint → Angular `getLatestSignals()` service → `candidates.component.ts` → template render. Industry data already present end-to-end; only the TypeScript interface and template need updating
- `db.getSignalHistory()` → `signals/history` → journal/history pages — those pages also display signals but are **out of scope for Phase 3**

</code_context>

<specifics>
## Specific Ideas

- CLI column order explicitly requested: industry fields slot in between `confidence` and `close`, mirroring conceptual grouping (quality indicators before price levels)
- Momentum color direction: green = positive (industry trending above SPY), red = negative. This is the same semantic as typical market momentum indicators
- Angular `industry_group` column truncation: CSS `max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap` on the `<td>` plus `[title]="s.industry_group"` for full-name tooltip on hover
- `industry_above_50ma` is an INTEGER (0/1) in the DB — cast to boolean in the template (`s.industry_above_50ma === 1 ? '↑' : '↓'`), not truthy check (because `0` is falsy in JS but represents a valid "below" state)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-Industry Display in CLI + Web UI*
*Context gathered: 2026-07-01*
