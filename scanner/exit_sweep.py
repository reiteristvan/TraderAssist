"""Exit-rule sweep diagnostic engine (analysis logic only). Read-only.

Answers "does a different exit rule improve this strategy?" against an
existing backtest run directory -- three sweep modes (time stop, breakeven
stop, fixed R-multiple target) sharing one bar-walking replica.

Why the equivalence gate exists: the time-stop mode uses the REAL
scanner.simulate.simulate_trades directly (time_stop is already one of its
parameters, so there is no reimplementation risk there). Breakeven and
fixed-target modes are NOT parameters of the real simulator, so this module
carries a REPLICA of its bar-precedence loop (simulate_variant). A replica
that silently drifts from the real simulator would produce confident, wrong
trading conclusions. check_equivalence therefore runs a trade-by-trade
comparison against a LIVE simulate_trades call, on the same signals, before
a single breakeven or target number is ever reported -- see
exit_rule_sweep.py for how a failed gate suppresses every table.

Promoted from three throwaway prototypes (exit_sweep.py, exit_be.py,
exit_tgt.py) staged at
.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/
(2026-08-19) -- see that task directory and
.planning/research/2026-08-19-signal-quality-investigation.md for the
original run and findings.

See scanner/winner_loser.py + winner_loser_split.py for the logic/CLI split
this module mirrors: no argparse, no printing here (CLI at
exit_rule_sweep.py).

ASCII only, whole file, including comments -- this module's printed report
strings must survive any stream encoding, and enforcing that on the whole
file lets one automated check cover it instead of a human eyeballing which
strings reach a stream (260712-h7l precedent).
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from scanner.data_store import get_history
from scanner.simulate import Signal, simulate_trades
from scanner.targets import apply_min_stop_floor

# The anchor time stop is the strategy's current setting and the time stop
# the equivalence gate always runs at, even in --mode time (decision (b)).
ANCHOR_TIME_STOP = 10

# Reproduces the exit_sweep.py prototype's time-stop grid (2026-08-19).
# Changing this changes what the reference-run numbers recorded in the
# 2026-08-19 signal-quality investigation mean.
TIME_STOPS = (5, 8, 10, 15, 20, 30, 40)

DEFAULT_SPLIT = "2024-01-01"

EQUIVALENCE_TOLERANCE = 1e-9

# Breakeven and fixed-target grids reproduce the exit_be.py / exit_tgt.py
# prototypes' grids (2026-08-19). Changing them invalidates the reference
# numbers recorded in the 2026-08-19 signal-quality investigation.
BE_TRIGGERS = (0.5, 0.75, 1.0, 1.5, 2.0)
BE_TIME_STOPS = (10, 20, 40)
TARGET_MULTIPLES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
TARGET_TIME_STOPS = (10, 20)
REPLICA_TIME_STOPS = tuple(sorted(set(BE_TIME_STOPS) | set(TARGET_TIME_STOPS)))


def validate_split(split: str) -> None:
    """Raise ValueError naming the bad value unless `split` is YYYY-MM-DD.

    A plain string comparison against ISO date text (as summarize() and
    sweep_time() perform) silently misclassifies every trade when handed a
    non-padded date such as "2024-1-1" -- this must be caught before any
    work happens, not discovered later as a wrong-looking table.
    """
    if len(split) != 10 or split[4] != "-" or split[7] != "-":
        raise ValueError(f"--split must be YYYY-MM-DD, got {split!r}")
    year, month, day = split[:4], split[5:7], split[8:10]
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise ValueError(f"--split must be YYYY-MM-DD, got {split!r}")


def load_signals(
    run_dir: str, qualified_only: bool = True, strategy: Optional[str] = None
) -> list[Signal]:
    """Load Signal objects from `<run_dir>/signals.parquet`. Read-only.

    Normalizes the `date` column the way the prototype did: pass a
    datetime.date through, parse an ISO string with date.fromisoformat, and
    call .date() on anything exposing it. failed_gates is set to [] -- the
    parquet stores a serialized form this tool has no use for.

    Raises FileNotFoundError naming the path when the run directory or the
    parquet file is absent, and ValueError naming the run dir when the
    filter leaves zero signals -- never returns an empty list that would
    render as a table of NaNs.
    """
    run_dir_path = Path(run_dir)
    parquet_path = run_dir_path / "signals.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(str(parquet_path))

    df = pd.read_parquet(parquet_path)
    if qualified_only:
        df = df[df["qualified"]]
    if strategy is not None:
        df = df[df["strategy"] == strategy]

    if df.empty:
        raise ValueError(
            f"No signals remain in {run_dir!r} after filtering "
            f"(qualified_only={qualified_only}, strategy={strategy!r})"
        )

    signals: list[Signal] = []
    for row in df.itertuples(index=False):
        sig_date = row.date
        if isinstance(sig_date, str):
            sig_date = date.fromisoformat(sig_date)
        elif hasattr(sig_date, "date"):
            sig_date = sig_date.date()
        signals.append(Signal(
            date=sig_date,
            ticker=row.ticker,
            strategy=row.strategy,
            score=float(row.score),
            confidence=row.confidence,
            stop=float(row.stop),
            target=float(row.target),
            atr=float(row.atr),
            qualified=bool(row.qualified),
            failed_gates=[],
            close=float(row.close),
        ))
    return signals


def make_bars_provider() -> Callable[[str], Optional[pd.DataFrame]]:
    """Return an lru_cache-wrapped (ticker) -> DataFrame | None callable.

    A module-level factory (not a module-level cache) so tests and the
    cp1252 regression helper can substitute a dict-backed provider without
    touching the Parquet cache. Every sweep/gate function below takes
    bars_provider as an explicit parameter -- nothing here reaches into the
    price cache implicitly.
    """
    @lru_cache(maxsize=None)
    def _bars(ticker: str) -> Optional[pd.DataFrame]:
        return get_history(ticker)

    return _bars


@dataclass
class VariantTrade:
    """One resolved trade from simulate_variant. Unresolved cases (gap
    skips, missing bars) are simply absent from the output list."""
    signal_date: str
    ticker: str
    strategy: str
    entry_px: float
    exit_px: float
    r_multiple: float
    exit_reason: str


def simulate_variant(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    time_stop: int = ANCHOR_TIME_STOP,
    be_trigger: Optional[float] = None,
    target_multiple: Optional[float] = None,
) -> list[VariantTrade]:
    """THE REPLICA. Mirrors scanner/simulate.py's bar-precedence loop, plus
    an optional breakeven rule and an optional fixed-target override.

    Returns resolved trades only -- gap-skips, missing-bar and
    no-future-bar cases are simply absent, matching the prototypes. The
    statement order below is not stylistic, it is the contract:

      1. bars = bars_provider(ticker); skip when None or empty.
      2. future = bars strictly after the signal date (index.normalize() >
         signal timestamp.normalize(), matching simulate.py exactly).
      3. entry_px = open of the first future bar.
      4. Gap-down guard against the PUBLISHED stop: entry_px <= sig.stop ->
         skip. This runs BEFORE the floor is applied, so a widened stop can
         never rescue a gap-skipped trade.
      5. effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr);
         risk = entry_px - effective_stop.
      6. effective_target = sig.target, or entry_px + target_multiple*risk
         when a target override is given.
      7. Gap-up guard against the EFFECTIVE target: entry_px >=
         effective_target -> skip. With no override this is bit-identical
         to simulate.py's entry_px >= sig.target check. The real simulator
         tests gap-up before gap-down; both branches are skips either way,
         so the resolved set is unaffected by which guard runs first.
      8. Walk bars from index 0: stop hit (low <= current stop) exits first
         -- pessimistic on a bar where both stop and target are touched --
         then target hit (high >= effective_target), then the time-stop
         close (bar_idx == time_stop - 1).
      9. Breakeven arming happens AFTER the exit tests, at the bottom of
         the loop body: once a bar's high reaches entry_px +
         be_trigger*risk, the stop moves to entry_px for SUBSEQUENT bars.
         The trigger bar itself can therefore never exit at breakeven --
         pessimistic arming.
     10. Ran out of bars without an exit -> exit at the last available
         close, reason "time_stop".
     11. r_multiple = (exit_px - entry_px) / risk.

    Bars are read once per signal as numpy float64 arrays rather than via
    future.iloc[bar_idx] -- materially faster over dozens of sweep passes
    and bit-identical to the iloc form. This optimization is safe because
    check_equivalence proves it equivalent to the real simulator every run.
    """
    out: list[VariantTrade] = []

    for sig in signals:
        bars = bars_provider(sig.ticker)
        if bars is None or bars.empty:
            continue

        sig_ts = pd.Timestamp(sig.date)
        future = bars[bars.index.normalize() > sig_ts.normalize()]
        if future.empty:
            continue

        entry_px = float(future.iloc[0]["Open"])

        if entry_px <= sig.stop:
            continue

        effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)
        risk = entry_px - effective_stop

        effective_target = (
            sig.target if target_multiple is None
            else entry_px + target_multiple * risk
        )

        if entry_px >= effective_target:
            continue

        lows = future["Low"].to_numpy(dtype=float)
        highs = future["High"].to_numpy(dtype=float)
        closes = future["Close"].to_numpy(dtype=float)
        n_bars = len(future)

        cur_stop = effective_stop
        armed = False
        exit_px: Optional[float] = None
        exit_reason: Optional[str] = None

        for bar_idx in range(n_bars):
            low = lows[bar_idx]
            high = highs[bar_idx]
            close = closes[bar_idx]

            if low <= cur_stop:
                exit_px = cur_stop
                exit_reason = "be_stop" if armed else "stop"
                break
            elif high >= effective_target:
                exit_px = effective_target
                exit_reason = "target"
                break
            elif bar_idx == time_stop - 1:
                exit_px = close
                exit_reason = "time_stop"
                break

            if (
                be_trigger is not None
                and not armed
                and high >= entry_px + be_trigger * risk
            ):
                armed = True
                cur_stop = entry_px

        if exit_reason is None:
            exit_px = closes[-1]
            exit_reason = "time_stop"

        r_multiple = (exit_px - entry_px) / risk
        out.append(VariantTrade(
            signal_date=str(sig.date),
            ticker=sig.ticker,
            strategy=sig.strategy,
            entry_px=entry_px,
            exit_px=exit_px,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
        ))

    return out


@dataclass
class EquivalenceReport:
    time_stop: int
    n_real: int
    n_variant: int
    missing_keys: list
    extra_keys: list
    mismatches: list
    max_abs_diff: float
    ok: bool


def check_equivalence(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    time_stop: int = ANCHOR_TIME_STOP,
    variant_fn: Callable[..., list[VariantTrade]] = simulate_variant,
    tolerance: float = EQUIVALENCE_TOLERANCE,
) -> EquivalenceReport:
    """The point of the whole tool. Compares the replica (with the
    breakeven rule disabled and no target override) against a LIVE
    scanner.simulate.simulate_trades call on the SAME signals, trade by
    trade, keyed by (signal_date, ticker, strategy) and restricted to
    trades that resolved to a non-None R.

    `ok` is True only when the key sets are identical, no exit_reason
    differs, and every R agrees within `tolerance`. Up to five example
    mismatches are kept for rendering, but every mismatching key counts
    toward `ok` regardless of how many are kept.

    `variant_fn` is an injected parameter so drift-detection tests can hand
    this a deliberately wrong bar loop. This function never prints or
    raises -- it returns a verdict; the CLI decides what to do with it.
    """
    real_trades = simulate_trades(signals, bars_provider, time_stop=time_stop)
    variant_trades = variant_fn(
        signals, bars_provider, time_stop=time_stop,
        be_trigger=None, target_multiple=None,
    )

    real_by_key = {}
    for t in real_trades:
        if t.r_multiple is None:
            continue
        key = (str(t.signal_date), t.ticker, t.strategy)
        real_by_key[key] = t

    variant_by_key = {}
    for t in variant_trades:
        key = (t.signal_date, t.ticker, t.strategy)
        variant_by_key[key] = t

    real_keys = set(real_by_key)
    variant_keys = set(variant_by_key)
    missing_keys = sorted(real_keys - variant_keys)
    extra_keys = sorted(variant_keys - real_keys)

    mismatches = []
    total_mismatches = 0
    max_abs_diff = 0.0
    for key in sorted(real_keys & variant_keys):
        rt = real_by_key[key]
        vt = variant_by_key[key]
        diff = abs(rt.r_multiple - vt.r_multiple)
        if diff > max_abs_diff:
            max_abs_diff = diff
        reason_mismatch = rt.exit_reason != vt.exit_reason
        r_mismatch = diff > tolerance
        if reason_mismatch or r_mismatch:
            total_mismatches += 1
            if len(mismatches) < 5:
                mismatches.append((
                    key, rt.exit_reason, vt.exit_reason,
                    rt.r_multiple, vt.r_multiple, diff,
                ))

    ok = not missing_keys and not extra_keys and total_mismatches == 0

    return EquivalenceReport(
        time_stop=time_stop,
        n_real=len(real_by_key),
        n_variant=len(variant_by_key),
        missing_keys=missing_keys,
        extra_keys=extra_keys,
        mismatches=mismatches,
        max_abs_diff=max_abs_diff,
        ok=ok,
    )


def summarize(trades, split: str) -> dict:
    """Return (n, meanR, trainR, holdR, win%, exit-reason mix) for resolved
    trades. Accepts either scanner.simulate.Trade or VariantTrade objects.

    Keeps the prototype's arithmetic: statistics.mean (not numpy), resolved
    trades only (r_multiple is not None), train is
    str(signal_date) < split and holdout is >=, win% is r > 0. `mix` is a
    raw collections.Counter of exit reasons -- callers that want be_stop
    folded into the stop bucket (breakeven mode) do that at render time,
    since it is a stop.
    """
    resolved = [t for t in trades if t.r_multiple is not None]
    rs = [t.r_multiple for t in resolved]
    train = [t.r_multiple for t in resolved if str(t.signal_date) < split]
    hold = [t.r_multiple for t in resolved if str(t.signal_date) >= split]
    mix = Counter(t.exit_reason for t in resolved)
    return {
        "n": len(resolved),
        "mean": statistics.mean(rs) if rs else float("nan"),
        "train": statistics.mean(train) if train else float("nan"),
        "hold": statistics.mean(hold) if hold else float("nan"),
        "win": 100 * sum(1 for r in rs if r > 0) / len(rs) if rs else float("nan"),
        "mix": mix,
    }


def sweep_time(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    time_stops=TIME_STOPS,
    split: str = DEFAULT_SPLIT,
) -> list[dict]:
    """One row per time stop, using the REAL simulate_trades -- never the
    replica. time_stop is already a parameter of the real simulator, so
    reimplementing it here would add risk for nothing.
    """
    rows = []
    for ts in time_stops:
        trades = simulate_trades(signals, bars_provider, time_stop=ts)
        row = summarize(trades, split)
        row["time_stop"] = ts
        rows.append(row)
    return rows


def _labeled_row(label: str, trades, split: str) -> dict:
    row = summarize(trades, split)
    row["label"] = label
    return row


# At time stops other than the anchor, the prototype sweeps only the
# (1.0, 1.5) triggers -- keep that so the output stays diffable against the
# prototype output line for line.
_BE_SECONDARY_TRIGGERS = (1.0, 1.5)


def sweep_breakeven(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    split: str = DEFAULT_SPLIT,
    triggers=BE_TRIGGERS,
    time_stops=BE_TIME_STOPS,
) -> list[dict]:
    """One baseline row per time stop (replica with be_trigger=None),
    followed by one row per trigger. Reuses simulate_variant unchanged --
    no second bar loop.
    """
    rows = []
    for ts in time_stops:
        baseline = simulate_variant(signals, bars_provider, time_stop=ts, be_trigger=None)
        rows.append(_labeled_row(f"baseline ts={ts}", baseline, split))
        trig_set = triggers if ts == ANCHOR_TIME_STOP else _BE_SECONDARY_TRIGGERS
        for k in trig_set:
            variant = simulate_variant(signals, bars_provider, time_stop=ts, be_trigger=k)
            rows.append(_labeled_row(f"BE@{k}R ts={ts}", variant, split))
    return rows


def sweep_target(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    split: str = DEFAULT_SPLIT,
    multiples=TARGET_MULTIPLES,
    time_stops=TARGET_TIME_STOPS,
) -> list[dict]:
    """One "current (resistance)" row per time stop (target_multiple=None),
    followed by one row per fixed multiple. Reuses simulate_variant
    unchanged -- no second bar loop.

    Because the target override moves the gap-up guard onto the synthetic
    target, override rows can cover MORE trades than the baseline row for
    the same time stop: a signal whose entry gapped past the published
    resistance target is re-admitted once a wider synthetic target no
    longer excludes it. This is the prototype's behavior, preserved
    deliberately -- see render_target_table's footnote.
    """
    rows = []
    for ts in time_stops:
        baseline = simulate_variant(signals, bars_provider, time_stop=ts, target_multiple=None)
        rows.append(_labeled_row(f"current (resistance) ts={ts}", baseline, split))
        for k in multiples:
            variant = simulate_variant(signals, bars_provider, time_stop=ts, target_multiple=k)
            rows.append(_labeled_row(f"target={k}R ts={ts}", variant, split))
    return rows


# -- ASCII report rendering --------------------------------------------------
# String building lives here (testable without subprocess gymnastics);
# print() lives only in exit_rule_sweep.py. Every character in every string
# returned below must be ASCII -- milestone v1.1 shipped a crash where one
# non-ASCII character in a print raised UnicodeEncodeError on a cp1252
# stream, and a passing suite missed it because capsys bypasses real stream
# encoding entirely. Comments may use plain hyphens for section rules;
# these rendered strings hold to the same ASCII rule as the rest of the
# file.


def render_header(run_dir: str, split: str, strategy: Optional[str], n_signals: int) -> str:
    strategy_label = strategy if strategy else "both"
    return (
        f"run_dir={run_dir}  split={split}  strategy={strategy_label}  "
        f"signals={n_signals}"
    )


def render_gate_section(reports: list[EquivalenceReport]) -> str:
    lines = []
    ok = all(r.ok for r in reports)
    lines.append("EQUIVALENCE GATE: PASS" if ok else "EQUIVALENCE GATE FAILED")
    for r in reports:
        status = "PASS" if r.ok else "FAIL"
        lines.append(
            f"  time_stop={r.time_stop}: {status}  n_real={r.n_real}  "
            f"n_variant={r.n_variant}  missing={len(r.missing_keys)}  "
            f"extra={len(r.extra_keys)}  max_abs_diff={r.max_abs_diff:.2e}"
        )
        for key, real_reason, variant_reason, real_r, variant_r, diff in r.mismatches:
            lines.append(
                f"    mismatch {key}: real_reason={real_reason}  "
                f"variant_reason={variant_reason}  real_r={real_r:+.6f}  "
                f"variant_r={variant_r:+.6f}  diff={diff:.2e}"
            )
    return "\n".join(lines)


def render_time_table(rows: list[dict]) -> str:
    lines = [
        f"{'time_stop':>10}{'n':>7}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}"
        f"{'stop%':>7}{'tgt%':>7}{'time%':>7}"
    ]
    for row in rows:
        mix = row["mix"]
        tot = sum(mix.values())
        stop_pct = 100 * mix.get("stop", 0) / tot if tot else float("nan")
        tgt_pct = 100 * mix.get("target", 0) / tot if tot else float("nan")
        time_pct = 100 * mix.get("time_stop", 0) / tot if tot else float("nan")
        lines.append(
            f"{row['time_stop']:>10}{row['n']:>7}{row['mean']:>+9.4f}"
            f"{row['train']:>+9.4f}{row['hold']:>+9.4f}{row['win']:>7.1f}"
            f"{stop_pct:>7.1f}{tgt_pct:>7.1f}{time_pct:>7.1f}"
        )
    return "\n".join(lines)


def render_breakeven_table(rows: list[dict]) -> str:
    lines = [
        f"{'variant':22s}{'n':>6}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}"
        f"{'stop%':>7}{'tgt%':>7}{'time%':>7}"
    ]
    for row in rows:
        mix = row["mix"]
        tot = sum(mix.values())
        # be_stop is folded into the stop bucket for display -- it is a
        # stop, just one whose price moved to entry after arming.
        stop_pct = 100 * (mix.get("stop", 0) + mix.get("be_stop", 0)) / tot if tot else float("nan")
        tgt_pct = 100 * mix.get("target", 0) / tot if tot else float("nan")
        time_pct = 100 * mix.get("time_stop", 0) / tot if tot else float("nan")
        lines.append(
            f"{row['label']:22s}{row['n']:>6}{row['mean']:>+9.4f}"
            f"{row['train']:>+9.4f}{row['hold']:>+9.4f}{row['win']:>7.1f}"
            f"{stop_pct:>7.1f}{tgt_pct:>7.1f}{time_pct:>7.1f}"
        )
    return "\n".join(lines)


_TARGET_FOOTNOTE = (
    "note: fixed-multiple rows above re-admit trades whose entry gapped "
    "past the published resistance target, so n is not comparable row to "
    "row against the current-target baseline"
)


def render_target_table(rows: list[dict]) -> str:
    lines = [
        f"{'variant':22s}{'n':>6}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}"
        f"{'tgt-hit%':>9}"
    ]
    for row in rows:
        mix = row["mix"]
        tot = sum(mix.values())
        tgt_pct = 100 * mix.get("target", 0) / tot if tot else float("nan")
        lines.append(
            f"{row['label']:22s}{row['n']:>6}{row['mean']:>+9.4f}"
            f"{row['train']:>+9.4f}{row['hold']:>+9.4f}{row['win']:>7.1f}"
            f"{tgt_pct:>9.1f}"
        )
    lines.append(_TARGET_FOOTNOTE)
    return "\n".join(lines)


# The single most reusable output of the 2026-08-19 signal-quality
# investigation: at ~3,800 trades with heavy time clustering, the baseline
# 95% CI (~+/-0.2R) dwarfs the ~0.03R effect sizes every sweep above is
# hunting for. Printed under every table so the next reader sees it where
# it matters, not buried in a research document nobody re-reads.
STANDING_CAVEAT = (
    "caveat: at this sample size the baseline 95% CI is about +/-0.2R "
    "against effect sizes near 0.03R -- a table ordering above is not "
    "evidence on its own"
)


def render_report(
    mode: str,
    header: str,
    reports: list[EquivalenceReport],
    time_rows: Optional[list[dict]] = None,
    be_rows: Optional[list[dict]] = None,
    target_rows: Optional[list[dict]] = None,
) -> str:
    """Compose the full report string: header, gate section, then whichever
    tables `mode` selected, plus the standing statistical-power caveat.
    Never prints -- callers on a failed gate should not reach this function
    with any rows at all; see exit_rule_sweep.py's suppress-on-failure path.
    """
    sections = [header, render_gate_section(reports)]
    if mode in ("time", "all") and time_rows is not None:
        sections.append(render_time_table(time_rows))
    if mode in ("breakeven", "all") and be_rows is not None:
        sections.append(render_breakeven_table(be_rows))
    if mode in ("target", "all") and target_rows is not None:
        sections.append(render_target_table(target_rows))
    sections.append(STANDING_CAVEAT)
    return "\n\n".join(sections)
