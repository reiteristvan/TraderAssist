---
phase: quick-260819-jjh
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scanner/winner_loser.py
  - winner_loser_split.py
  - scanner/store_db.py
  - tests/test_winner_loser.py
  - tests/test_winner_loser_cli.py
  - tests/_regression_cp1252_winner_loser_helper.py
  - CLAUDE.md
autonomous: true
requirements: [D-01, D-02, D-03, D-04, D-05, D-06]

must_haves:
  truths:
    - "`python winner_loser_split.py --run-id <run>` prints train/holdout counts, both baselines with month-block bootstrap CIs, the categorical breakdown, the top-N train-selected rules with their holdout performance, and the Spearman rho — all ASCII (D-06)."
    - "Threshold selection reads train rows only; changing holdout r_multiple values cannot change any selected feature, threshold, direction, or train statistic (D-05)."
    - "A feature that is absent from the table or has fewer than 200 non-null train values is named on stdout as skipped with its reason, and the printed test count reflects only the features actually tested (D-04)."
    - "An unknown/empty run_id, a missing DB file, or a malformed --split prints one clear line to stderr and exits 2 — never a traceback and never a table of NaNs."
    - "The database file is byte-identical after a run; the connection is opened with the read-only URI."
    - "On the reference run with the legacy 8 features, the promoted code reproduces the prototype's published numbers exactly."
  artifacts:
    - scanner/winner_loser.py
    - winner_loser_split.py
    - tests/test_winner_loser.py
    - tests/test_winner_loser_cli.py
    - tests/_regression_cp1252_winner_loser_helper.py
  key_links:
    - "winner_loser_split.main -> store_db.get_readonly_connection -> store_db.get_analysis_signals -> winner_loser.load_records -> winner_loser.analyze -> winner_loser.render_report -> print"
    - "store_db.get_analysis_signals intersects its column list with PRAGMA table_info(signals) — this is what keeps the tool alive against the live schema-v9 database, where rsi_entry/rvol/pullback_depth_pct/pct_to_52w_high do not exist as columns at all."
---

<objective>
Promote the working throwaway prototype `260819-jjh-PROTOTYPE.py` into a permanent project
diagnostic: `scanner/winner_loser.py` (analysis logic, testable) plus `winner_loser_split.py`
(CLI at repo root), mirroring the `scanner/seasonality.py` + `seasonality_by_week.py` precedent
from v1.1 (D-01).

Purpose: "which entry-time signal features separate winners from losers?" must be re-runnable
against every new backtest, by anyone, from any session — with train/holdout separation intact
so a finding has to survive data that played no part in discovering it.

Output: two new source files, one new query pair in `store_db.py`, three test files, and a
documented parity check proving the refactor did not silently change the prototype's results.

**This is a promotion of code whose method is already trusted, not a redesign.** The method is
LOCKED (D-05): month-block bootstrap, selection on train only, no model fitting, nothing
per-ticker, no outcome variables as predictors. Preserve the prototype's arithmetic verbatim —
including its idiosyncratic quantile index formula and its use of pure-python
`statistics.mean` — because the parity check in Task 4 depends on bit-level agreement.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/260819-jjh-CONTEXT.md
@.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/260819-jjh-PROTOTYPE.py
@scanner/seasonality.py
@seasonality_by_week.py
@tests/test_seasonality_cli.py
@tests/_regression_cp1252_helper.py
@scanner/store_db.py
@CLAUDE.md
</context>

<decisions_resolved>
Two questions the planner was asked to settle rather than leave implicit:

**(a) The "all SQL lives in store_db.py" convention — NO EXCEPTION IS TAKEN.**
Both the read-only connection helper and the analysis query go into `scanner/store_db.py`
(`get_readonly_connection`, `get_analysis_signals`). Rationale: the convention exists so a
Postgres swap touches one module, and a `PRAGMA table_info` probe is exactly the kind of
dialect-specific SQL that must not leak into an analysis module. `scanner/winner_loser.py`
imports `store_db` and never writes a SQL string. This costs ~35 lines and removes an
ambiguity permanently.

