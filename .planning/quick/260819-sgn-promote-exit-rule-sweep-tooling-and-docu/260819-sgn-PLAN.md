---
phase: quick-260819-sgn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scanner/exit_sweep.py
  - exit_rule_sweep.py
  - tests/test_exit_sweep.py
  - tests/test_exit_rule_sweep_cli.py
  - tests/_regression_cp1252_exit_sweep_helper.py
  - .planning/research/2026-08-19-signal-quality-investigation.md
  - .planning/PROJECT.md
  - CLAUDE.md
autonomous: true
requirements: [D-01, D-02, D-03, D-04, D-05]

must_haves:
  truths:
    - "`python exit_rule_sweep.py --run-dir <dir> --mode all` prints an equivalence-gate result, a time-stop table, a breakeven table and a fixed-target table, all ASCII, and exits 0 (D-01)."
    - "Before a single breakeven or target number is printed, the replica is compared TRADE BY TRADE against a LIVE `scanner.simulate.simulate_trades` call on the same signals at the same time stop; on any key-set difference, exit-reason difference, or R difference above 1e-9 the tool prints the mismatches and exits 3 having printed no variant table (D-02)."
    - "`--mode time` never touches the replica — its table comes from `simulate_trades` with `time_stop` varied, exactly as the prototype did (D-02)."
    - "`pytest -q` proves the replica equals `simulate_trades` on synthetic bars across stop-hit, target-hit, ambiguous-bar, time-stop-close, short-history fallback, gap-up, gap-down, stop-floor-binding and missing-bars cases at several time stops; and proves the checker REPORTS FAILURE when handed a deliberately drifted variant (D-02)."
    - "Breakeven arming is pessimistic: a bar that both reaches the breakeven trigger and trades below entry exits that bar at the ORIGINAL stop, or does not exit at all — never at breakeven (D-04)."
    - "The tool never opens the SQLite database, never runs a backtest, and writes nothing except what the user asked for on stdout (D-03)."
    - "No test file reads the OHLCV Parquet cache, the SQLite database, or any backtest run directory; every test injects its own bars provider and its own signal list."
    - "On the reference run the promoted tool reproduces the prototypes' published numbers to 4 dp: baseline ts=10 +0.0293 / win 35.9% / n=3813, ts=40 +0.0541, BE@1.0R ts=10 +0.0137, target=3.0R ts=10 +0.0121."
    - "The findings document carries every investigation, table and conclusion from the session with the numbers unchanged, and PROJECT.md carries the six durable lessons (D-05)."
  artifacts:
    - scanner/exit_sweep.py
    - exit_rule_sweep.py
    - tests/test_exit_sweep.py
    - tests/test_exit_rule_sweep_cli.py
    - tests/_regression_cp1252_exit_sweep_helper.py
    - .planning/research/2026-08-19-signal-quality-investigation.md
  key_links:
    - "exit_rule_sweep.main -> exit_sweep.load_signals(run_dir) -> exit_sweep.make_bars_provider() -> exit_sweep.check_equivalence(simulate_trades vs simulate_variant) -> exit_sweep.sweep_time / sweep_breakeven / sweep_target -> exit_sweep.render_report -> print"
    - "exit_sweep.simulate_variant mirrors scanner/simulate.py lines 116-245 (future-bar slice, gap guards, apply_min_stop_floor, stop-before-target precedence, bar_idx == time_stop-1, ran-out-of-bars fallback). check_equivalence is the ONLY thing keeping that mirror honest — if it is weakened, the tool silently starts producing confident wrong answers."
    - "tests/test_exit_sweep.py::test_variant_matches_real_simulator_on_synthetic_bars is the drift alarm that fires if scanner/simulate.py is edited again without updating the replica."
---

<objective>
Promote three working throwaway prototypes (`exit_sweep.py`, `exit_be.py`, `exit_tgt.py`, staged
in this task directory) into one permanent, tested project diagnostic: `scanner/exit_sweep.py`
(analysis logic, pure, testable) plus `exit_rule_sweep.py` (CLI at repo root), mirroring the
`scanner/winner_loser.py` + `winner_loser_split.py` precedent from quick task 260819-jjh (D-01).
Then write the 2026-08-19 signal-quality investigation up as a permanent research document and
append its durable lessons to PROJECT.md (D-05).

Purpose: "does a different exit rule improve this strategy?" must be re-runnable against every
future backtest without rebuilding a bar-walking harness from scratch — and, more importantly,
without the harness quietly disagreeing with the real simulator. The whole value of the answer
rests on the replica being identical to `scanner/simulate.py` where it is supposed to be
identical, and different ONLY in the one rule under test.

Output: two new source files, three test files, one research document, and edits to PROJECT.md
and CLAUDE.md.

**This is a promotion of code whose results are already trusted, not a redesign.** The three
prototypes are three MODES of one tool (`--mode {time,breakeven,target,all}`), not three tools
(D-01). Preserve their arithmetic exactly — Task 3 reproduces their published numbers to 4 dp,
and a mismatch there means the promotion changed a result, not that the expected value is stale.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/260819-sgn-CONTEXT.md
@.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/exit_sweep.py
@.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/exit_be.py
@.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/exit_tgt.py
@scanner/simulate.py
@scanner/targets.py
@scanner/winner_loser.py
@winner_loser_split.py
@tests/test_winner_loser_cli.py
@tests/_regression_cp1252_winner_loser_helper.py
@.planning/PROJECT.md
@CLAUDE.md
</context>

