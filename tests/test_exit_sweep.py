"""Tests for scanner.exit_sweep -- the replica bar loop, the equivalence
gate that proves it matches the real simulator, and the sweep helpers.

Every fixture here is synthetic and constructed in this module or in
tmp_path. No test names a backtest run directory, the SQLite database, the
OHLCV cache directory, or the module/function this tool reads prices
through -- not in code, not in a comment, not in a docstring. Refer to the
reference run only as "the reference run" in prose.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from scanner.exit_sweep import (
    ANCHOR_TIME_STOP,
    EquivalenceReport,
    VariantTrade,
    check_equivalence,
    render_breakeven_table,
    render_target_table,
    simulate_variant,
    summarize,
    sweep_breakeven,
    sweep_target,
    sweep_time,
)
from scanner.simulate import Signal, simulate_trades


def _bars(rows, start="2024-01-02"):
    """Build a tz-naive OHLCV frame from a list of (open, high, low, close)
    tuples, one row per business day starting at `start`. Column names
    match what the real simulator and the replica both expect."""
    idx = pd.bdate_range(start=start, periods=len(rows))
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
            "Volume": [1000] * len(rows),
        },
        index=idx,
    )


def _provider(mapping):
    def provider(ticker):
        return mapping.get(ticker)
    return provider


def _sig(ticker="AAA", strategy="pullback", stop=95.0, target=110.0, atr=2.0,
         sig_date=date(2024, 1, 1)):
    return Signal(
        date=sig_date, ticker=ticker, strategy=strategy, score=50.0,
        confidence="MEDIUM", stop=stop, target=target, atr=atr,
        qualified=True, failed_gates=[], close=100.0,
    )


# -- individual behavior cases -----------------------------------------------

def test_stop_hit_only_exits_at_effective_stop():
    bars = _bars([(100.0, 101.0, 94.0, 96.0)])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "stop"
    assert t.r_multiple == pytest.approx(-1.0)


def test_target_hit_only_exits_at_target():
    bars = _bars([(100.0, 111.0, 99.0, 105.0)])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "target"
    assert t.r_multiple == pytest.approx((110.0 - 100.0) / 5.0)


def test_ambiguous_bar_stop_wins_pessimistic():
    bars = _bars([(100.0, 115.0, 90.0, 100.0)])  # low<=stop AND high>=target
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert len(trades) == 1
    assert trades[0].exit_reason == "stop"


def test_no_exit_trigger_closes_at_time_stop_minus_one():
    bars = _bars([
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 102.0, 98.0, 101.0),
        (101.0, 103.0, 99.0, 102.0),
    ])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=3)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "time_stop"
    assert t.exit_px == pytest.approx(102.0)
    assert t.r_multiple == pytest.approx((102.0 - 100.0) / 5.0)


def test_fewer_bars_than_time_stop_exits_at_last_close():
    bars = _bars([
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 102.0, 98.0, 101.0),
    ])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "time_stop"
    assert t.exit_px == pytest.approx(101.0)


def test_entry_open_at_or_above_target_is_unresolved():
    bars = _bars([(111.0, 112.0, 110.5, 111.5)])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert trades == []


def test_entry_open_at_or_below_stop_is_unresolved():
    bars = _bars([(94.0, 96.0, 93.0, 95.5)])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert trades == []


def test_adverse_gap_floors_risk_and_drives_r():
    # entry_px=95.5 gives raw risk 0.5 against published stop 95, but
    # mult*atr = 0.5*2.0 = 1.0 -> the floor widens the effective stop well
    # below the raw-risk value, and both the stop-hit test and R must use
    # that floored risk, not the naive 0.5.
    from scanner.targets import apply_min_stop_floor

    bars = _bars([(95.5, 96.0, 95.0, 96.0)])
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=1)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "time_stop"
    assert t.exit_px == pytest.approx(96.0)

    floored_stop = apply_min_stop_floor(95.0, 95.5, 2.0)
    floored_risk = 95.5 - floored_stop
    assert floored_risk > 0.5  # the floor did widen the raw 0.5 risk
    assert t.r_multiple == pytest.approx((96.0 - 95.5) / floored_risk)


def test_bars_provider_returns_none_is_unresolved():
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({}), time_stop=10)
    assert trades == []


def test_no_bars_after_signal_date_is_unresolved():
    bars = _bars([(100.0, 101.0, 99.0, 100.0)], start="2023-12-20")
    # Signal dated after every bar in the frame -> future slice is empty.
    sig = _sig(stop=95.0, target=110.0, atr=2.0, sig_date=date(2024, 6, 1))
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10)
    assert trades == []


# -- equivalence: replica must match the real simulator ----------------------

def _equivalence_fixture():
    mapping = {
        "STOP": _bars([(100.0, 101.0, 94.0, 96.0),
                        (96.0, 97.0, 95.0, 96.5),
                        (96.5, 97.5, 95.5, 97.0),
                        (97.0, 98.0, 96.0, 97.5),
                        (97.5, 98.5, 96.5, 98.0),
                        (98.0, 99.0, 97.0, 98.5),
                        (98.5, 99.5, 97.5, 99.0),
                        (99.0, 100.0, 98.0, 99.5),
                        (99.5, 100.5, 98.5, 100.0),
                        (100.0, 101.0, 99.0, 100.5)]),
        "TARGET": _bars([(100.0, 102.0, 99.0, 101.0),
                          (101.0, 111.0, 100.0, 105.0),
                          (105.0, 106.0, 104.0, 105.5),
                          (105.5, 106.5, 104.5, 106.0),
                          (106.0, 107.0, 105.0, 106.5),
                          (106.5, 107.5, 105.5, 107.0),
                          (107.0, 108.0, 106.0, 107.5),
                          (107.5, 108.5, 106.5, 108.0),
                          (108.0, 109.0, 107.0, 108.5),
                          (108.5, 109.5, 107.5, 109.0)]),
        "AMBIG": _bars([(100.0, 115.0, 90.0, 100.0)] + [(100.0, 101.0, 99.0, 100.0)] * 9),
        "NOTRIG": _bars([(100.0, 101.0, 99.0, 100.0),
                          (100.0, 102.0, 98.0, 101.0),
                          (101.0, 103.0, 99.0, 102.0),
                          (102.0, 104.0, 100.0, 103.0),
                          (103.0, 105.0, 101.0, 104.0),
                          (104.0, 106.0, 102.0, 105.0),
                          (105.0, 107.0, 103.0, 106.0),
                          (106.0, 108.0, 104.0, 107.0),
                          (107.0, 109.0, 105.0, 108.0),
                          (108.0, 109.5, 106.0, 108.5)]),
        "FEWBARS": _bars([(100.0, 101.0, 99.0, 100.0),
                           (100.0, 102.0, 98.0, 101.0)]),
        "GAPFLOOR": _bars([(95.5, 96.0, 95.0, 96.0),
                            (96.0, 97.0, 95.5, 96.5),
                            (96.5, 97.5, 96.0, 97.0),
                            (97.0, 98.0, 96.5, 97.5),
                            (97.5, 98.5, 97.0, 98.0),
                            (98.0, 99.0, 97.5, 98.5),
                            (98.5, 99.5, 98.0, 99.0),
                            (99.0, 100.0, 98.5, 99.5),
                            (99.5, 100.5, 99.0, 100.0),
                            (100.0, 101.0, 99.5, 100.5)]),
    }
    signals = [
        _sig(ticker="STOP", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="TARGET", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="AMBIG", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="NOTRIG", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="FEWBARS", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="GAPFLOOR", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="GAPUP", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="GAPDOWN", stop=95.0, target=110.0, atr=2.0),
        _sig(ticker="MISSING", stop=95.0, target=110.0, atr=2.0),
    ]
    mapping["GAPUP"] = _bars([(111.0, 112.0, 110.5, 111.5)] * 10)
    mapping["GAPDOWN"] = _bars([(94.0, 96.0, 93.0, 95.5)] * 10)
    return signals, _provider(mapping)


@pytest.mark.parametrize("time_stop", [1, 3, 5, 10])
def test_replica_matches_real_simulator_on_synthetic_bars(time_stop):
    signals, bars_provider = _equivalence_fixture()
    report = check_equivalence(signals, bars_provider, time_stop=time_stop)
    assert report.ok, (report.missing_keys, report.extra_keys, report.mismatches)
    assert report.max_abs_diff <= 1e-9


def test_check_equivalence_never_raises_and_returns_report_type():
    signals, bars_provider = _equivalence_fixture()
    report = check_equivalence(signals, bars_provider, time_stop=10)
    assert isinstance(report, EquivalenceReport)


# -- drift detection: the gate must fail when the replica is wrong ----------

def _apply_min_stop_floor_free_walk(sig, future, entry_px, time_stop, floor_stop):
    lows = future["Low"].to_numpy(dtype=float)
    highs = future["High"].to_numpy(dtype=float)
    closes = future["Close"].to_numpy(dtype=float)
    risk = entry_px - floor_stop
    exit_px = exit_reason = None
    for bar_idx in range(len(future)):
        low, high, close = lows[bar_idx], highs[bar_idx], closes[bar_idx]
        if low <= floor_stop:
            exit_px, exit_reason = floor_stop, "stop"
            break
        elif high >= sig.target:
            exit_px, exit_reason = sig.target, "target"
            break
        elif bar_idx == time_stop - 1:
            exit_px, exit_reason = close, "time_stop"
            break
    if exit_reason is None:
        exit_px, exit_reason = closes[-1], "time_stop"
    return exit_px, exit_reason, risk


def _variant_target_before_stop(signals, bars_provider, time_stop=10,
                                 be_trigger=None, target_multiple=None):
    """Deliberately wrong: checks the target before the stop on each bar."""
    from scanner.targets import apply_min_stop_floor
    out = []
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
        effective_target = sig.target if target_multiple is None else entry_px + target_multiple * risk
        if entry_px >= effective_target:
            continue
        lows = future["Low"].to_numpy(dtype=float)
        highs = future["High"].to_numpy(dtype=float)
        closes = future["Close"].to_numpy(dtype=float)
        exit_px = exit_reason = None
        for bar_idx in range(len(future)):
            low, high, close = lows[bar_idx], highs[bar_idx], closes[bar_idx]
            if high >= effective_target:  # BUG: target checked before stop
                exit_px, exit_reason = effective_target, "target"
                break
            elif low <= effective_stop:
                exit_px, exit_reason = effective_stop, "stop"
                break
            elif bar_idx == time_stop - 1:
                exit_px, exit_reason = close, "time_stop"
                break
        if exit_reason is None:
            exit_px, exit_reason = closes[-1], "time_stop"
        r = (exit_px - entry_px) / risk
        out.append(VariantTrade(str(sig.date), sig.ticker, sig.strategy, entry_px, exit_px, r, exit_reason))
    return out


def _variant_ignores_floor(signals, bars_provider, time_stop=10,
                            be_trigger=None, target_multiple=None):
    """Deliberately wrong: never applies the minimum stop-distance floor."""
    out = []
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
        effective_stop = sig.stop  # BUG: floor not applied
        risk = entry_px - effective_stop
        if risk <= 0:
            continue
        effective_target = sig.target if target_multiple is None else entry_px + target_multiple * risk
        if entry_px >= effective_target:
            continue
        exit_px, exit_reason, risk = _apply_min_stop_floor_free_walk(
            sig, future, entry_px, time_stop, effective_stop
        )
        r = (exit_px - entry_px) / risk
        out.append(VariantTrade(str(sig.date), sig.ticker, sig.strategy, entry_px, exit_px, r, exit_reason))
    return out


def _variant_drops_one_signal(signals, bars_provider, time_stop=10,
                               be_trigger=None, target_multiple=None):
    """Deliberately wrong: silently drops the first resolved trade."""
    trades = simulate_variant(
        signals, bars_provider, time_stop=time_stop,
        be_trigger=be_trigger, target_multiple=target_multiple,
    )
    return trades[1:] if trades else trades


def test_drift_detection_target_before_stop_fails_gate():
    signals, bars_provider = _equivalence_fixture()
    report = check_equivalence(
        signals, bars_provider, time_stop=10, variant_fn=_variant_target_before_stop
    )
    assert report.ok is False
    assert report.mismatches


def test_drift_detection_ignores_floor_fails_gate():
    signals, bars_provider = _equivalence_fixture()
    report = check_equivalence(
        signals, bars_provider, time_stop=1, variant_fn=_variant_ignores_floor
    )
    assert report.ok is False
    assert report.mismatches or report.missing_keys


def test_drift_detection_drops_signal_fails_gate():
    signals, bars_provider = _equivalence_fixture()
    report = check_equivalence(
        signals, bars_provider, time_stop=10, variant_fn=_variant_drops_one_signal
    )
    assert report.ok is False
    assert report.missing_keys


# -- summarize / sweep_time --------------------------------------------------

def test_summarize_train_holdout_split_and_win_pct():
    trades = [
        VariantTrade("2023-06-01", "AAA", "pullback", 100.0, 105.0, 0.5, "target"),
        VariantTrade("2024-06-01", "BBB", "pullback", 100.0, 95.0, -1.0, "stop"),
    ]
    s = summarize(trades, split="2024-01-01")
    assert s["n"] == 2
    assert s["train"] == pytest.approx(0.5)
    assert s["hold"] == pytest.approx(-1.0)
    assert s["win"] == pytest.approx(50.0)
    assert s["mix"]["target"] == 1
    assert s["mix"]["stop"] == 1


def test_summarize_ignores_unresolved_trades():
    class _Unresolved:
        r_multiple = None

    trades = [
        VariantTrade("2023-06-01", "AAA", "pullback", 100.0, 105.0, 0.5, "target"),
        _Unresolved(),
    ]
    s = summarize(trades, split="2024-01-01")
    assert s["n"] == 1


def test_sweep_time_uses_real_simulator_and_matches_variant_baseline():
    signals, bars_provider = _equivalence_fixture()
    rows = sweep_time(signals, bars_provider, time_stops=(10,), split="2024-01-01")
    assert len(rows) == 1
    row = rows[0]
    assert row["time_stop"] == 10

    variant_trades = simulate_variant(signals, bars_provider, time_stop=10)
    variant_summary = summarize(variant_trades, split="2024-01-01")
    assert row["n"] == variant_summary["n"]
    assert row["mean"] == pytest.approx(variant_summary["mean"], abs=1e-9)


# -- Task 2: breakeven pessimism, target override, cross-table consistency --

def test_breakeven_arming_is_pessimistic_no_exit_on_trigger_bar():
    # Bar 0: high clears the 1.0R trigger (entry 100 + 1*5 = 105) but low
    # sits between the original stop (95) and entry (100) -- must NOT exit
    # at breakeven on this bar. Bar 1: low touches entry exactly -> exits
    # at breakeven with r == 0.0.
    bars = _bars([
        (100.0, 106.0, 97.0, 101.0),   # trigger bar: high>=105, low=97 (>95, <100)
        (101.0, 102.0, 100.0, 101.5),  # later bar: low touches entry exactly
    ])
    sig = _sig(stop=95.0, target=200.0, atr=2.0)  # far target so BE/stop decide the exit
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10, be_trigger=1.0)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "be_stop"
    assert t.r_multiple == pytest.approx(0.0)


def test_be_trigger_none_matches_task1_equivalence_and_never_arms():
    # be_trigger=None must leave the walk identical to the baseline replica
    # -- already proven by the equivalence test, but explicitly assert here
    # that no bar can ever move the stop when be_trigger is None (the
    # armed stop, if it existed, would equal entry_px and never go below).
    bars = _bars([(100.0, 130.0, 99.0, 101.0)] * 3)  # high always clears any BE trigger
    sig = _sig(stop=95.0, target=200.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10, be_trigger=None)
    assert len(trades) == 1
    # Never stopped out at entry (100.0) -- stays on the original floor-
    # adjusted stop since be_trigger=None means arming can never happen.
    assert trades[0].exit_reason != "be_stop"


def test_target_multiple_exits_at_entry_plus_k_risk_with_r_equal_k():
    bars = _bars([(100.0, 108.0, 99.0, 103.0)])  # high 108 clears entry+1.5*5=107.5
    sig = _sig(stop=95.0, target=110.0, atr=2.0)
    trades = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10, target_multiple=1.5)
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "target"
    assert t.r_multiple == pytest.approx(1.5)
    assert t.exit_px == pytest.approx(100.0 + 1.5 * 5.0)


def test_target_multiple_readmits_trade_gap_skipped_by_published_target():
    # Published target is 103 -- entry 105 gap-skips against it (published
    # gap-up guard). risk = entry(105) - effective_stop(95) = 10, so a
    # k=1.0 override synthesizes a target of 115, which entry (105) sits
    # below -- the trade IS simulated even though the published target had
    # already gap-skipped it.
    bars = _bars([(105.0, 116.0, 104.0, 106.0)])
    sig = _sig(stop=95.0, target=103.0, atr=2.0)

    baseline = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10, target_multiple=None)
    assert baseline == []  # gap-skipped against the published target

    override = simulate_variant([sig], _provider({"AAA": bars}), time_stop=10, target_multiple=1.0)
    assert len(override) == 1


def test_target_multiple_none_reproduces_baseline_n_and_mean():
    signals, bars_provider = _equivalence_fixture()
    baseline_via_sweep = simulate_variant(signals, bars_provider, time_stop=10, target_multiple=None)
    baseline_direct = simulate_variant(signals, bars_provider, time_stop=10)
    assert len(baseline_via_sweep) == len(baseline_direct)
    s1 = summarize(baseline_via_sweep, split="2024-01-01")
    s2 = summarize(baseline_direct, split="2024-01-01")
    assert s1["n"] == s2["n"]
    assert s1["mean"] == pytest.approx(s2["mean"], abs=1e-9)


def test_breakeven_and_target_baseline_rows_match_time_table_row():
    signals, bars_provider = _equivalence_fixture()
    split = "2024-01-01"

    time_rows = sweep_time(signals, bars_provider, time_stops=(ANCHOR_TIME_STOP,), split=split)
    be_rows = sweep_breakeven(signals, bars_provider, split=split, time_stops=(ANCHOR_TIME_STOP,), triggers=())
    target_rows = sweep_target(signals, bars_provider, split=split, time_stops=(ANCHOR_TIME_STOP,), multiples=())

    time_row = time_rows[0]
    be_baseline = next(r for r in be_rows if r["label"] == f"baseline ts={ANCHOR_TIME_STOP}")
    target_baseline = next(r for r in target_rows if r["label"] == f"current (resistance) ts={ANCHOR_TIME_STOP}")

    assert be_baseline["n"] == time_row["n"]
    assert target_baseline["n"] == time_row["n"]
    assert be_baseline["mean"] == pytest.approx(time_row["mean"], abs=1e-9)
    assert target_baseline["mean"] == pytest.approx(time_row["mean"], abs=1e-9)


def test_sweep_breakeven_full_trigger_grid_at_anchor_reduced_elsewhere():
    signals, bars_provider = _equivalence_fixture()
    rows = sweep_breakeven(
        signals, bars_provider, split="2024-01-01",
        triggers=(0.5, 0.75, 1.0, 1.5, 2.0), time_stops=(10, 20),
    )
    labels = [r["label"] for r in rows]
    for k in (0.5, 0.75, 1.0, 1.5, 2.0):
        assert f"BE@{k}R ts=10" in labels
    assert "BE@1.0R ts=20" in labels
    assert "BE@1.5R ts=20" in labels
    assert "BE@0.5R ts=20" not in labels


def test_render_target_table_includes_footnote():
    signals, bars_provider = _equivalence_fixture()
    rows = sweep_target(signals, bars_provider, split="2024-01-01", time_stops=(10,), multiples=(2.0,))
    text = render_target_table(rows)
    assert "not comparable row to row" in text


def test_render_breakeven_table_folds_be_stop_into_stop_bucket():
    rows = [{
        "label": "BE@1.0R ts=10", "n": 2, "mean": 0.0, "train": 0.0, "hold": 0.0,
        "win": 50.0, "mix": {"be_stop": 1, "target": 1},
    }]
    text = render_breakeven_table(rows)
    # 1 be_stop + 0 stop out of 2 total -> 50.0 in the stop% column.
    assert "50.0" in text


def test_exactly_one_simulate_variant_definition_in_module():
    import inspect

    import scanner.exit_sweep as m
    src = inspect.getsource(m)
    assert src.count("def simulate_variant") == 1
