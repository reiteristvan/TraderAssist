---
phase: 03-industry-display-in-cli-web-ui
reviewed: 2026-07-01T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - scan.py
  - tests/test_scan_display.py
  - web/ui/src/app/pages/candidates/candidates.component.css
  - web/ui/src/app/pages/candidates/candidates.component.html
  - web/ui/src/app/pages/candidates/candidates.component.spec.ts
  - web/ui/src/app/pages/candidates/candidates.component.ts
  - web/ui/src/app/services/api.service.ts
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-01
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 03 adds industry momentum display columns (Industry / Mom / Trend / Rank%) to the CLI
`_print_scan_results` function and the Angular Candidates table. The general structure is sound:
null-handling comments are thoughtful, the `Signal` interface is correctly extended, CSS classes
are additive, and the formatter functions are mostly correct.

Two blockers were found. The more critical is a unit mismatch: `pandas.Series.rank(pct=True)`
returns fractions in (0, 1], not integers in (0, 100]. Both the Python formatter and the
TypeScript formatter round the stored fraction to the nearest integer, producing "Top 0%" or
"Top 1%" for every signal in production. The tests pass because they inject hardcoded values
like `18.0` that bypass the actual `_attach_industry_rank_pct` computation. The second blocker
is that `_process_diagnose_job` (the on-demand web diagnose path) was not updated: it calls
`run_scan`, which computes industry data, but then silently omits those fields from the `sig`
dict and the INSERT statement, so diagnosed signals always carry NULL for all four industry columns.

Five warnings and four informational items follow.

---

## Critical Issues

### CR-01: `_process_diagnose_job` drops all four industry fields

**File:** `scan.py:551-575`
**Issue:** `_process_diagnose_job` calls `run_scan`, which populates `industry_group`,
`industry_momentum`, `industry_above_50ma`, and `industry_rank_pct` in the returned DataFrame
(via `core.py` lines 712-715). However, when the function builds the `sig` dict (lines 551-567)
it only copies legacy fields. The four industry keys are never transferred into `sig`. The
subsequent `INSERT OR REPLACE` statement (lines 568-576) also hard-codes only the legacy column
list. SQLite silently stores NULL for the missing columns.

Consequence: every signal produced by the web diagnose flow (on-demand diagnose via the jobs
table) will show '—' for all four industry columns in the Candidates and Diagnosis pages, even
when the scan engine computed valid industry data.

**Fix:**
```python
# scan.py — extend the sig dict (after line 566)
sig = {
    "date": str(row.get("as_of", "")),
    ...
    "ath_zone": row.get("ath_zone"),
    # Phase 03 — industry momentum fields
    "industry_group":      row.get("industry_group"),
    "industry_momentum":   row.get("industry_momentum"),
    "industry_above_50ma": row.get("industry_above_50ma"),
    "industry_rank_pct":   row.get("industry_rank_pct"),
}
# and update the INSERT column list and VALUES placeholders accordingly:
cur = conn.execute(
    """INSERT OR REPLACE INTO signals
       (date, ticker, strategy, source, run_id, score, confidence,
        stop, target, atr, qualified, failed_gates, close,
        gate_detail_json, ath_zone,
        industry_group, industry_momentum, industry_above_50ma, industry_rank_pct)
       VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
               :stop, :target, :atr, :qualified, :failed_gates, :close,
               :gate_detail_json, :ath_zone,
               :industry_group, :industry_momentum,
               :industry_above_50ma, :industry_rank_pct)""",
    sig,
)
```

---

### CR-02: `industry_rank_pct` stored as fraction (0–1) but formatted as integer percentage (0–100)

**File:** `scan.py:235` and `web/ui/src/app/pages/candidates/candidates.component.ts:77`

**Issue:** `pandas.Series.rank(pct=True)` returns values in the half-open interval (0, 1].
Confirmed by running the actual calculation on the test ETF set:

```
XSD (5.2%)   → 1.000000
KRE (1.5%)   → 0.666667
XBI (-3.1%)  → 0.333333
```

Neither `_attach_industry_rank_pct` in `core.py` nor the backtest path in `backtest.py` applies
`* 100` before storing. So `industry_rank_pct` in the DB holds values like `0.333`, `1.0`.

Both formatters apply integer rounding directly to this fraction:

**Python (`scan.py:235`):**
```python
lambda v: f"Top {int(round(v))}%" if v is not None and not pd.isna(v) else "—"
```
`int(round(0.333))` → `0` → "Top 0%"
`int(round(1.0))` → `1` → "Top 1%"
Every row in a live scan would display "Top 0%" or "Top 1%".