<decisions_resolved>
Questions the planner settled so the executor does not have to improvise on the load-bearing part.

**(a) The equivalence gate compares TRADE BY TRADE, not means.** Two different bar loops can
produce the same mean R from offsetting errors — a mean check is the weakest possible test of the
exact property that matters. The gate builds a dict keyed by `(signal_date, ticker, strategy)`
from both sides, restricted to trades that resolved to a non-None R, and requires: identical key
sets, identical `exit_reason` per key, and `abs(r_real - r_variant) <= 1e-9` per key. It reports
counts plus up to five example mismatches. The prototype's `assert abs(mean - 0.0293) < 0.0005`
is explicitly rejected (D-02) — it stops testing anything the moment the data changes.

**(b) The gate runs at every time stop a replica table will use, and always runs at least once.**
`REPLICA_TIME_STOPS` for the breakeven table is `(10, 20, 40)`; the target table uses `(10, 20)`.
In `--mode time` no replica table is produced, so the gate runs at the anchor stop only
(`ANCHOR_TIME_STOP = 10`) — the tool always self-checks, cheaply. Cost is one extra
`simulate_trades` pass per gated time stop, and the bars provider is `lru_cache`d.

**(c) `--run-dir` is REQUIRED, not defaulted.** CONTEXT grants discretion on the default; the
right exercise of that discretion is no default. Defaulting to one specific historical run makes
it possible to read a table, believe it describes the run you have in mind, and be wrong.
`--split` keeps the project-wide `2024-01-01` default, matching `winner_loser_split.py`.

**(d) Flags stay minimal: `--run-dir`, `--mode`, `--split`, `--strategy`.** Sweep grids live as
module-level constants in `scanner/exit_sweep.py` (engine-holds-defaults, CLI-stays-thin — the
seasonality/winner_loser precedent). `--strategy` earns its place for the same reason it did in
260819-jjh: a mixed pullback+breakout run has two different exit regimes (different stop rules,
different target logic) and averaging them produces a number describing neither.

**(e) Exit codes are split by cause.** `0` success; `2` user/input error (missing run dir or
parquet, malformed `--split`, no qualified signals, unreadable file); `3` EQUIVALENCE GATE
FAILED. A gate failure is a code defect in this repo, not a user mistake, and the two must be
distinguishable without reading prose.

**(f) The two new source files are ASCII-only end to end** — including comments. The house style
elsewhere allows U+2500 section rules in comments while forbidding non-ASCII in printed strings;
here the whole file is held to ASCII so the rule can be enforced by one unambiguous automated
check rather than by a human eyeballing which strings reach a stream. Markdown deliverables
(PROJECT.md, the research doc) are unaffected — that project lesson is about `print()`, not docs.

**(g) The replica may read bars through numpy arrays instead of `future.iloc[i]`.** Slicing
`Low`/`High`/`Close` to `float64` arrays once per signal is materially faster over ~30 sweep
passes and produces bit-identical values. This is safe precisely because the gate exists: the
optimization is proven equivalent every single run rather than assumed.
</decisions_resolved>

<discovered_state>
**Verified read-only on 2026-08-21, before planning:**

| Fact | Value |
|---|---|
| `runs/pb_2021_2026_v10/signals.parquet` | 24,091 rows x 19 columns; 3,883 qualified |
| Parquet columns | date, ticker, strategy, score, confidence, stop, target, atr, qualified, failed_gates, close, industry_* (4), rsi_entry, rvol, pullback_depth_pct, pct_to_52w_high |
| Qualified-and-resolved (baseline ts=10) | 3,813 -> the 70-signal gap is gap-skips and missing-bar cases |
| `scanner.store_db._SCHEMA_VERSION` | 10 |
| `schema_version` in `data/scanner.db` | **10** (the v10 migration has since run) |
| `CLAUDE.md` stale version markers | **three**, at lines 20, 60, 74 — all say v6 |
| Current test count | 403 passing |

`CLAUDE.md`'s `signals` column list is stale beyond the version number: it predates `target_r`,
`target_atr`, `mae_r`, `mfe_r`, `post_stop_reached_target`, `post_stop_mfe_r`, the four
`industry_*` columns, and the four v10 entry-time feature columns. Task 4 corrects the version
markers and reconciles that list against the live table (constraint (e) called this out as a
one-word fix; it is one word in three places plus a column list that is wrong for the same
reason).
</discovered_state>

<!-- planner-discipline-allow: runs/pb_2021_2026_v10 -->
<!-- planner-discipline-allow: scanner.db -->

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end thin slice — signals to printed time-stop table, with the equivalence gate wired in</name>
  <files>scanner/exit_sweep.py, exit_rule_sweep.py, tests/test_exit_sweep.py</files>
  <reversibility rating="reversible">Two new files plus one new test file; no existing module changes behavior.</reversibility>
  <read_first>
scanner/simulate.py lines 105-245 — the exact statement order the replica must mirror (D-04).
scanner/targets.py `apply_min_stop_floor` — total function, never raises, never tightens.
The staged prototypes `exit_sweep.py` and `exit_be.py` — reference implementations for the
loader and the bar loop respectively.
`winner_loser_split.py` — the CLI shape (`build_parser()` + `main(argv=None) -> int`) to copy.
  </read_first>
  <behavior>
