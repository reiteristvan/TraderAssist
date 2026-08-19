# Quick Task 260819-gv9: Persist entry-time features to the signals table - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Task Boundary

Persist four entry-time signal features to the `signals` table so they can be queried for
winner/loser analysis: `rsi_entry`, `rvol`, `pullback_depth_pct`, `pct_to_52w_high`.

### Why

These four fields are already computed and already flow through
`scanner/backtest.py` → `scanner/simulate.py` (the `Signal` dataclass, lines 35-38) →
`scanner/report.py`. But **`scanner/store_db.py` never writes them and they are not columns
on the `signals` table**, so they exist only inside a fresh backtest run's in-memory report
and vanish on write.

Consequence, measured on 2026-08-19: a train/holdout winner-loser analysis over backtest run
`4f4fe68_2021-01-01_20260702_090418` (3,813 qualified resolved trades) could only test
`score`, `confidence`, `atr_pct`, `close`, `target_r`, `target_atr`, `industry_momentum`,
and `industry_rank_pct`. None separated winners from losers out of sample. The four features
most likely to actually separate were untestable because they are not stored. This task
removes that blocker.

Note `gate_detail_json` is NULL for all backtest rows, so there is no fallback path — the
data genuinely does not exist anywhere queryable.

</domain>

<decisions>
## Implementation Decisions

### Scope — LOCKED: both write paths, via ONE shared normalization helper

Both the backtest path (`journal.write_backtest_to_db`) and the live scan path
(`journal.write_live_signals`, fed by `core.run_scan`) must populate the four columns, and
both must go through a **single shared normalization function** so a column means exactly one
thing regardless of `source`.

This was chosen over "backtest only" and over "both paths writing raw values". The reason is
in the semantics below — writing raw per-path values would silently corrupt the very analysis
this task exists to enable.

### THE TRAP — `pct_to_52w_high` means opposite things in the two result dataclasses

Measured field availability (verified 2026-08-19 via `dataclasses.fields`):

| Field | `PullbackResult` | `BreakoutResult` |
|---|---|---|
| `rsi` | present | present |
| `vol_ratio` | **ABSENT** | present |
| `pullback_depth_pct` | present | **ABSENT** |
| `pct_to_52w_high` | **ABSENT** | present, but in **ratio** form |

`BreakoutResult.pct_to_52w_high` is `close / high_52w * 100` — **higher means CLOSER to the
high**. `scanner/backtest.py:448-452` converts it to `100.0 - raw`, i.e. **distance BELOW the
high — higher means FURTHER away**. The stored column must use the backtest's convention
(distance below the high) for BOTH strategies and BOTH sources.

If the live path were to write `BreakoutResult.pct_to_52w_high` straight through, the same
column would hold a "closeness" number for live rows and a "distance" number for backtest
rows. Any pooled query mixing sources would then be silently wrong — not error out, just
produce a meaningless answer. This is the single highest-risk aspect of the task.

### Canonical definitions (the shared helper must produce exactly these)

Derived from `scanner/backtest.py:435-457`, which is the existing reference implementation:

- `rsi_entry` — `result.rsi` for both strategies.
- `rvol` — current volume ÷ 50-day mean volume. Breakout: `result.vol_ratio` directly.
  Pullback: computed as `df["Volume"].iloc[-1] / df["Volume"].rolling(50).mean().iloc[-1]`
  (backtest gets this from `precomp.vol_sma50`; the live path has no `precomp` and must
  compute from the frame). Guard against a zero or NaN denominator → None.
- `pullback_depth_pct` — `result.pullback_depth_pct` for pullback; **None** for breakout.
- `pct_to_52w_high` — **percent distance BELOW the 52-week high; higher = further below.**
  Breakout: `100.0 - result.pct_to_52w_high`. Pullback:
  `(high_52w - close) / high_52w * 100` where `high_52w` is
  `df["High"].rolling(252, min_periods=200).max().iloc[-1]` (backtest uses
  `precomp.high_52w`). Guard against a non-positive or NaN `high_52w` → None.

### Schema — LOCKED: version bump to 10, additive ALTER TABLE only

Follow the existing precedent exactly. `store_db.py` is at `_SCHEMA_VERSION = 9`; the v9 step
(lines 159-164) added `industry_group` / `industry_momentum` / `industry_above_50ma` /
`industry_rank_pct` via `ALTER TABLE signals ADD COLUMN`. Do the same for v10 with the four
new columns. All REAL. Additive only — no table rebuild, no backfill of historical rows
(existing rows keep NULL; that is correct and expected).