**TypeScript (`candidates.component.ts:77`):**
```typescript
return Math.round(s.industry_rank_pct).toString();
// Math.round(0.667) → 1 → "Top 1%"
// Math.round(0.333) → 0 → "Top 0%"
```

The tests are not catching this because they inject raw values (`18.0`, `62.0`) that look like
percentages but are never produced by `_attach_industry_rank_pct`.

**Fix — multiply by 100 in both formatters:**
```python
# scan.py:235 — Python formatter
lambda v: f"Top {int(round(v * 100))}%" if v is not None and not pd.isna(v) else "—"
```
```typescript
// candidates.component.ts:77 — TypeScript formatter
return Math.round(s.industry_rank_pct * 100).toString();
```

Update the test fixtures to match real stored values (fractions in 0–1):
```python
# test_scan_display.py — change industry_rank_pct values in _make_row calls
industry_rank_pct=0.18,   # was 18.0 — stored fraction, displayed as "Top 18%"
industry_rank_pct=0.62,   # was 62.0
```
```typescript
// candidates.component.spec.ts
{ industry_rank_pct: 0.18 }  // expects industryRank → '18'
{ industry_rank_pct: 0.187 } // expects rounding → '19'
```

---

## Warnings

### WR-01: `industry_group` sort produces NaN comparisons for null rows

**File:** `web/ui/src/app/pages/candidates/candidates.component.ts:47`
**Issue:** The `sorted` getter uses `?? 0` as a universal null fallback:
```typescript
const av = (a as any)[this.sortCol] ?? 0;
const bv = (b as any)[this.sortCol] ?? 0;
return av < bv ? -dir : av > bv ? dir : 0;
```
For numeric columns this is acceptable. For `industry_group` — a string column that is
frequently null — a null row is coerced to `0` (number). JavaScript's relational operators
then compare `"Semiconductors" < 0`, which coerces `"Semiconductors"` to `NaN` via
`Number()`. `NaN < 0` and `NaN > 0` are both `false`, so the comparator always returns `0`
(equal) for null-vs-string comparisons. Null rows are not placed consistently at the top or
bottom of an Industry sort; their position is governed by the sort engine's stable-sort
tie-breaking (insertion order), which is not what the user expects.

This bug is newly exposed in Phase 03 because `industry_group` is the first sortable string
column that has a meaningful fraction of null rows.

**Fix:**
```typescript
get sorted(): Signal[] {
  const dir = this.sortAsc ? 1 : -1;
  return [...this.signals].sort((a, b) => {
    const av = (a as any)[this.sortCol];
    const bv = (b as any)[this.sortCol];
    // Nulls always sort last regardless of direction
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}
```

---

### WR-02: `industry_above_50ma` lambda omits explicit null guard, inconsistent with sibling lambdas

**File:** `scan.py:225-228`
**Issue:** The three sibling lambdas (Industry, Mom, Rank%) all use the explicit two-part guard:
```python
lambda v: ... if v is not None and not pd.isna(v) else "—"
```
The Trend lambda relies instead on arithmetic equality falling through for null-like values:
```python
lambda v: "↑" if v == 1 else ("↓" if v == 0 else "—")
```
For `None` and `float('nan')` this is safe: both evaluate `== 1` and `== 0` as `False`,
falling through to `"—"`. However, if the column is ever assigned a pandas nullable integer
dtype (`Int64`, which uses `pd.NA`), then `pd.NA == 1` returns `pd.NA` — not `False` — and
using it as the condition of an `if` statement raises `TypeError: boolean value of NA is
ambiguous`. The engine currently produces Python `bool` or `None` for this field (`core.py:307`),
but the inconsistency is a latent failure and breaks the established pattern.

**Fix:**
```python
if "industry_above_50ma" in display_df.columns:
    display_df["Trend"] = display_df["industry_above_50ma"].apply(
        lambda v: "↑" if v is not None and not pd.isna(v) and v == 1
                  else ("↓" if v is not None and not pd.isna(v) and v == 0
                        else "—")
    )
```

---

### WR-03: Missing assertion promised by inline comment in `test_scan_display.py`

**File:** `tests/test_scan_display.py:113-116`
**Issue:** Lines 113-114 read:
```python
# We check that '0.0' does not appear (NaN formatted as float would look like nan/0.0)
```
But no corresponding assertion `assert "0.0" not in out` is present. The intent was clearly
to verify that a NULL `industry_above_50ma` value of `0` (an integer!) rendered as `"↓"` in
the non-null test row and as `"—"` in the null row, and that neither was accidentally printed
as the float string `"0.0"`. The comment documents the test intent but the assertion was never
written.