Tests written before the implementation is trusted (all on synthetic bars, no filesystem):
  - stop-hit only: exits at the effective stop, `exit_reason="stop"`, r == -1.0
  - target-hit only: exits at the signal target, `exit_reason="target"`
  - ambiguous bar (low &lt;= stop AND high &gt;= target on the same bar): stop wins, pessimistic
  - no exit trigger within the window: exits at the close of bar index `time_stop - 1`
  - fewer bars available than `time_stop`: exits at the last available close, reason `time_stop`
  - entry open at or above target: unresolved, absent from the variant output
  - entry open at or below the published stop: unresolved, absent from the variant output
  - adverse gap that puts entry within 0.5x ATR of the published stop: the widened stop drives
    both the stop-hit test and the exit price, so R is measured on the floored risk
  - bars provider returns None, or no bars exist after the signal date: unresolved
  - EQUIVALENCE: for `time_stop` in (1, 3, 5, 10), `simulate_variant(..., be_trigger=None,
    target_multiple=None)` and `simulate_trades(..., time_stop=ts)` agree on key set, exit reason
    and R (tolerance 1e-9) across a fixture covering every case above simultaneously
  - DRIFT DETECTION: `check_equivalence` returns `ok=False` with non-empty mismatches when given
    a `variant_fn` that (i) checks target before stop, (ii) ignores the stop floor, or
    (iii) drops one signal from its output
  </behavior>
  <action>
Wire one path through every layer before adding any breadth: parquet -> signals -> bars provider
-> real simulator + replica -> equivalence gate -> time-stop table -> CLI -> stdout. No breakeven
sweep, no target sweep in this task.

Create `scanner/exit_sweep.py` with a module docstring in the house style (mirror
`scanner/winner_loser.py`: what it does, why the equivalence gate exists, a pointer back to this
task directory). ASCII only, whole file, per decision (f) — note the trap: the precedent files
you are copying style from contain em dashes and U+2500 section rules in their docstrings and
comments, and pasting either into these two files fails the ASCII check below. Module contents:

Constants: `ANCHOR_TIME_STOP = 10`, `TIME_STOPS = (5, 8, 10, 15, 20, 30, 40)`,
`DEFAULT_SPLIT = "2024-01-01"`, `EQUIVALENCE_TOLERANCE = 1e-9`. A comment must record that
`TIME_STOPS` reproduces the prototype's grid and that changing it changes what Task 3's reference
numbers mean.

`load_signals(run_dir, qualified_only=True, strategy=None) -> list[Signal]` — read
`<run_dir>/signals.parquet` with pandas, filter on the `qualified` column when
`qualified_only`, filter on `strategy` when given, and build `scanner.simulate.Signal` objects.
Normalize the `date` column the way the prototype does: pass a `datetime.date` through, parse an
ISO string with `date.fromisoformat`, and call `.date()` on anything exposing it. Set
`failed_gates=[]` (the parquet stores a serialized form this tool has no use for). Raise
`FileNotFoundError` naming the path when the directory or the parquet is absent, and `ValueError`
naming the run dir when the filter leaves zero signals — never return an empty list that renders
as a table of NaNs.

`make_bars_provider()` -> an `lru_cache(maxsize=None)`-wrapped callable `(ticker) -> DataFrame |
None` delegating to `scanner.data_store.get_history`. It must be a module-level factory so tests
and the cp1252 helper can substitute a dict-backed provider without touching the Parquet cache.
Every function below takes `bars_provider` as an explicit parameter — no module-level global
reaches into `data_store`.

`@dataclass VariantTrade` with `signal_date: str`, `ticker: str`, `strategy: str`,
`entry_px: float`, `exit_px: float`, `r_multiple: float`, `exit_reason: str`.

`simulate_variant(signals, bars_provider, time_stop=ANCHOR_TIME_STOP, be_trigger=None,
target_multiple=None) -> list[VariantTrade]` — THE REPLICA. It returns resolved trades only;
gap-skips, missing-bar and no-future-bar cases are simply absent, matching the prototypes. The
statement order is not stylistic, it is the contract (D-04):

  1. `bars = bars_provider(sig.ticker)`; skip when None or empty.
  2. `future = bars[bars.index.normalize() &gt; pd.Timestamp(sig.date).normalize()]` — copy this
     expression from `simulate.py`, including `.normalize()` on both sides; skip when empty.
  3. `entry_px = float(future.iloc[0]["Open"])`.
  4. Gap-down guard against the PUBLISHED stop: `entry_px &lt;= sig.stop` -> skip. This is
     deliberately before the floor, exactly as in `simulate.py`, so a widened stop can never
     rescue a gap-skipped trade.
  5. `effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)`;
     `risk = entry_px - effective_stop`.
  6. `effective_target = sig.target if target_multiple is None else entry_px + target_multiple * risk`.
  7. Gap-up guard against the EFFECTIVE target: `entry_px &gt;= effective_target` -> skip. With no
     override this is bit-identical to `simulate.py`'s `entry_px &gt;= sig.target` check; the real
     simulator tests gap-up before gap-down, but both branches are skips, so the resolved set is
     unaffected by the order. Write a comment saying so, since it looks like a divergence.
  8. Walk `bar_idx` from 0 over the future bars with `cur_stop = effective_stop`, `armed = False`:
     `stop_hit = low &lt;= cur_stop` -> exit at `cur_stop`, reason `"be_stop"` if `armed` else
     `"stop"`; `elif high &gt;= effective_target` -> exit at `effective_target`, reason `"target"`;
     `elif bar_idx == time_stop - 1` -> exit at that bar's close, reason `"time_stop"`. Stop is
     tested first — pessimistic on the ambiguous bar.
  9. Breakeven arming happens AFTER the exit tests, at the bottom of the loop body: when
     `be_trigger is not None and not armed and high &gt;= entry_px + be_trigger * risk`, set
     `armed = True` and `cur_stop = entry_px`. The trigger bar itself is therefore never exited at
     breakeven — the stop only moves for subsequent bars (D-04, pessimistic).
  10. Ran out of bars without an exit -> exit at the last available close, reason `"time_stop"`.
  11. `r_multiple = (exit_px - entry_px) / risk`; `signal_date = str(sig.date)`.

