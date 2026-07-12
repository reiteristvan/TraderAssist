# Phase 7: CLI Output & Reporting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 7-CLI Output & Reporting
**Areas discussed:** Table rendering & missing weeks, Summary & multiple-comparison caveat, Survivorship-bias warning, CSV export shape

---

## Table rendering & missing weeks

| Option | Description | Selected |
|--------|-------------|----------|
| Pad with N/A row | Insert a row for every missing week with N/A in all numeric columns and significant=False — guarantees exactly 52 rows | ✓ |
| Print fewer than 52 rows | Only print weeks that exist; note count vs 52 in summary | |
| Treat as a hard error | Abort like the thin-data guard if any week is completely absent | |

**User's choice:** Pad with N/A row (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Show N/A for CI/significant + note | ci_low_bps/ci_high_bps show N/A, significant=False, summary calls out uncomputable weeks | ✓ |
| Silent — just show significant=False | Matches SEAS-10's literal column list exactly, insufficient_years stays invisible | |

**User's choice:** Show N/A for CI/significant + note (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| 2 decimal places | Matches typical bps precision elsewhere in codebase | ✓ |
| 4 decimal places | More precision, matches internal float | |
| Whole integers only | Cleanest visually but loses resolution | |

**User's choice:** 2 decimal places (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| pandas to_string() | weeks is already a DataFrame, zero new dependencies | ✓ |
| tabulate library | Nicer box-drawing output, but adds a new pip dependency | |

**User's choice:** pandas to_string() (Recommended)

**Notes:** All four recommended options selected without pushback.

---

## Summary & multiple-comparison caveat

| Option | Description | Selected |
|--------|-------------|----------|
| Explain the false-positive math | Ties to SEAS-15's 0-3/52 expectation, gives actual reasoning | ✓ |
| Short generic disclaimer | Shorter, less pedagogical, still satisfies literal requirement | |

**User's choice:** Explain the false-positive math (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, always show top/bottom 5 | Descriptive context regardless of significance | ✓ |
| Only show when at least one week is significant | Suppress ranked list on clean "none" result | |

**User's choice:** Yes, always show top/bottom 5 (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Show min(5, available) with no overlap | Dedup any week appearing in both top and bottom lists | ✓ |
| Always force exactly 5 and 5 even if they overlap | Simpler logic but can double-count on thin data | |

**User's choice:** Show min(5, available) with no overlap (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Week + delta + CI | Self-contained, no need to cross-reference table | ✓ |
| Week numbers only | Terser, relies on scanning the table above | |

**User's choice:** Week + delta + CI (Recommended)

**Notes:** All four recommended options selected without pushback.

---

## Survivorship-bias warning

| Option | Description | Selected |
|--------|-------------|----------|
| Explain today's-membership bias | Names the actual mechanism (today's sector membership applied to historical prices) | ✓ |
| Short generic warning | Minimal, satisfies literal one-line requirement | |

**User's choice:** Explain today's-membership bias (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Static text | Bias mechanism doesn't change per-run, simplest, no interpolation risk | ✓ |
| Include run parameters | More specific per-run, adds interpolation complexity | |

**User's choice:** Static text (Recommended)

**Notes:** Both recommended options selected without pushback.

---

## CSV export shape

| Option | Description | Selected |
|--------|-------------|----------|
| Same 9 display columns | Matches SEAS-10 literally, keeps stdout/CSV consistent | ✓ |
| 9 display columns + insufficient_years | Adds a 10th column for downstream processing | |

**User's choice:** Same 9 display columns (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-create parent dirs, overwrite existing file | Matches scan.py's --out behavior, least friction | ✓ |
| Error if parent dir missing, overwrite silently otherwise | More conservative, requires pre-existing dir | |

**User's choice:** Auto-create parent dirs, overwrite existing file (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same padding as stdout | Keeps CSV and stdout table in lockstep, one shared DataFrame feeds both | ✓ |
| CSV only has actually-computed weeks | CSV for downstream processing, N/A rows might be noise | |

**User's choice:** Yes, same padding as stdout (Recommended)

**Notes:** All recommended options selected without pushback. User consistently favored the more explanatory/self-contained option across every area (caveat math, mechanism-explaining warning, week+delta+CI format) — noted in CONTEXT.md `<specifics>` as a pattern for planning/execution to default toward.

---

## Claude's Discretion

- Exact function names/signatures for table padding, string formatting, summary assembly, and CSV writing in `scanner/seasonality.py`
- Whether padding logic is a shared helper called by both stdout and CSV paths, or computed once and passed to both
- Exact column header capitalization/spacing beyond the decided number formatting and column order
- Where in `seasonality_by_week.py::main` the render/CSV calls get wired in

## Deferred Ideas

None — discussion stayed within phase scope.