**(b) `--strategy` earns its place — INCLUDE IT.**
`pullback_depth_pct` is NULL for breakout rows. On a mixed-strategy run the 200-non-null guard
can pass on pullback rows alone, and the resulting rule would silently describe a pullback-only
subpopulation while the header claims it covers the run. A four-line SQL filter prevents that
class of wrong answer. The reference run is pullback-only, so this does not perturb Task 4.

**No new CLI flags beyond the locked four plus `--strategy`.** Bootstrap iterations (2000) and
seed (11) stay as function parameters with module defaults, per the seasonality precedent of
keeping defaults in the engine and the CLI thin. Adding `--iters`/`--seed` would be padding.
</decisions_resolved>

<discovered_state>
**Verified read-only against the live database on 2026-08-19, before planning:**

| Fact | Value |
|---|---|
| `schema_version` in `data/scanner.db` | **9**, not 10 |
| `rsi_entry`, `rvol`, `pullback_depth_pct`, `pct_to_52w_high` | **columns ABSENT from `signals`** |
| Reference run total rows | 24,285 (all `strategy='pullback'`) |
| Reference run qualified + resolved | 3,813 |
| Train (`date < '2024-01-01'`) / holdout (`>=`) | **1404 / 2409** — matches the prototype exactly |

The v10 migration from quick task 260819-gv9 shipped in code but has not yet run against this
database (migrations are lazy — they fire on the next write path). CONTEXT.md anticipated the
four columns being *NULL*; on this machine today they are *missing entirely*, so a naive
`SELECT rsi_entry, ...` raises `sqlite3.OperationalError: no such column: rsi_entry` and the
tool is dead on arrival against the user's real database. A read-only tool must not and cannot
migrate. Hence the column-intersection requirement in Task 1 is load-bearing, not defensive
polish.
</discovered_state>

<tasks>

<task type="tracer">
  <name>Task 1: End-to-end thin slice — read-only DB access through to a printed baseline</name>
  <files>scanner/store_db.py, scanner/winner_loser.py, winner_loser_split.py, tests/test_winner_loser_cli.py</files>
  <reversibility rating="reversible">Two additive functions in store_db.py and two new files; nothing existing changes behavior.</reversibility>
  <action>
Wire one path through every layer this task touches — DB -> query -> records -> split ->
baseline -> CLI -> stdout — before building any of the analysis breadth. No categorical table,
no rule search, no bootstrap yet.

In `scanner/store_db.py`, add two functions next to the existing `get_connection`, following
its style (module-level `_DEFAULT_DB`, `sqlite3.Row` row factory, `Optional[Path]` argument):

`get_readonly_connection(db_path=None)` — raise `FileNotFoundError` with a message naming the
path when the file does not exist (do not let SQLite's opaque "unable to open database file"
surface, and do not create the file). Otherwise open via the SQLite URI form
`file:<path>?mode=ro` with `uri=True`, building the path component from `Path(...).as_posix()`
passed through `urllib.parse.quote` with `safe="/:"` so Windows drive letters survive and a
stray `?` or `#` in a path cannot corrupt the URI. Set `row_factory = sqlite3.Row`. Do not call
`mkdir`, do not call `migrate`, do not set any write-affecting PRAGMA.

`get_analysis_signals(conn, run_id, strategy=None)` — the single read the diagnostic performs.
Define a module-level tuple of the columns it wants: `date`, `ticker`, `r_multiple`, `score`,
`confidence`, `atr`, `close`, `target_r`, `target_atr`, `industry_momentum`,
`industry_above_50ma`, `industry_rank_pct`, `rsi_entry`, `rvol`, `pullback_depth_pct`,
`pct_to_52w_high`. Probe the live table with `PRAGMA table_info(signals)` and select only the
intersection of wanted and present columns — see `<discovered_state>`, the last four are absent
from the schema-v9 database this ships against. Return a list of dicts in which every wanted
column is a key, with `None` filling any column the table does not have, so callers see one
uniform record shape and cannot tell "column missing" from "value null" by accident. Filter
`run_id = ? AND qualified = 1 AND r_multiple IS NOT NULL`, add `AND strategy = ?` when
`strategy` is given, `ORDER BY date`. Every value must be bound as a parameter; never
interpolate `run_id` or `strategy` into the SQL text. Also return, as a second element, the set
of column names that were absent, so the caller can report them as skipped with a distinct
reason rather than as "too few non-null values".

