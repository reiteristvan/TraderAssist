# Phase 3: Industry Display in CLI + Web UI - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 4 modified files
**Analogs found:** 4 / 4 (all self-referential — each file is its own analog)

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scan.py` | utility/CLI | transform | `scan.py:189–200` `_print_scan_results()` itself | exact — extend in-place |
| `web/ui/src/app/services/api.service.ts` | service/interface | request-response | `Signal` interface lines 12–36 | exact — add fields |
| `web/ui/src/app/pages/candidates/candidates.component.html` | component template | request-response | existing `<th>`/`<td>` block lines 41–77 | exact — replicate column pattern |
| `web/ui/src/app/pages/candidates/candidates.component.ts` | component controller | request-response | `sort()` + helper methods lines 34–67 | exact — extend sort keys + add formatter |

---

## Pattern Assignments

### `scan.py` — extend `_print_scan_results()` (lines 189–200)

**Current core pattern** (`scan.py` lines 189–200):
```python
def _print_scan_results(df) -> None:
    import pandas as pd
    qualified = df[df["qualified"]] if "qualified" in df.columns else df
    print(f"\n{'=' * 60}")
    print(f"  {len(qualified)} qualified setup(s)")
    print(f"{'=' * 60}")
    cols = ["ticker", "strategy", "score", "confidence", "close",
            "suggested_stop", "suggested_target", "risk_reward"]
    display_cols = [c for c in cols if c in df.columns]
    if not qualified.empty:
        print(qualified[display_cols].to_string(index=False))
    print()
```

**Extension pattern — insert industry cols after `confidence`, before `close`:**

New `cols` list order per D-05:
```python
cols = [
    "ticker", "strategy", "score", "confidence",
    "industry_group", "industry_momentum", "industry_above_50ma", "industry_rank_pct",
    "close", "suggested_stop", "suggested_target", "risk_reward",
]
```

**Format preprocessing step** (add before `to_string()` call, operating on a copy):
```python
display_df = qualified[display_cols].copy()

# D-02: industry_momentum → signed percent string, NULL → "—"
if "industry_momentum" in display_df.columns:
    display_df["industry_momentum"] = display_df["industry_momentum"].apply(
        lambda v: f"{v:+.1f}%" if v is not None and not pd.isna(v) else "—"
    )

# D-03: industry_above_50ma → arrow symbol, NULL → "—"
if "industry_above_50ma" in display_df.columns:
    display_df["industry_above_50ma"] = display_df["industry_above_50ma"].apply(
        lambda v: "↑" if v == 1 else ("↓" if v == 0 else "—")
    )

# D-04: industry_rank_pct → "Top N%", NULL → "—"
if "industry_rank_pct" in display_df.columns:
    display_df["industry_rank_pct"] = display_df["industry_rank_pct"].apply(
        lambda v: f"Top {int(round(v))}%" if v is not None and not pd.isna(v) else "—"
    )

print(display_df.to_string(index=False))
```

**UTF-8 safety note:** `scan.py` line 22 already calls `sys.stdout.reconfigure(encoding='utf-8')` — arrow symbols `↑↓` are safe.

**NULL guard pattern** — use `v is not None and not pd.isna(v)` (not bare `if v`) because `0` is a valid value for `industry_above_50ma`.

---

### `web/ui/src/app/services/api.service.ts` — extend `Signal` interface (lines 12–36)

**Existing nullable field pattern** (lines 20–35):
```typescript
export interface Signal {
  ...
  confidence: string | null;
  stop: number | null;
  target: number | null;
  atr: number | null;
  ...
  ath_zone: string | null;
  ...
  r_multiple: number | null;
  holding_days: number | null;
  notes: string | null;
}
```

**Fields to add** (after `notes` or after `confidence` — logical grouping; per D-01 and code_context):
```typescript
  industry_group: string | null;
  industry_momentum: number | null;
  industry_above_50ma: number | null;
  industry_rank_pct: number | null;
```

Rule: all nullable DB columns use `| null` — never `| undefined`.

---

### `web/ui/src/app/pages/candidates/candidates.component.html` — add 4 column headers + cells

**Existing `<th>` pattern with sort** (lines 42–45):
```html
<th (click)="sort('ticker')">Ticker{{ sortIcon('ticker') }}</th>
<th (click)="sort('strategy')">Strategy{{ sortIcon('strategy') }}</th>
<th (click)="sort('score')" class="num">Score{{ sortIcon('score') }}</th>
<th>Conf</th>
```

**New headers to insert after `<th>Conf</th>`, before `<th class="num">Entry</th>`** (per D-06):
```html
<th (click)="sort('industry_group')">Industry{{ sortIcon('industry_group') }}</th>
<th (click)="sort('industry_momentum')" class="num">Mom{{ sortIcon('industry_momentum') }}</th>
<th>Trend</th>
<th (click)="sort('industry_rank_pct')" class="num">Rank%{{ sortIcon('industry_rank_pct') }}</th>
```

Note: column header for `industry_above_50ma` is Claude's discretion (D-09 says `↑↓` or `50MA` or `Trend`) — `Trend` avoids special chars in the header while `↑↓` appear in the cell values.

**Existing `<td>` NULL pattern** (line 76):
```html
<td class="muted">{{ s.ath_zone ?? '—' }}</td>
```

**Existing conditional class pattern** (line 73):
```html
<td class="num" [class.good-rr]="rrNum(s) >= 2" [class.ok-rr]="rrNum(s) >= 1.5 && rrNum(s) < 2">
```

**New cells to insert after `<td>` for confidence, before `<td class="num">` for close** (per D-06/D-07/D-09):
```html
<td class="industry-cell muted"
    [title]="s.industry_group ?? ''"
    style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
  {{ s.industry_group ?? '—' }}
