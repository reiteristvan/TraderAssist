# Phase 3: Industry Display in CLI + Web UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 03-industry-display-in-cli-web-ui
**Areas discussed:** Field selection, CLI format, Angular table layout

---

## Field Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Industry group name | Human-readable name from `info['industry']` | ✓ |
| Momentum score (20d %) | Signed % vs SPY — core discriminating signal | ✓ |
| Above 50-day MA flag | Boolean trend direction for the industry ETF | ✓ |
| Rank percentile | Industry momentum rank among all industries in scan run | ✓ |

**User's choice:** All 4 fields
**Notes:** All fields already computed and stored from Phase 2; no reason to surface a subset.

---

## CLI Display Format

| Option | Description | Selected |
|--------|-------------|----------|
| +5.2% (signed %) | Shows direction and magnitude clearly. NULL → '—' | ✓ |
| 5.2 (raw float) | No sign, no percent symbol | |
| +5.2 (signed, no percent) | Direction without % clutter | |

**User's choice (momentum):** `+5.2%` signed percent

| Option | Description | Selected |
|--------|-------------|----------|
| ↑ / ↓ (arrow) | Single character, visually intuitive | ✓ |
| Y / N | Simple boolean text | |
| above / below | Verbose, more width | |

**User's choice (50MA flag):** `↑ / ↓` arrows

| Option | Description | Selected |
|--------|-------------|----------|
| Top 18% | Human-readable, directional | ✓ |
| 18% (plain percent) | Compact | |
| 18 (integer) | Most compact, no unit | |

**User's choice (rank):** `Top N%` format

| Option | Description | Selected |
|--------|-------------|----------|
| After score/confidence | Groups quality signals: score → conf → industry group → momentum → flag → rank → price cols | ✓ |
| At end of row | Zero disruption to existing layout | |
| You decide | Claude picks placement | |

**User's choice (column order):** After confidence column

---

## Angular Table Layout

| Option | Description | Selected |
|--------|-------------|----------|
| After Conf column | Groups alpha-signal columns together | ✓ |
| Before ATH zone | Keeps price block intact | |
| At far right | Zero disruption, tacked on as last columns | |

**User's choice (placement):** After Conf column

| Option | Description | Selected |
|--------|-------------|----------|
| +5.2% with color | Green/red color coding, matches CLI format | ✓ |
| +5.2% plain text | Same value, no color | |
| Progress bar style | Visual bar, more complex | |

**User's choice (momentum display):** `+5.2%` with green/red color coding

| Option | Description | Selected |
|--------|-------------|----------|
| Horizontal scroll | cand-table-wrap already has overflow-x: auto | ✓ |
| Abbreviate headers | Shorter labels reduce width | |
| You decide | Claude picks approach | |

**User's choice (table width):** Horizontal scroll (already supported by existing CSS)

| Option | Description | Selected |
|--------|-------------|----------|
| Full name, truncated to ~20 chars with CSS | Title shown on hover via tooltip | ✓ |
| Full name, no truncation | Everything visible, table wider | |
| Abbreviated (planner decides mapping) | Compact table | |

**User's choice (industry group name):** CSS truncation with hover tooltip

---

## Claude's Discretion

- Exact CSS class names for momentum color coding
- Column header label for `industry_above_50ma` in Angular (`↑↓` vs `50MA` vs `Trend`)
- Pandas format string approach for CLI column formatting
- Whether to add sort support for new industry columns in `candidates.component.ts`

## Deferred Ideas

None — discussion stayed within phase scope.