Create `scanner/winner_loser.py` with a module docstring in the house style (mirror
`scanner/seasonality.py`: what it does, why train/holdout, a pointer back to this task
directory). Define the constants that pin the LOCKED method (D-05): `_CONF_LEVELS` mapping LOW
0.0 / MEDIUM 1.0 / HIGH 2.0, `LEGACY_FEATURES` as the prototype's eight in the prototype's
order (score, confidence, atr_pct, close, target_r, target_atr, industry_momentum,
industry_rank_pct), `V10_FEATURES` as the four from schema v10 (rsi_entry, rvol,
pullback_depth_pct, pct_to_52w_high), and `FEATURES = LEGACY_FEATURES + V10_FEATURES` (twelve,
per D-04). Note in a comment that `industry_above_50ma` is deliberately categorical-only and is
not a threshold feature — that matches the prototype and must not drift.

Add `load_records(conn, run_id, strategy=None)` reproducing the prototype's record shaping
exactly: a `num()` coercion returning None for anything non-floatable (confidence arrives as a
text label), the skip condition `not close or close <= 0 or atr is None` (the falsy test is
intentional — it rejects 0.0 and None alike), `atr_pct = atr / close * 100`, `confidence` mapped
through `_CONF_LEVELS`, `conf_label` retained verbatim for the categorical section, and the
four v10 features coerced through `num()`. Raise `ValueError` naming the run_id and the db path
when the query yields no usable records.

Add `split_records(records, split)` returning `(train, holdout)`. A record whose date is
strictly less than `split` is train; a record dated on or after `split` is holdout — a trade
dated exactly on the boundary belongs to the HOLDOUT (D-06, prototype `>=`). Compare on the
first ten characters of the date string so a stored timestamp cannot change the classification.
Validate that `split` matches `YYYY-MM-DD` and raise `ValueError` otherwise: string comparison
against ISO date text silently misclassifies everything if given `2024-1-1`.

Add `mean_r(records)` using `statistics.mean` (not numpy) — pure-python arithmetic is what the
prototype used and what Task 4's parity numbers were produced by.

Create `winner_loser_split.py` at the repo root, structured exactly like `seasonality_by_week.py`:
a `build_parser()` and a `main(argv=None) -> int`. Arguments per D-03: `--run-id` required,
`--split` default `2024-01-01`, `--db` default `data/scanner.db`, `--top` type int default 8,
plus `--strategy` with choices pullback/breakout defaulting to None. `main` opens the read-only
connection, loads records, and for this task prints only the trade-count line and the two
baseline mean-R lines; it catches `ValueError` and `FileNotFoundError`, prints the message to
stderr, and returns 2, mirroring the seasonality CLI's exit-2 convention. Return 0 on success.
All printed strings ASCII-only (D-06) — comments may keep the house U+2500 section rules, print
strings may not.

