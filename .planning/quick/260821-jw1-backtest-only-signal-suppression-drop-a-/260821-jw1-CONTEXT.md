# Quick Task 260821-jw1 — Context

**Task:** Backtest-only signal suppression — drop a signal when the same ticker
already produced >= 3 signals in the trailing 10 calendar days.

**Motivation (user):** Prior backtest review showed that clusters of repeated
signals on the same ticker within a short window were net-loss-producing. This
is a hypothesis test, not an accepted edge — it must be measurable A/B against
the current behavior on the same commit.

## Locked decisions (do not revisit)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Which signals count toward the cluster, and which get suppressed | **Qualified only.** Only `qualified=True` signals increment the per-ticker window, and only qualified signals can be suppressed. Near-misses (`qualified=False`) are neither counted nor dropped. | Keeps the near-miss control arm identical to prior runs so the qualified-vs-near-miss comparison stays readable. |
| D2 | Does a suppressed signal still count toward the window for later signals | **Yes.** A signal that is suppressed still records its date into the ticker's window. | The hypothesis is that the *cluster* is the loss-maker, so the whole cluster must be silenced. Not counting suppressions makes a leaky bucket that still emits ~3 of every 4 signals. |
| D3 | Delivery mechanism | **CLI flag, default OFF.** `--cluster-limit N` and `--cluster-window D`, disabled by default. Setting must be recorded in `run_meta.json`. | Enables A/B on a single commit and keeps existing/prior runs bit-reproducible without passing new flags. |

## Scope boundaries (user-stated, hard)

- **Backtest only.** Do NOT change `scanner/core.py`, `scanner/strategies/*`,
  `scanner/regime.py`, `scanner/targets.py`, or any live-scan path. The nightly
  `scan.py scan` behavior must be byte-identical.
- No gate threshold or score formula changes (CLAUDE.md standing rule).
- No DB schema change / no schema version bump.
- `pytest -q` must stay green.

## Derived semantics (from D1–D3)

- Window predicate: a prior qualified signal at date `p` is inside the window for
  a candidate at date `d` when `0 < (d - p).days <= cluster_window`
  (**calendar** days, not trading sessions — the user said "calendar days").
- Suppression predicate: suppress the candidate when the count of in-window prior
  qualified signals for that ticker is `>= cluster_limit` (default limit 3,
  window 10). With limit=3, the 4th qualified signal in the window is the first
  one dropped.
- Ordering guarantee: `generate_signals()` already iterates trading days in the
  outer loop, so signals are produced in chronological order — a per-ticker list
  of prior qualified signal dates is sufficient; no re-sort is needed.
- Suppressed signals are dropped from the returned list entirely (they must not
  reach `simulate_trades()` or `signals.parquet`), but the count of suppressions
  should be surfaced so the A/B is legible.

## Verification the user cares about

The point of the change is to run the same backtest twice — once with the flag
off, once with `--cluster-limit 3 --cluster-window 10` — and compare expectancy.
So the run artifacts must make the setting and its effect visible.
