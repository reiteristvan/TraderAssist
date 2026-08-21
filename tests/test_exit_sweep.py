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
    EquivalenceReport,
    VariantTrade,
    check_equivalence,
    simulate_variant,
    summarize,
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