Create `tests/test_winner_loser_cli.py` with a fixture helper that builds a throwaway SQLite
database in `tmp_path` — create the `signals` table with only the schema-v9 column set (so the
fixture reproduces the real machine), insert a handful of rows straddling the split, and hand
back the path. Write the tracer test: invoke `main` with `--run-id` and `--db` pointed at that
fixture, assert exit 0 and that the printed trade counts match the rows inserted on each side of
the split. Fixtures come from `tmp_path` only — never from `data/scanner.db`.
  </action>
  <verify>
    <automated>python -m pytest tests/test_winner_loser_cli.py -q</automated>
  </verify>
  <done>`python winner_loser_split.py --run-id 4f4fe68_2021-01-01_20260702_090418` runs against the real schema-v9 database without raising, and prints `train(&lt;2024-01-01) n=1404  holdout(&gt;=2024-01-01) n=2409`. The tracer test passes against a tmp fixture DB.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: The analysis engine — categorical breakdown, bootstrap, train-only rule search, holdout scoring, rho</name>
  <files>scanner/winner_loser.py, tests/test_winner_loser.py</files>
  <behavior>
    - A record dated exactly on the split lands in holdout, not train (D-06).
    - Perturbing every holdout `r` value leaves every selected rule's feature, threshold, direction, train_n and train_r bit-identical — selection cannot see the holdout (D-05).
    - A feature with fewer than 200 non-null train values is reported skipped with its count and is absent from the tested set; a feature whose column was missing is reported skipped with a distinct "column absent" reason.
    - The test count equals 2 directions x 3 quantiles x the number of TESTED features — 48 for the legacy eight, 72 when all twelve are testable (D-04).
    - `FEATURES` shares no member with the outcome variables mae_r, mfe_r, holding_days, exit_px, exit_reason, post_stop_reached_target, post_stop_mfe_r, r_multiple (D-05 predictor discipline).
    - The same seed produces an identical bootstrap CI across calls; fewer than 20 records produces NaN bounds rather than a crash.
    - A perfectly rank-concordant train/holdout rule set yields Spearman rho of +1.0.
    - An empty record set raises ValueError naming the run_id; a malformed split string raises ValueError.
  </behavior>
  <action>
Write the tests in `tests/test_winner_loser.py` first, one per `<behavior>` bullet, driving them
off small hand-built record lists and tmp SQLite fixtures. Follow `tests/test_seasonality.py`
for structure: plain functions, `pytest.approx` for floats, an explicit docstring on any test
that encodes a project lesson.

Then complete `scanner/winner_loser.py`. Every numeric step is a port, not a redesign —
transcribe the prototype's arithmetic and change only its packaging.

Port the month-block bootstrap as `bootstrap_ci(records, rng, iters=2000)`: group r-values by
the first seven characters of the date (year-month), then for each iteration resample as many
month keys as exist, with replacement, concatenating each drawn month's whole block, and take
the mean; sort and take the 2.5th/97.5th percentile by the prototype's integer index
(`k = int(iters * 0.025)`, lower `out[k]`, upper `out[-k-1]`). Return NaN bounds when fewer than
20 records. Month blocks, not per-trade resampling — dozens of trades fire the same day and
share one market move, so a naive standard error is far too small (D-05).

Port the quantile helper verbatim, including its index formula
`max(0, min(len(v)-1, int(round(p * (len(v)-1)))))` on the sorted values. Do NOT substitute
`numpy.percentile` or `statistics.quantiles` — they interpolate, this does not, and the
published reference threshold `atr_pct >= 3.47` is a product of this exact formula. A silent
change here is precisely the failure mode Task 4 exists to catch.

Add `select_rules(train, features, skipped_out)` whose signature takes the train list and
nothing else — the holdout is structurally unreachable from rule selection, which is the
cheapest way to guarantee D-05 rather than merely test for it. For each feature, collect the
non-null train values; when there are fewer than 200, record the skip (feature name, count,
reason) and continue without testing it. For each surviving feature, walk the three quantiles
(0.25 "Q1", 0.50 "median", 0.75 "Q3") and both directions (">=", "<"), incrementing the test
counter once per enumerated rule BEFORE the kept-size filter (the prototype counts enumeration,
not survival — this is what makes the reference count 48), then discard any rule keeping fewer
than 150 train rows. Return the candidate rules sorted by descending train mean R, plus the test
count.

Add `score_on_holdout(rules, holdout, rng, top)` applying each of the top-N rules UNCHANGED to
the holdout — same feature, same threshold, same direction, no re-fitting — recording holdout n,
holdout mean R, and the bootstrap CI.