Per decision (g) the loop may read `future["Low"].to_numpy(dtype=float)` and siblings once per
signal instead of `future.iloc[bar_idx]`. Both forms yield the same float64s; the gate proves it.

`@dataclass EquivalenceReport` with `time_stop`, `n_real`, `n_variant`, `missing_keys: list`,
`extra_keys: list`, `mismatches: list[tuple]`, `max_abs_diff: float`, and `ok: bool`.

`check_equivalence(signals, bars_provider, time_stop=ANCHOR_TIME_STOP,
variant_fn=simulate_variant, tolerance=EQUIVALENCE_TOLERANCE) -> EquivalenceReport` — the point
of the whole tool (D-02). It calls the LIVE `scanner.simulate.simulate_trades(signals,
bars_provider, time_stop=time_stop)` and `variant_fn(signals, bars_provider,
time_stop=time_stop, be_trigger=None, target_multiple=None)` on the same signals, indexes both by
`(signal_date, ticker, strategy)` restricted to trades whose R is not None, and compares key sets,
`exit_reason` per key, and R per key against `tolerance`. `variant_fn` is an injected parameter so
the drift-detection tests can hand it a deliberately wrong loop. `ok` is True only when the key
sets are identical, no exit reason differs, and `max_abs_diff <= tolerance`. Keep at most five
example mismatches for rendering but count them all. No printing, no raising — this function
returns a verdict; the CLI decides what to do with it.

