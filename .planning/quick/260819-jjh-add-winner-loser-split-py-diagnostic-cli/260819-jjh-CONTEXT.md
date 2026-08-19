# Quick Task 260819-jjh: winner_loser_split.py diagnostic CLI - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Task Boundary

Promote a working throwaway prototype into a proper project diagnostic CLI:
`winner_loser_split.py` at the repo root, backed by testable analysis logic in
`scanner/winner_loser.py`.

### What it does

Answers "which entry-time signal features separate winners from losers?" with train/holdout
separation, so a finding has to survive on data that played no part in discovering it.

Pipeline: read qualified+resolved trades for one `run_id` from `signals` -> split by date into
train/holdout -> baseline mean R with month-block bootstrap CIs -> categorical breakdown ->
search single-feature threshold rules on TRAIN ONLY -> apply the top rules UNCHANGED to the
holdout -> report Spearman rank correlation of train vs holdout rule performance.

### Why it exists

Run on backtest `4f4fe68_2021-01-01_20260702_090418` on 2026-08-19, it established that:
- no entry-time feature separated winners from losers out of sample (48 rules tested, best
  train rule lost money on holdout, Spearman rho = -0.455)
- `confidence` ranks outcomes inconsistently (HIGH best on train, MEDIUM best on holdout)
- `industry_above_50ma` flips sign entirely between windows

It also produced the finding that motivated quick task 260819-g5h (the stop floor): the
strategy's positive expectancy was carried by 15 trades with degenerate near-zero risk.

This is a recurring diagnostic, not a one-off. It needs to be re-runnable against each new
backtest, from any session, by anyone.

### The prototype

`260819-jjh-PROTOTYPE.py` in this task directory is the working script, verbatim as run on
2026-08-19. It is CORRECT and its output is trusted -- treat it as the reference
implementation. This task is a promotion (argparse, new features, module split, tests), NOT a
redesign of the method.

</domain>

<decisions>
## Implementation Decisions

### Placement -- LOCKED: follow the v1.1 seasonality precedent exactly

- `scanner/winner_loser.py` -- the analysis logic (pure, testable, no argparse, no printing)
- `winner_loser_split.py` -- the CLI at repo root (argparse + presentation only)

This mirrors `scanner/seasonality.py` + `seasonality_by_week.py` from milestone v1.1, which is
the established shape for a standalone diagnostic in this project. Splitting logic from
presentation is what makes it unit-testable without subprocess gymnastics.

### Tracked in git -- LOCKED

Not gitignored. It is a project tool, not scratch.

### CLI arguments -- replace the hardcoded constants at prototype lines 11-13

- `--run-id` (required) -- the backtest `run_id` to analyze
- `--split` (default `2024-01-01`) -- train/holdout boundary date
- `--db` (default `data/scanner.db`)
- `--top` (default 8) -- how many train-best rules to carry to the holdout
- Consider `--strategy` to filter pullback/breakout, since `pullback_depth_pct` is NULL for
  breakout rows and a mixed run dilutes it. Planner's call whether this earns its place.

Fail clearly when `--run-id` matches no rows -- an empty result must say so, not print a table
of NaNs.

### Feature set -- add the four schema-v10 columns

Existing eight (from the prototype): `score`, `confidence`, `atr_pct`, `close`, `target_r`,
`target_atr`, `industry_momentum`, `industry_rank_pct`.

Add (landed in quick task 260819-gv9, schema v10): `rsi_entry`, `rvol`, `pullback_depth_pct`,
`pct_to_52w_high`.

Twelve features -> 72 threshold rules instead of 48. The script already prints the test count
and expected spurious-winner count; that line MUST stay and must reflect the new total. The
multiple-comparison burden growing is exactly the thing the user needs to see.

**These four are NULL for all ~192k pre-v10 rows.** Against an old `run_id` they will be
skipped by the existing "fewer than 200 non-null" guard. That guard must stay, and when it
skips a feature it must say so on stdout -- silently testing 8 features while the header claims
12 would be a lie about coverage.

### Predictor discipline -- LOCKED, do not relax

Only entry-time features may be used as predictors. `mae_r`, `mfe_r`, `holding_days`,
`exit_px`, `exit_reason`, `post_stop_*` are OUTCOME variables -- known only after the trade
closes. Including any of them would produce a spectacular, useless result. The prototype
excludes them deliberately.