Add `spearman_rho(pairs)` porting the rank formula (`1 - 6*d2/(n*(n*n-1))`) over every candidate
rule whose holdout membership reaches 150, returning None when fewer than five pairs qualify.
Rank ties are handled the way the prototype handled them — by dict-of-sorted-value position —
keep that, do not upgrade to average ranks.

Add the `Rule` and `WinnerLoserResult` dataclasses carrying everything the report needs: run_id,
db path, split, strategy filter, train/holdout counts, both baselines and CIs, the categorical
rows (conf_label across LOW/MEDIUM/HIGH and industry_above_50ma across 0.0/1.0, each with train
n, train R, holdout n, holdout R), the tested feature list, the skipped feature list with
reasons, the test count, the top rules, the rho and its rule count.

Tie it together in `analyze(records, split="2024-01-01", features=FEATURES, top=8, iters=2000,
seed=11, missing_columns=())`. Seed a dedicated `random.Random(seed)` instance rather than
touching the global `random` module state, and thread it through every bootstrap call. Fold
`missing_columns` (from `get_analysis_signals`) into the skipped list with the distinct
"column absent" reason before selection runs. The `features` parameter exists so Task 4 can
re-run the legacy eight and isolate the refactor from the feature addition — keep it a real
parameter, not a constant.

Raise `ValueError` with an actionable message when train or holdout ends up empty (a valid
run_id whose trades all fall on one side of the split must say so, not print NaN rows).
  </action>
  <verify>
    <automated>python -m pytest tests/test_winner_loser.py -q</automated>
  </verify>
  <done>All `<behavior>` bullets have a passing test. `analyze` returns a fully populated result for a fixture spanning the split, and rule selection is structurally incapable of reading holdout rows.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: ASCII report rendering, CLI error paths, and the cp1252 regression gate</name>
  <files>scanner/winner_loser.py, winner_loser_split.py, tests/test_winner_loser_cli.py, tests/_regression_cp1252_winner_loser_helper.py</files>
  <behavior>
    - The rendered report survives a real stdout stream bound to cp1252, on both the success path and the error path, in a subprocess.
    - An unknown run_id exits 2 with a message naming the run_id on stderr and prints no result table.
    - A missing database file exits 2 with a message naming the path, not a SQLite traceback.
    - The database file's bytes are identical before and after a successful run.
    - `--top 3` prints three rule rows; `--strategy breakout` excludes pullback rows from the counts.
    - The features line states how many features are defined, how many were tested and how many were skipped, and names each skipped feature with its reason.
  </behavior>
  <action>
Add the report builders to `scanner/winner_loser.py` as string-returning functions —
`render_report(result)` composing the sections. String building lives in the module (that is what
makes it testable without subprocess gymnastics) and `print()` lives only in the CLI; this is the
same division `scanner/seasonality.py` uses with `render_weeks_table` / `build_summary`, and it
satisfies D-01's "no printing in the module" while keeping the CLI thin.

Sections, in the prototype's order: the trade-count line; both baseline lines with their CIs;
the categorical table; the coverage and multiple-comparison lines; the top-N rule table with
holdout columns and holdout CI; the rank-correlation line.

Two content requirements beyond the prototype:

The coverage line must make the D-04 skip visible. Print how many features are defined, how many
were tested and how many were skipped, then one line per skipped feature naming it and its reason
— either that its column is absent from this database, or that it had too few non-null train
values, with the count. Against the live schema-v9 database this reports twelve defined, eight
tested, four skipped for absent columns. Silently testing eight while a header implies twelve
would be a lie about coverage, and that is the whole reason the guard is being kept.

The multiple-comparison line must report the actual enumerated test count and the expected count
of spurious winners at the 5% level, as the prototype did. That number growing with the feature
set is information the user specifically wants to see, so it is derived from the live count and
never hardcoded.

Every character in every rendered string must be ASCII (D-06). Use hyphens for rules and arrows,
not box-drawing or em-dashes. Milestone v1.1 shipped a crash where one U+2500 in a print raised
`UnicodeEncodeError` on a cp1252 stream and 319 passing tests missed it, because `capsys`
captures through an in-memory buffer that bypasses real stream encoding entirely. Comments inside
these files may keep the house section-rule style; rendered output may not.