Per `.claude/CLAUDE.md`: "no new tables without schema version bump" — this bumps.

### Claude's Discretion

- Where the shared helper lives. `scanner/core.py` is the natural home (it already holds
  `_industry_strength` and `_attach_industry_rank_pct`, the analogous cross-cutting helpers,
  and both `backtest.py` and `core.py` already import from it). A new module is acceptable if
  it avoids a circular import — verify rather than assume.
- The helper's exact signature. It needs the result object plus the daily frame, and should
  optionally accept the pre-computed series so `backtest.py` keeps its O(log n) `.asof()`
  fast path instead of recomputing rolling windows per ticker per day.
- Test structure and fixtures.

</decisions>

<specifics>
## Specific Ideas

### Performance — do NOT regress the backtest inner loop

`backtest.py` pre-computes rolling indicators once per ticker (`_precompute_bars`) and uses
`.asof()` for O(log n) point-in-time lookups precisely to avoid O(n) recomputation inside the
ticker×day loop. A 10-year sp500 backtest is already ~9-10 hours.

The shared helper must therefore let the backtest keep passing `precomp.vol_sma50` and
`precomp.high_52w` rather than forcing a `rolling(50)` / `rolling(252)` recomputation on each
sliced frame. Accept the pre-computed values as optional parameters and fall back to
computing from the frame only when they are absent (the live path). Recomputing per
ticker×day would be a severe, silent performance regression.

### Write-path call sites to update

- `scanner/store_db.py` — `_SCHEMA_VERSION` → 10; the v10 migration step; the `CREATE TABLE
  signals` column list (for fresh DBs); and **both** `insert_signal()` (line ~208) and
  `insert_signals_batch()` (line ~233) INSERT statements + their param dicts. Missing either
  insert function leaves one path silently writing NULLs.
- `scanner/journal.py` — `write_backtest_to_db()` (~line 300-314) reads attributes off the
  `Signal` dataclass, which already carries all four fields; and `write_live_signals()`
  (~line 63-72) reads from a row dict.
- `scanner/core.py` — `run_scan()` builds `row = asdict(result)` (line 705) then adds the
  industry fields. The four normalized fields must be added here the same way so
  `write_live_signals` can pick them up. Follow the existing `row["industry_*"] = ...` pattern
  at lines 712-716.
- `scanner/backtest.py` — replace the inline block at lines 435-457 with a call to the shared
  helper. Behavior must be identical; this is a refactor of that block, not a rewrite of its
  semantics.

### Guardrails (from CLAUDE.md, non-negotiable)

- `pytest -q` must stay green offline.
- All SQL stays in `store_db.py`.
- Do NOT change gate thresholds or score formulas. This task touches persistence only — no
  gate, no score, no confidence change.
- No `yf.` imports outside `data_store.py` / `earnings_store.py`.
- No `datetime.now()` / `pd.Timestamp.now()` in evaluation logic — use `ctx.as_of`.
- The web layer (`web/api`, `web/ui`) reads `scanner.db`. Adding columns is additive and
  should not break it, but confirm the API does not do `SELECT *` into a strict schema
  validator. If no web change is needed, say so explicitly rather than leaving it unchecked.

### Migration safety

`data/scanner.db` is the user's live database with 192,217 backtest signals, 102 live signals,
and real history. The migration must be additive and idempotent — re-running it must not
error or duplicate columns. Do not rebuild, do not drop, do not backfill.

### Not in scope

- Re-running the backtest (a separate follow-up, ~2.9h for 3 years on sp600)
- Surfacing the new fields in the web API or UI
- Any winner/loser analysis logic in `report.py` (it already consumes these fields in-memory)
- Backfilling the four columns for existing rows — impossible without a re-run, and NULL is
  the honest value

</specifics>

<canonical_refs>
## Canonical References

- `scanner/backtest.py:435-457` — the existing reference implementation of the normalization
  being extracted; the source of truth for the canonical definitions above
- `scanner/simulate.py:35-38` — the `Signal` dataclass fields already carrying these values
- `scanner/store_db.py:159-164` — the v9 migration, the precedent to copy for v10
- `scanner/store_db.py:208-260` — `insert_signal` and `insert_signals_batch`, both needing updates
- `scanner/journal.py:63-72, 300-314` — the two write paths
- `scanner/core.py:705-717` — live `run_scan` row construction
- `CLAUDE.md` — DB conventions ("all SQL in store_db.py"), gate-stability rule
- `.claude/CLAUDE.md` — "no new tables without schema version bump"

</canonical_refs>