### Method -- LOCKED, preserve the prototype's semantics exactly

- **Month-block bootstrap**, not per-trade resampling. Trades cluster in time; dozens fire the
  same day and share one market move, so a naive standard error is far too small. This mirrors
  the year-block bootstrap decision from v1.1 for cross-sectionally correlated panels.
- **Selection on train only.** Thresholds come from train quantiles; the holdout is scored
  once with rules chosen without seeing it.
- **No model fitting.** Single-feature thresholds only. With ~3,800 trades and a near-zero
  signal, a tree or regression would find beautiful structure in noise.
- **Nothing per-ticker.** Ranking tickers on ~11 trades each was already established as noise
  (permutation test: 140 observed net-positive vs 137.4 expected under the null).

### Claude's Discretion

- Function decomposition within `scanner/winner_loser.py`
- Whether bootstrap iteration count becomes a flag or stays at 2000
- Output formatting refinements, provided the information content is preserved
- Whether `--strategy` earns its place

</decisions>

<specifics>
## Specific Ideas

### ASCII-only stdout -- project lesson, non-negotiable

Milestone v1.1 shipped a crash where a Unicode arrow in a confirmation print raised
`UnicodeEncodeError` on a Windows cp1252 stream, and 319 passing pytest tests missed it
because `capsys` bypasses the real stream encoding. Quick task 260712-h7l fixed it and added a
subprocess-based regression test.

**Every printed string in both new files must be ASCII-only.** Confirmed reproducible today:
piping a `U+2500` through this machine's stdout raises `UnicodeEncodeError: 'charmap' codec`.

The prototype is already clean on this point -- its only non-ASCII is `U+2500` on comment
lines 100 and 113 (the `# -- section --` house style used throughout `scanner/`). Comments are
safe and may keep that style. Print strings may not.

Follow the existing precedent for testing this: `tests/test_seasonality.py` has a
subprocess-based encoding regression test (added by 260712-h7l). Reuse that pattern rather
than inventing a new one.

### Read-only against the database -- hard requirement

This tool must never write to `data/scanner.db`. Open read-only if practical
(`file:...?mode=ro` URI). The user's DB holds 192,217 backtest signals and real live-signal
history.

Note this is a read-only *consumer* of the schema, so the "all SQL lives in `store_db.py`"
convention deserves a judgment call: either add a query function there (consistent with the
convention) or document why a read-only analysis query is an acceptable exception. Decide
explicitly and say which -- do not leave it implicit.

### Tests

`pytest -q` must stay green (currently 358 passing). Follow `tests/test_seasonality.py` for
structure. Cover at minimum:
- the train/holdout split boundary is applied correctly (a trade exactly on `--split` goes to
  holdout, matching the prototype's `>=`)
- rule selection never inspects holdout rows
- the "fewer than 200 non-null" skip path reports the skip
- empty/unknown `run_id` produces a clear message, not a crash or a NaN table
- ASCII-only stdout under a cp1252 stream (subprocess pattern)

Build fixtures from an in-memory or tmp SQLite DB. Do NOT depend on `data/scanner.db` --
tests must pass offline on a clean checkout.

### Not in scope

- Changing any gate, score, stop, or confidence logic -- this tool only reads and reports
- Re-running any backtest
- Surfacing results in the web UI
- Multi-fold or rolling-window validation. A single split conflates "does this generalize"
  with "did the regime change" (train measured -0.136, holdout +0.159). Worth doing only if
  something survives the simple version first -- note it as a future option, do not build it.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/260819-jjh-PROTOTYPE.py`
  -- the working reference implementation
- `seasonality_by_week.py` + `scanner/seasonality.py` -- the CLI/logic split precedent (v1.1)
- `tests/test_seasonality.py` -- test structure and the cp1252 subprocess regression pattern
- `.planning/quick/260712-h7l-fix-unicode-arrow-crash-unicodeencodeerr/` -- the Unicode crash
  post-mortem
- `scanner/store_db.py` -- schema v10; `signals` table columns
- `CLAUDE.md` -- "all SQL in store_db.py" convention; `pytest -q` requirement

</canonical_refs>