Finish `winner_loser_split.py`: print `render_report(...)` and return 0; keep the `ValueError` /
`FileNotFoundError` to stderr-and-exit-2 handling from Task 1 as the only error surface.

Create `tests/_regression_cp1252_winner_loser_helper.py`, modeled directly on the existing
`tests/_regression_cp1252_helper.py`. The leading underscore keeps it out of pytest collection.
It inserts the repo root at the front of `sys.path`, builds its own self-contained tmp fixture
database at a path given on argv (self-contained by precedent — the existing helper duplicates
its fixtures rather than importing from a test module), and takes a second argv value selecting
the success path or the unknown-run-id path, then calls `winner_loser_split.main` and returns its
exit code. Make the fixture large enough that at least one feature clears both the 200-non-null
and 150-kept thresholds, so the rule table and rho line actually render and their characters are
exercised.

In `tests/test_winner_loser_cli.py`, add the regression test parametrized over both paths: run
the helper via `subprocess.run` with `cwd` at the repo root and an environment copy setting
`PYTHONIOENCODING` to cp1252 and removing `PYTHONUTF8`, with `capture_output`, `text=True` and a
timeout. Assert the expected exit code and that no `UnicodeEncodeError` appears in stderr. Then
add the remaining CLI tests from `<behavior>`: unknown run_id, missing db path, `--top`,
`--strategy`, and the byte-identity check that hashes the fixture database before and after a
successful run and compares the digests.
  </action>
  <verify>
    <automated>python -m pytest tests/test_winner_loser_cli.py -q</automated>
  </verify>
  <done>Both cp1252 subprocess invocations exit with their expected codes and clean stderr. Every error path returns 2 with one readable line. The fixture database hashes identically before and after a run.</done>
</task>

<task type="auto">
  <name>Task 4: Reference-run parity against the prototype, docs, and full suite</name>
  <files>tests/test_winner_loser.py, CLAUDE.md</files>
  <precondition>`data/scanner.db` exists and contains run_id `4f4fe68_2021-01-01_20260702_090418` with 3813 qualified, resolved rows (verified 2026-08-19: 1404 train / 2409 holdout, schema v9).</precondition>
  <action>
Prove the refactor did not change the answer. This is the task that justifies the other three.

Run the promoted code against the reference run restricted to `LEGACY_FEATURES`, so the
comparison isolates the refactor from the feature addition. Use a short throwaway invocation
(`python -c`, or `winner_loser_split.py` if you add nothing to its surface to enable this — do
not add a CLI flag for it; `analyze(..., features=LEGACY_FEATURES)` is the intended entry point)
against run_id `4f4fe68_2021-01-01_20260702_090418` with the default split, seed 11.

Compare against the prototype's published output, all six of which are deterministic and
RNG-independent:

| Quantity | Expected |
|---|---|
| train n | 1404 |
| holdout n | 2409 |
| train baseline mean R | -0.136 |
| holdout baseline mean R | +0.159 |
| enumerated tests | 48 |
| best train rule | `atr_pct >= 3.47` |
| that rule, train mean R | +0.026 |
| that rule, holdout mean R | -0.085 |
| Spearman rho | -0.455 |

If every value matches, record the actual printed numbers in the SUMMARY as evidence.

**If any value does not match: do NOT adjust the analysis code to force agreement.** Report the
exact deltas in the SUMMARY and stop for a human decision. A refactor that quietly changes
results is the primary risk this whole task is guarding against, and the most likely innocent
cause of a mismatch is that the reference run was re-executed after quick task 260819-g5h
introduced the minimum stop-distance floor, which would legitimately move every stored
`r_multiple`. That is a data question, not a code question, and the user decides it.