`summarize(trades, split) -> dict` — accept either `Trade` or `VariantTrade` objects. Keep the
prototype's arithmetic: `statistics.mean` (not numpy), resolved trades only (`r_multiple is not
None`), train is `str(signal_date) < split` and holdout is `>=`, win% is `r > 0`, and a
`collections.Counter` of exit reasons. Count `be_stop` inside the stop bucket for the printed
stop%, since it is a stop.

`sweep_time(signals, bars_provider, time_stops=TIME_STOPS, split=DEFAULT_SPLIT) -> list[dict]` —
uses the REAL `simulate_trades` at each time stop. Never the replica (D-02): `time_stop` is
already a parameter of the real simulator, so reimplementing it would add risk for nothing.

`render_*` helpers returning strings (never printing), and a header block naming the run dir,
split, strategy filter, signal count, and the equivalence verdict. Column layout follows the
prototypes: `time_stop, n, meanR, trainR, holdR, win%, stop%, tgt%, time%` with `:+9.4f` on the R
columns, so a reader can diff this output against the prototype output line for line.

Create `exit_rule_sweep.py` at the repo root, shaped exactly like `winner_loser_split.py`:
`build_parser()` and `main(argv=None) -> int`, no logic beyond argument handling, orchestration
and printing. Arguments per decision (c)/(d): `--run-dir` required; `--mode` with choices
`time`, `breakeven`, `target`, `all`, default `all`; `--split` default `2024-01-01`;
`--strategy` with choices `pullback`, `breakout`, default None. Validate `--split` against
`YYYY-MM-DD` and exit 2 on anything else — string comparison against ISO date text silently
misclassifies every trade if handed `2024-1-1`. `main` loads signals, builds the bars provider,
runs the equivalence gate at the required time stops (decision (b) — for this task, the anchor
stop only), prints the gate result, and then prints the time-stop table. On a failed gate it
prints `EQUIVALENCE GATE FAILED` plus the report to stderr and returns 3 WITHOUT printing any
table. `FileNotFoundError` and `ValueError` are caught, printed to stderr as one line, and
return 2. In this task, modes other than `time` may print `not implemented yet` and return 0;
Task 2 replaces that. All printed strings ASCII (D-01 house rule).

Create `tests/test_exit_sweep.py`. Build synthetic OHLCV frames with a helper that takes a list
of `(open, high, low, close)` tuples and a start date, returning a tz-naive
`DatetimeIndex`ed DataFrame with the `Open/High/Low/Close/Volume` column names `data_store` uses.
Build a `_provider(mapping)` closure returning frames from a dict, and `None` for unknown
tickers. Write every case in the `<behavior>` block. The equivalence test must run one fixture
containing ALL the cases at once, parametrized over `time_stop` in (1, 3, 5, 10), and assert key
sets, exit reasons and R agree — that combination is the drift alarm. The drift-detection tests
pass perturbed `variant_fn` callables and assert `ok is False` with a non-empty explanation.

Test-hygiene rule for this file and every later test file in this task: no test may name a
backtest run directory, the SQLite database, the OHLCV cache directory, `data_store`, or
`get_history` — not in code, not in a comment, not in a docstring. Refer to the reference run in
prose as "the reference run". Fixtures are constructed in the test module or in `tmp_path`.
  </action>
  <verify>
    <automated>python -m pytest tests/test_exit_sweep.py -q</automated>
    <automated>python -c "import pathlib; [pathlib.Path(p).read_text(encoding='utf-8').encode('ascii') for p in ('scanner/exit_sweep.py','exit_rule_sweep.py')]"</automated>
    <automated>python -c "import pathlib,sys; needles=('ru'+'ns/','scanner'+'.db','data/'+'ohlcv','data_'+'store','get_'+'history'); bad=[(p,n) for p in ('tests/test_exit_sweep.py',) for n in needles if n in pathlib.Path(p).read_text(encoding='utf-8')]; print(bad); sys.exit(1 if bad else 0)"</automated>
  </verify>
  <done>`python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode time` prints a passing equivalence line and the seven-row time-stop table, with the ts=10 row showing n=3813, meanR +0.0293, win 35.9 and the ts=40 row showing +0.0541. The synthetic equivalence test passes at four time stops, and the three drift-detection tests prove the checker fails when it should.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Breakeven and fixed-target modes on top of the proven replica</name>
  <files>scanner/exit_sweep.py, exit_rule_sweep.py, tests/test_exit_sweep.py</files>
  <read_first>
The staged prototypes `exit_be.py` and `exit_tgt.py` — the sweep grids and label formats to
preserve, and (in `exit_tgt.py`) the target-override gap-guard behavior described below.
  </read_first>
  <behavior>
  - BE arming is pessimistic: a bar whose high reaches `entry + k * risk` and whose low is below
    entry but above the original stop does NOT exit that bar; a later bar touching entry exits at
    entry with `exit_reason="be_stop"` and r == 0.0 (D-04)
  - `be_trigger=None` changes nothing (already covered by the Task 1 equivalence test; assert
    explicitly here that the armed stop equals `entry_px` and never moves below it)
  - `target_multiple=k` exits at `entry + k * risk` with r == k when the high reaches it
  - `target_multiple=k` re-admits trades the published target had gap-skipped: a signal whose
    entry open sits above `sig.target` but below `entry + k * risk` IS simulated, so the target
    sweep's n exceeds the baseline n. This is the prototype's behavior and is intended
  - `target_multiple=None` reproduces the baseline row exactly (n and mean R)
  - A breakeven table row and a target table row for the same time stop report the same baseline
    numbers, because both come from the same replica with its extra rule switched off
  </behavior>
  <action>
Add the two remaining sweeps to `scanner/exit_sweep.py`, reusing `simulate_variant` unchanged —
no second bar loop is created anywhere in this task, and `simulate_variant`'s statement order from
Task 1 is not touched.

Constants: `BE_TRIGGERS = (0.5, 0.75, 1.0, 1.5, 2.0)`, `BE_TIME_STOPS = (10, 20, 40)`,
`TARGET_MULTIPLES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)`, `TARGET_TIME_STOPS = (10, 20)`,
`REPLICA_TIME_STOPS = tuple(sorted(set(BE_TIME_STOPS) | set(TARGET_TIME_STOPS)))`. These grids
reproduce the prototypes' grids; a comment must say that changing them invalidates the recorded
reference numbers.

`sweep_breakeven(signals, bars_provider, split, triggers=BE_TRIGGERS, time_stops=BE_TIME_STOPS)`
-> rows, one baseline row per time stop (replica with `be_trigger=None`) followed by one row per
trigger, labeled as the prototype labels them (`baseline ts=10`, `BE@1.0R ts=10`). At time stops
other than the anchor, the prototype sweeps only the (1.0, 1.5) triggers; keep that so the output
stays diffable against the prototype run.

`sweep_target(signals, bars_provider, split, multiples=TARGET_MULTIPLES,
time_stops=TARGET_TIME_STOPS)` -> rows, one `current (resistance)` row per time stop
(`target_multiple=None`) followed by one row per multiple. Its table gets a `tgt-hit%` column in
place of the stop/time columns, as the prototype had.

Because the target override moves the gap-up guard onto the synthetic target, override rows cover
MORE trades than the baseline row. Do not "fix" this — it is what the measured numbers were
produced from, and hiding it would be worse than showing it. The `n` column already exposes it;
add one ASCII footnote under the target table stating that fixed-multiple rows re-admit trades
whose entry gapped past the published resistance target, so `n` is not comparable row to row.

Extend `render_report` to compose: header, gate section, then whichever tables the mode selected.
Under all tables print a standing caveat, ASCII, roughly: at this sample size the baseline 95% CI
is about +/-0.2R against effect sizes near 0.03R, so a table ordering is not evidence. That
sentence is the single most reusable output of the investigation being documented in Task 4 and
belongs where the next reader will actually see it.

Wire `--mode` fully in `exit_rule_sweep.py`: `time` -> the Task 1 table; `breakeven` -> gate at
`BE_TIME_STOPS` then the BE table; `target` -> gate at `TARGET_TIME_STOPS` then the target table;
`all` -> gate at `REPLICA_TIME_STOPS` then all three tables. The gate runs and is printed BEFORE
any variant table in every replica-using mode, and a failure at ANY gated time stop suppresses
ALL tables and returns 3 (D-02). Remove the `not implemented yet` stub.

Extend `tests/test_exit_sweep.py` with the `<behavior>` cases, all on synthetic bars via the
injected provider. The breakeven pessimism test is the one that matters most: construct a bar
whose high clears the trigger and whose low sits between the original stop and entry, and assert
that bar produces no exit at entry.
  </action>
  <verify>
    <automated>python -m pytest tests/test_exit_sweep.py -q</automated>
    <automated>python -c "import pathlib; [pathlib.Path(p).read_text(encoding='utf-8').encode('ascii') for p in ('scanner/exit_sweep.py','exit_rule_sweep.py')]"</automated>
    <automated>python -c "import scanner.exit_sweep as m, inspect, sys; src=inspect.getsource(m); sys.exit(0 if src.count('def simulate_variant') == 1 else 1)"</automated>
  </verify>
  <done>All four modes render. The BE table's `baseline ts=10` row and the target table's `current (resistance)` ts=10 row both report n=3813 and meanR +0.0293, matching the time table's ts=10 row produced by the real simulator. Exactly one bar loop exists in the module.</done>
</task>

<task type="auto">
  <name>Task 3: CLI behavior tests, cp1252 regression, and reference-run reproduction</name>
  <files>tests/test_exit_rule_sweep_cli.py, tests/_regression_cp1252_exit_sweep_helper.py, scanner/exit_sweep.py, exit_rule_sweep.py</files>
  <read_first>
tests/test_winner_loser_cli.py — the CLI test shape and the cp1252 subprocess test.
tests/_regression_cp1252_winner_loser_helper.py — the self-contained subprocess helper pattern
(underscore prefix keeps it out of pytest discovery; it builds its own fixture rather than
importing from a test module).
  </read_first>
  <action>
Create `tests/test_exit_rule_sweep_cli.py` covering the CLI contract with a fixture run directory
built in `tmp_path` (write a small signals parquet with `pandas.DataFrame.to_parquet`) and a
substituted bars provider (monkeypatch `exit_sweep.make_bars_provider` to return a dict-backed
callable over synthetic frames — the same helpers Task 1 built, imported from the test module or
re-declared):

  - `--mode time` on the fixture exits 0 and prints a table row per configured time stop
  - `--mode all` on the fixture exits 0 and prints all three tables plus the gate line
  - a missing run directory exits 2 with one stderr line naming the path, and no traceback
  - a run directory whose parquet has zero qualified rows exits 2 with a clear message
  - `--split 2024-1-1` exits 2 before doing any work
  - `--strategy breakout` on a pullback-only fixture exits 2 rather than printing an empty table
  - a failing gate suppresses every table: monkeypatch `exit_rule_sweep`'s reference to the
    equivalence checker (or to `simulate_variant`) with a deliberately drifted implementation,
    then assert the exit code is 3, that stderr names the gate, and that stdout contains none of
    the table headers. This is the end-to-end proof of D-02 — the gate does not merely detect
    drift, it stops the tool from reporting
  - nothing is written: assert the fixture run directory's file list and contents are unchanged
    after a run (D-03)

Create `tests/_regression_cp1252_exit_sweep_helper.py`, self-contained by precedent: it inserts
the repo root at the front of `sys.path`, builds its own synthetic signals parquet plus synthetic
bars in the directory handed to it via `sys.argv[1]`, substitutes the bars provider factory, and
calls `exit_rule_sweep.main([...])`. Cover both the success path (`--mode all`, full report to
stdout) and the error path (missing run dir, message to stderr), selected by `sys.argv[2]`.

Add two tests to `tests/test_exit_rule_sweep_cli.py` that invoke that helper through
`subprocess.run` with `env["PYTHONIOENCODING"] = "cp1252"` and `env.pop("PYTHONUTF8", None)`,
asserting return code (0 / 2), no `Traceback`, and no `UnicodeEncodeError` in either stream. This
subprocess form is mandatory: `capsys` captures through an in-memory buffer that bypasses real
stream encoding, which is exactly why the 260712-h7l crash shipped through a green suite.

Then reproduce the prototypes' measured numbers on the reference run — MANUALLY, not as a test.
Run:

  `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all`

and compare against these expected values, which the staged prototypes produced:

| check | expected |
|---|---|
| time table, ts=10: n / meanR / win% | 3813 / +0.0293 / 35.9 |
| time table, ts=40: meanR | +0.0541 |
| BE table, baseline ts=10: n / meanR | 3813 / +0.0293 |
| BE table, BE@1.0R ts=10: meanR | +0.0137 |
| target table, current (resistance) ts=10: n / meanR | 3813 / +0.0293 |
| target table, target=3.0R ts=10: meanR | +0.0121 |

Save the full stdout to the scratchpad for Task 4 to transcribe. Record the observed-versus-
expected table in the SUMMARY.

If any value differs: STOP and report. Do not update the expected number, and do not add a
tolerance to make it pass. The expected values came from code whose results are trusted; a
difference means the promotion changed a result, which is the single failure mode this whole task
was designed to prevent. The likely culprits, in order: the future-bar slice comparison, the
order of the floor relative to the gap guards, the arming position inside the loop body, or a
numpy-versus-`statistics` mean.

Neither the reference run nor any run directory may be referenced from a test file — the
automated hygiene check below enforces that across all three test files.
  </action>
  <verify>
    <automated>python -m pytest tests/test_exit_sweep.py tests/test_exit_rule_sweep_cli.py -q</automated>
    <automated>python -c "import pathlib,sys; needles=('ru'+'ns/','scanner'+'.db','data/'+'ohlcv','data_'+'store','get_'+'history'); files=('tests/test_exit_sweep.py','tests/test_exit_rule_sweep_cli.py','tests/_regression_cp1252_exit_sweep_helper.py'); bad=[(p,n) for p in files for n in needles if n in pathlib.Path(p).read_text(encoding='utf-8')]; print(bad); sys.exit(1 if bad else 0)"</automated>
    <automated>python -m pytest -q</automated>
  </verify>
  <done>`pytest -q` is green with the new tests on top of the existing 403, offline, with no test reading the database, the OHLCV cache, or a run directory. The gate-failure CLI test proves exit code 3 with no table printed. The reference run reproduces all six expected values to 4 dp and its full output is saved for Task 4.</done>
</task>

<task type="auto">
  <name>Task 4: Findings document, PROJECT.md lessons, and the stale schema markers in CLAUDE.md</name>
  <files>.planning/research/2026-08-19-signal-quality-investigation.md, .planning/PROJECT.md, CLAUDE.md</files>
  <read_first>
`.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/260819-sgn-CONTEXT.md`
section "Session findings" — the source of truth for the document, and the six lessons at its end.
`.planning/PROJECT.md` lines 92-99 — the existing "Key lessons from prior milestones" list.
  </read_first>
  <action>
Write `.planning/research/2026-08-19-signal-quality-investigation.md` (D-05). This is a
first-class deliverable, not a changelog entry: it is the reason four negative investigations do
not get repeated by a future session. Transcribe the CONTEXT.md "Session findings" section
faithfully. Formatting may be improved; numbers, tables and conclusions must not change, and
nothing may be summarized away. Every one of these sections must be present, in this order:

  - a short header block: date 2026-08-19, dataset (sp600 pullback, 2021-01-01 to 2026-06-30,
    3,813 qualified resolved trades), the reference run name, git hash b19b16b
  - Context
  - Investigation 1 - per-ticker winner selection (REJECTED), including 140 observed vs 137.4
    expected, the [128, 147] 5-95 range, and the ~0.75R per-ticker standard error
  - Investigation 2 - entry-time feature discrimination (NOTHING SURVIVED), including the
    12 features / 72 rules design, rho = -0.135, the `rsi_entry < 48.2` rule with holdout mean
    +0.580 CI [+0.053, +1.098], and the forward pointer to Investigation 5 that explains it
  - Investigation 3 - quality gate attribution (INCONCLUSIVE, DO NOT CUT), including the
    qualified baseline n=3813 mean +0.029 CI [-0.195, +0.237], the 6-of-8 sign-flip count, the
    +0.029 vs -0.006 comparison, and the Volume contraction figures (7,112 excluded at +0.032)
  - Investigation 4 - exit rules, with the exit-reason composition, the 4a time-stop series, and
    BOTH markdown tables (4b breakeven and 4c fixed targets) reproduced with every column
  - Investigation 5 - two bugs found and fixed, including EPAC 2024-01-16, the 4,128,767
    `target_r`, the 551 / 14.4% entry-side figure, the 78.1% vs 3.0% and 38.9% vs 7.4%
    comparisons, the widen-not-skip rationale, and the before/after metric-health line
  - The unifying finding, with the +/-0.2R vs 0.03R contrast and the ~66 independent monthly
    blocks
  - Next steps, all three, in the recommended order, plus the explicit NOT-recommended list
  - **How to reproduce** (new): the promoted tool, the exact command
    `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all`, a note that the tool
    is read-only and runs no backtest, and one paragraph explaining the equivalence gate and why
    the numbers below can be trusted (D-02)
  - **Appendix: reference run output** (new): the verbatim stdout captured in Task 3

Then append the six durable lessons from CONTEXT.md's "Durable lessons for PROJECT.md" to the
existing "Key lessons from prior milestones" bullet list in `.planning/PROJECT.md`, as six new
bullets at the end of that list (D-05). Append only — do not reorder, rewrite or reformat the
existing bullets, and do not touch any other section of that file. Add a cross-reference to the
research document in the lesson about the +/-0.2R CI so the full evidence is one click away.

Finally correct `CLAUDE.md`. The version marker `v6` is wrong in three places (lines 20, 60 and
74 per `<discovered_state>`); the live database and `scanner.store_db._SCHEMA_VERSION` are both
10. Update all three to v10 / `current = 10`. While there, reconcile the `signals` column list in
that section against the live table: read the column names with a read-only
`PRAGMA table_info(signals)` and add the ones the list omits. Do not restructure the section, do
not touch any other schema description, and do not write to the database. Also add the new tool
to the CLI quick-reference block beside `winner_loser_split.py`:
`python exit_rule_sweep.py --run-dir runs/<dir> --mode all   # read-only exit-rule sweep (time stop / breakeven / fixed target)`.
  </action>
  <verify>
    <automated>python -c "import pathlib,sys; d=pathlib.Path('.planning/research/2026-08-19-signal-quality-investigation.md').read_text(encoding='utf-8'); need=['137.4','[128, 147]','-0.135','48.2','[-0.195, +0.237]','7,112','+0.029','4,128,767','78.1','66 independent','How to reproduce','Appendix']; missing=[n for n in need if n not in d]; print(missing); sys.exit(1 if missing else 0)"</automated>
    <automated>python -c "import pathlib,sys; p=pathlib.Path('.planning/PROJECT.md').read_text(encoding='utf-8'); need=['Winsorized vs raw mean R','BOTH signal close and entry','train/holdout separation is mandatory','7x the effect','Breakeven stops degrade','resistance-aware target']; missing=[n for n in need if n not in p]; print(missing); sys.exit(1 if missing else 0)"</automated>
    <automated>python -c "import pathlib,sys,sqlite3; c=pathlib.Path('CLAUDE.md').read_text(encoding='utf-8'); v=sqlite3.connect('file:data/scanner.db?mode=ro',uri=True).execute('select version from schema_version').fetchone()[0]; ok=('v%d'%v) in c and ('current = %d'%v) in c and 'exit_rule_sweep.py' in c and ('v'+'6') not in c; print('ok' if ok else 'FAIL'); sys.exit(0 if ok else 1)"</automated>
    <automated>python -m pytest -q</automated>
  </verify>
  <done>The research document exists with all eleven sections, both investigation-4 tables intact and the reference-run output appended verbatim. PROJECT.md's lesson list has six new bullets and no other change. CLAUDE.md reports schema v10 in all three places, lists the columns the live table actually has, and documents the new command.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| shell -> CLI arguments | `--run-dir`, `--split`, `--strategy`, `--mode` are user-supplied strings reaching filesystem reads and date comparisons |