**Fix:** Add immediately after the `nan` check:
```python
assert "0.0" not in out, "Raw '0.0' float text leaked for NULL industry field"
```

---

### WR-04: `industryRank` null branch is dead code when called from the template

**File:** `web/ui/src/app/pages/candidates/candidates.component.ts:75-78` and
`web/ui/src/app/pages/candidates/candidates.component.html:78`

**Issue:** The template guards against null before calling `industryRank`:
```html
{{ s.industry_rank_pct != null ? 'Top ' + industryRank(s) + '%' : '—' }}
```
The function's null guard (`if (s.industry_rank_pct == null) return '—'`) is never reached
from this call site. The '—' returned by the function would need to be concatenated as
`'Top ' + '—' + '%'` → `'Top —%'` — a visible rendering defect — if the template guard were
ever removed or the function were used elsewhere without a null check.

The function should either own the full formatting (including the "Top … %" wrapper) or drop
the dead null guard and document that callers are responsible for null-checking.

**Fix (preferred — consolidate formatting into the function):**
```typescript
industryRankDisplay(s: Signal): string {
  if (s.industry_rank_pct == null) return '—';
  return 'Top ' + Math.round(s.industry_rank_pct * 100).toString() + '%';
}
```
```html
<td class="num muted">{{ industryRankDisplay(s) }}</td>
```

---

### WR-05: `const f: any = {}` bypasses TypeScript type-checking for filter object

**File:** `web/ui/src/app/pages/candidates/candidates.component.ts:24`
**Issue:**
```typescript
const f: any = {};
if (this.filterStrategy)        f.strategy  = this.filterStrategy;
if (this.filterConfidence)      f.confidence = this.filterConfidence;
if (this.filterMinScore != null) f.min_score = this.filterMinScore;
this.api.getLatestSignals(f).subscribe(...)
```
`getLatestSignals` declares its parameter as
`{ strategy?: string; min_score?: number; confidence?: string }`.
Using `any` means a misspelled key (e.g., `f.confidnece`) would compile and produce a silent
API call with a missing filter — a class of error TypeScript was designed to catch.

**Fix:**
```typescript
const f: { strategy?: string; min_score?: number; confidence?: string } = {};
```

---

## Info

### IN-01: Unused `import math` in `test_scan_display.py`

**File:** `tests/test_scan_display.py:9`
**Issue:** `import math` is present at the top of the file but no symbol from `math` is
referenced anywhere in the module. Dead import.
**Fix:** Remove the line.

---

### IN-02: Angular spec render test omits 'Mom' and 'Trend' column headers

**File:** `web/ui/src/app/pages/candidates/candidates.component.spec.ts:109-112`
**Issue:** The `industry columns render` block asserts only that 'Industry' and 'Rank%'
appear in `fixture.nativeElement.textContent`. The 'Mom' and 'Trend' column headers (and
their formatted cell values `+5.2%`, `↑`) are not verified.
**Fix:** Extend the assertions:
```typescript
expect(text).toContain('Mom');
expect(text).toContain('Trend');
expect(text).toContain('+5.2%');
expect(text).toContain('↑');
expect(text).toContain('—');  // null row
```

---

### IN-03: D-05 column order is not asserted in `test_scan_display.py`

**File:** `tests/test_scan_display.py`
**Issue:** The code comment at `scan.py:195` documents the required column order:
"industry columns inserted after confidence, before close". The test checks that each column
header token appears somewhere in the output but does not verify their relative positions.
A regression that reorders the columns (e.g., Industry after close) would not be caught.
**Fix:** Assert positional order:
```python
industry_pos  = out.index("Industry")
confidence_pos = out.index("confidence")
close_pos      = out.index("close")
assert confidence_pos < industry_pos < close_pos, \
    "Industry columns must appear after 'confidence' and before 'close'"
```

---

### IN-04: Empty `title` attribute emitted for null `industry_group` rows

**File:** `web/ui/src/app/pages/candidates/candidates.component.html:73`
**Issue:**
```html
<td class="industry-group-cell" [title]="s.industry_group ?? ''">
```
When `s.industry_group` is null the binding renders `title=""`. Some browsers (Chrome,
Firefox) display a tooltip box on hover even when the attribute value is empty, which looks
like a rendering artifact. Using `*ngIf` or removing the binding for null values prevents
the empty tooltip.
**Fix:**
```html
<td class="industry-group-cell"
    [attr.title]="s.industry_group ?? null">
```
`[attr.title]="null"` causes Angular to omit the attribute entirely.

---

_Reviewed: 2026-07-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