Also confirm on this same real run that the four schema-v10 features are reported skipped with
the absent-column reason and that the coverage line reads twelve defined / eight tested / four
skipped — the live database is schema v9 (see `<discovered_state>`), which makes this run the
natural end-to-end proof of the D-04 skip reporting.

Encode the parity check as a test in `tests/test_winner_loser.py` guarded by
`pytest.mark.skipif` on the absence of `data/scanner.db` or of the reference run inside it, so a
clean offline checkout skips it and `pytest -q` stays green everywhere. Put the expected values
in a module-level table with a docstring stating where they came from and that a future
mismatch means the data moved, not that the constants are stale.

Add one line to the CLI quick reference block in `CLAUDE.md` showing the invocation with
`--run-id` and `--split`, described as a read-only train/holdout feature diagnostic. Keep the
edit to that block. If you notice other drift in `CLAUDE.md` while you are in there — the schema
version stated in prose is one version behind the DDL — note it in the SUMMARY rather than
fixing it here; it is outside this task.

Finish with the full suite.
  </action>
  <verify>
    <automated>python -m pytest -q</automated>
    <human-check>The parity table in the SUMMARY shows the reference run reproducing all nine published values, or an explicit delta report with no code changed to chase it.</human-check>
  </verify>
  <done>`pytest -q` is green with the new tests added on top of the existing 358. The reference-run parity result is recorded in the SUMMARY. `CLAUDE.md` documents the new command.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| shell -> CLI arguments | `--run-id`, `--strategy`, `--split`, `--db` are user-supplied strings reaching SQL and filesystem calls |
| CLI -> data/scanner.db | a read path over 192k rows of real signal history and live-trade outcomes |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-jjh-01 | Tampering | `store_db.get_analysis_signals` | medium | mitigate | `run_id` and `strategy` bound as SQL parameters; the only identifier ever interpolated is a column name drawn from the intersection with `PRAGMA table_info`, never from user input |
| T-jjh-02 | Tampering | `store_db.get_readonly_connection` | high | mitigate | connection opened with the `file:...?mode=ro` URI so SQLite refuses writes at the engine level; no `migrate()` call, no `mkdir`; Task 3 asserts the database file is byte-identical after a run |
| T-jjh-03 | Denial of Service | `--db` path handling | low | mitigate | explicit `FileNotFoundError` before connecting, so a typo'd path fails fast with a readable message rather than creating an empty database that yields a silent zero-row analysis |
| T-jjh-04 | Tampering | dependency supply chain | low | accept | no package installs — the implementation uses only stdlib `sqlite3`, `statistics`, `random`, `argparse` plus modules already vendored in this repo |
</threat_model>

<verification>
- `pytest -q` green, offline, on a clean checkout (the parity test skips when `data/scanner.db` is absent).
- `python winner_loser_split.py --run-id 4f4fe68_2021-01-01_20260702_090418` produces the full report against the live schema-v9 database, naming the four absent-column features as skipped.
- No SQL string exists outside `scanner/store_db.py`.
- No printed string in either new file contains a non-ASCII character.
</verification>

<success_criteria>
- `scanner/winner_loser.py` and `winner_loser_split.py` exist, are tracked in git (D-02), and mirror the seasonality logic/CLI split (D-01).
- Twelve features defined, skips reported explicitly, test count derived from what was actually tested (D-04).
- Month-block bootstrap, train-only selection, no model fitting, nothing per-ticker, and no outcome variable used as a predictor (D-05).
- All output ASCII, gated by a subprocess cp1252 test rather than capsys (D-06).
- The reference run reproduces the prototype's published numbers under the legacy eight features.
</success_criteria>

<output>
Create `.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/260819-jjh-SUMMARY.md` when done.

The SUMMARY must contain the Task 4 parity table with the actual observed values beside the
expected ones — that record is the artifact that lets a future session trust this tool.

Note for the future, do not build now (CONTEXT "Not in scope"): multi-fold or rolling-window
validation. A single split conflates "does this generalize" with "did the regime change"
(train -0.136 vs holdout +0.159). Worth revisiting only if something survives the simple version.
</output>