| CLI -> `runs/<dir>/signals.parquet` + OHLCV Parquet cache | read path over historical signal and price data |
| replica -> reported numbers | the trust boundary that actually matters here: a diverged replica produces confident, wrong trading conclusions |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-sgn-01 | Tampering | `exit_sweep.simulate_variant` | high | mitigate | trade-by-trade `check_equivalence` against a live `simulate_trades` call runs before any variant table prints; failure exits 3 with no output; a synthetic-bar pytest fires if `simulate.py` is edited later (D-02) |
| T-sgn-02 | Information Disclosure | `data/scanner.db` | low | mitigate | the tool never imports `store_db` and never opens the database; Task 3 asserts the fixture run directory is unchanged after a run (D-03) |
| T-sgn-03 | Denial of Service | `--run-dir` path handling | low | mitigate | explicit `FileNotFoundError` naming the path, and `ValueError` on a zero-signal filter, so a typo fails fast instead of rendering a table of NaNs |
| T-sgn-04 | Tampering | dependency supply chain | low | accept | no package installs — stdlib `statistics`, `argparse`, `functools`, `subprocess` plus pandas and modules already in this repo |
| T-sgn-05 | Repudiation | reference-run numbers | medium | mitigate | expected values are recorded in this plan and the observed-vs-expected table goes in the SUMMARY and the research doc appendix, so a future divergence is attributable |
</threat_model>