</td>
<td class="num"
    [class.mom-pos]="(s.industry_momentum ?? 0) > 0"
    [class.mom-neg]="(s.industry_momentum ?? 0) < 0 && s.industry_momentum !== null">
  {{ industryMom(s) }}
</td>
<td class="num">{{ s.industry_above_50ma === 1 ? '↑' : s.industry_above_50ma === 0 ? '↓' : '—' }}</td>
<td class="num muted">{{ s.industry_rank_pct != null ? 'Top ' + industryRank(s) + '%' : '—' }}</td>
```

**Why `=== 1` not truthy check:** `industry_above_50ma` is INTEGER 0/1 in DB; `0` is falsy in JS but means "below 50MA" — use strict equality (per CONTEXT.md specifics section).

---

### `web/ui/src/app/pages/candidates/candidates.component.ts` — add sort keys + formatters

**Existing sort mechanism** (lines 34–50) — already handles any field key via `(a as any)[this.sortCol]`:
```typescript
sort(col: string): void {
  if (this.sortCol === col) this.sortAsc = !this.sortAsc;
  else { this.sortCol = col; this.sortAsc = false; }
}

get sorted(): Signal[] {
  const dir = this.sortAsc ? 1 : -1;
  return [...this.signals].sort((a, b) => {
    const av = (a as any)[this.sortCol] ?? 0;
    const bv = (b as any)[this.sortCol] ?? 0;
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}
```

**No changes needed to `sort()` or `sorted`** — the `(a as any)[this.sortCol]` pattern already handles any new string key. New industry column sort keys work automatically once `(click)="sort('industry_group')"` etc. are added to the template.

**Existing helper method pattern** (lines 53–67):
```typescript
rr(s: Signal): string {
  if (s.stop == null || s.target == null || s.close == null) return '—';
  const r = (s.target - s.close) / (s.close - s.stop);
  return isFinite(r) ? r.toFixed(2) + 'R' : '—';
}

stopPct(s: Signal): string {
  if (s.close == null || s.stop == null) return '—';
  return ((s.close - s.stop) / s.close * 100).toFixed(1) + '%';
}
```

**New formatter methods to add** (follow the same null-guard-then-format pattern):
```typescript
industryMom(s: Signal): string {
  if (s.industry_momentum == null) return '—';
  const sign = s.industry_momentum >= 0 ? '+' : '';
  return sign + s.industry_momentum.toFixed(1) + '%';
}

industryRank(s: Signal): string {
  if (s.industry_rank_pct == null) return '—';
  return Math.round(s.industry_rank_pct).toString();
}
```

---

## Shared Patterns

### NULL Display Convention
**Source:** `candidates.component.html` line 76 + `candidates.component.ts` helper methods
**Apply to:** All 4 industry field renderings in both CLI and Angular

- CLI: `lambda v: "..." if v is not None and not pd.isna(v) else "—"` — guard against both Python `None` and pandas `NaN`
- Angular template: `s.field ?? '—'` for strings; helper method returns `'—'` for null numbers
- Never display `0`, `0.0`, or empty string for NULL — always `—` (D-10)

### Color Coding via CSS Class Binding
**Source:** `candidates.component.html` lines 73–74 + `candidates.component.css` lines 44–45
**Apply to:** `industry_momentum` cell

Existing pattern:
```html
[class.good-rr]="rrNum(s) >= 2"
```
```css
.good-rr { color: #4caf89; font-weight: 600; }
.ok-rr   { color: #c4a836; }
```

New momentum classes to add to `candidates.component.css`:
```css
.mom-pos { color: #4caf89; }   /* green — same hue as .good-rr and .target-col */
.mom-neg { color: #c46060; }   /* red   — same hue as .stop-col */
```

### Sortable Column Header
**Source:** `candidates.component.html` lines 42–44
**Apply to:** `industry_group`, `industry_momentum`, `industry_rank_pct` headers (not `industry_above_50ma` — binary field, sort less useful but harmless to add)

Pattern: `<th (click)="sort('field_key')" class="num">Label{{ sortIcon('field_key') }}</th>`

---

## No Analog Found

None — all 4 files have clear in-file extension points with identical patterns already present.

---

## Metadata

**Analog search scope:** `scan.py`, `web/ui/src/app/` tree
**Files scanned:** 4 source files read in full
**Pattern extraction date:** 2026-07-01