<verification>
- `pytest -q` green, offline, on a clean checkout — no test opens the database, the OHLCV cache, or a run directory.
- `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all` exits 0, prints a passing gate, and reproduces all six expected reference values to 4 dp.
- Exactly one bar-walking loop exists in `scanner/exit_sweep.py`; `--mode time` uses the real simulator.
- Both new source files are ASCII end to end; the cp1252 subprocess tests cover the success and error paths.
- `git status` shows no modification to `data/scanner.db` or anything under the run directory after a full run.
</verification>

<success_criteria>
- `scanner/exit_sweep.py` + `exit_rule_sweep.py` exist, are tracked in git, and follow the logic/CLI split precedent (D-01).
- The equivalence gate compares trade by trade against a live `simulate_trades` call, blocks reporting on failure, and is itself covered by synthetic-bar and drift-detection tests (D-02).
- Read-only: no DB writes, no backtest, no cache mutation (D-03).
- Bar precedence matches `simulate.py` exactly and breakeven arming is pessimistic (D-04).
- The research document and the six PROJECT.md lessons are in place, numbers unchanged (D-05).
</success_criteria>

<output>
Create `.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/260819-sgn-SUMMARY.md` when done.

The SUMMARY must contain the Task 3 observed-versus-expected reference table with the actual
printed values beside the expected ones. That record, plus the equivalence gate, is what lets a
future session trust a number this tool prints without re-deriving it.

Do not delete the three staged prototypes — they are the provenance for the numbers in the
research document.

Not in scope, do not drift into it: promoting any exit rule into `scanner/targets.py` or
`scanner/simulate.py`. Every variant measured so far is worse than what ships. The document's
"Next steps" list (backtest the breakout strategy, widen the universe) is the follow-on work,
and it is a separate task.
</output>
