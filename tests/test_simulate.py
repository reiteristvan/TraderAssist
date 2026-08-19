"""Tests for scanner.simulate — E7.1.

Mandatory fixture set per CLAUDE.md E7.1:
  1. Clean target hit
  2. Clean stop hit  (r = −1.0 exactly)
  3. Time-stop exit
  4. Gap-skip up    (open ≥ target)
  5. Gap-skip down  (open ≤ stop)
  6. Ambiguous bar  (Low ≤ stop AND High ≥ target)

Each fixture has hand-computed exit_px and r_multiple asserted.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from scanner.simulate import Signal, Trade, simulate_trades
from scanner.targets import MIN_STOP_ATR_MULT, apply_min_stop_floor


# ── shared helpers ────────────────────────────────────────────────────────────

def _signal(
    ticker="TEST",
    sig_date=date(2026, 1, 2),  # Friday
    stop=90.0,
    target=110.0,
    entry_open=100.0,  # expected entry price (set bar opens to match)
) -> Signal:
    return Signal(
        date=sig_date,
        ticker=ticker,
        strategy="pullback",
        score=60.0,
        confidence="MEDIUM",
        stop=stop,
        target=target,
        atr=1.0,
        qualified=True,
        close=entry_open,
    )


def _bars(
    index_dates: list[date],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in index_dates])
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes,
         "Volume": [1_000_000] * len(index_dates)},
        index=idx,
    )


def _provider(bars_map: dict[str, pd.DataFrame]):
    return lambda ticker: bars_map.get(ticker)


# ── 1. Clean target hit ───────────────────────────────────────────────────────

def test_clean_target_hit():
    """Signal day = 2026-01-02; entry bar = 01-05 (Mon after Fri signal)."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # Entry bar (01-05): open=100, no exit; day 2 (01-06): high >= 110
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 111.0],
        lows   =[99.5,   99.0,  99.0],
        closes =[100.0, 100.5, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "target"
    assert trade.exit_px == pytest.approx(110.0)
    assert trade.entry_px == pytest.approx(100.0)
    assert trade.entry_date == date(2026, 1, 5)
    assert trade.entry_date > trade.signal_date  # AC: entry_date > signal_date
    # r = (110 - 100) / (100 - 90) = 10/10 = 1.0
    assert trade.r_multiple == pytest.approx(1.0)
    assert trade.holding_days >= 0


# ── 2. Clean stop hit — r exactly −1.0 ───────────────────────────────────────

def test_clean_stop_hit():
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # Entry bar (01-05): open=100; day 2 (01-06): low=89 → stop hit
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 100.0],
        lows   =[99.5,   99.0,  89.0],
        closes =[100.0, 100.5,  89.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(90.0)  # exit AT stop price
    # r = (90 - 100) / (100 - 90) = -10/10 = -1.0 exactly
    assert trade.r_multiple == pytest.approx(-1.0)
    assert not trade.flags.get("ambiguous_bar")


# ── 3. Time-stop exit ─────────────────────────────────────────────────────────

def test_time_stop_exit():
    """10 bars, none hit stop/target → exit at session-10 close."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    n = 11  # signal bar + 10 session bars
    idx_dates = [date(2026, 1, 2)] + [
        (pd.Timestamp("2026-01-05") + pd.Timedelta(days=i)).date()
        for i in range(10)
    ]
    bars = _bars(
        idx_dates,
        opens  =[100.0] * n,
        highs  =[100.5] * n,
        lows   =[99.5]  * n,
        closes =[100.0] * n,
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}), time_stop=10)

    assert trade.exit_reason == "time_stop"
    # Exit at close of session 10 (bar_idx=9 in future bars = idx_dates[10])
    expected_exit_date = idx_dates[10]
    assert trade.exit_date == expected_exit_date
    assert trade.exit_px == pytest.approx(100.0)
    # r = (100 - 100) / (100 - 90) = 0.0
    assert trade.r_multiple == pytest.approx(0.0)


# ── 4. Gap-skip up ────────────────────────────────────────────────────────────

def test_gap_skip_up():
    """Entry bar opens >= target → gap_skip_up, r=None."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # Entry bar opens at 111 ≥ target (110)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens  =[100.0, 111.0],
        highs  =[100.5, 112.0],
        lows   =[99.5,  110.0],
        closes =[100.0, 111.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "gap_skip_up"
    assert trade.r_multiple is None
    assert trade.flags.get("skipped_gap") is True
    assert trade.entry_date > trade.signal_date


# ── 5. Gap-skip down ─────────────────────────────────────────────────────────

def test_gap_skip_down():
    """Entry bar opens <= stop → gap_skip_down, r=None."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # Entry bar opens at 89.5 ≤ stop (90)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens  =[100.0, 89.5],
        highs  =[100.5, 90.0],
        lows   =[99.5,  88.0],
        closes =[100.0, 89.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "gap_skip_down"
    assert trade.r_multiple is None
    assert trade.flags.get("skipped_gap") is True


# ── 6. Ambiguous bar ─────────────────────────────────────────────────────────

def test_ambiguous_bar():
    """Same bar: Low ≤ stop AND High ≥ target → pessimistic stop-out."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # Entry bar (01-05): clean. Day 2 (01-06): Low=88 and High=112
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 101.0],
        highs  =[100.5, 101.0, 112.0],
        lows   =[99.5,   99.0,  88.0],
        closes =[100.0, 100.5, 100.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(90.0)  # pessimistic → stop price
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.flags.get("ambiguous_bar") is True


# ── entry_date > signal_date for all exit types ───────────────────────────────

@pytest.mark.parametrize("scenario", ["target", "stop", "gap_up", "gap_down", "time_stop"])
def test_entry_date_after_signal(scenario):
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    if scenario == "target":
        bars = _bars(
            [date(2026, 1, 2), date(2026, 1, 5)],
            [100.0, 100.0], [101.0, 111.0], [99.0, 99.0], [100.0, 110.0],
        )
    elif scenario == "stop":
        bars = _bars(
            [date(2026, 1, 2), date(2026, 1, 5)],
            [100.0, 100.0], [101.0, 100.0], [99.0, 88.0], [100.0, 89.0],
        )
    elif scenario == "gap_up":
        bars = _bars(
            [date(2026, 1, 2), date(2026, 1, 5)],
            [100.0, 115.0], [101.0, 116.0], [99.0, 114.0], [100.0, 115.0],
        )
    elif scenario == "gap_down":
        bars = _bars(
            [date(2026, 1, 2), date(2026, 1, 5)],
            [100.0, 85.0], [101.0, 86.0], [99.0, 84.0], [100.0, 85.0],
        )
    else:  # time_stop
        n = 12
        idx_dates = [date(2026, 1, 2)] + [
            (pd.Timestamp("2026-01-05") + pd.Timedelta(days=i)).date()
            for i in range(11)
        ]
        bars = _bars(idx_dates, [100.0]*n, [100.5]*n, [99.5]*n, [100.0]*n)

    [trade] = simulate_trades([sig], _provider({"TEST": bars}), time_stop=10)
    if trade.entry_date is not None:
        assert trade.entry_date > trade.signal_date


# ── Incomplete (no next bar) ──────────────────────────────────────────────────

def test_incomplete_signal():
    """Signal on last available bar — no next bar to enter."""
    sig = _signal(sig_date=date(2026, 1, 5))
    # Only one bar and it IS the signal date
    bars = _bars(
        [date(2026, 1, 5)],
        [100.0], [101.0], [99.0], [100.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "incomplete"
    assert trade.r_multiple is None
    assert trade.flags.get("incomplete") is True


# ── Multiple signals, mixed outcomes ─────────────────────────────────────────

def test_multiple_signals():
    sig1 = _signal(ticker="A", sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    sig2 = _signal(ticker="B", sig_date=date(2026, 1, 2), stop=90.0, target=110.0)

    bars_a = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        [100.0, 100.0], [101.0, 111.0], [99.0, 99.0], [100.0, 110.0],
    )
    bars_b = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        [100.0, 100.0], [101.0, 101.0], [99.0, 88.0], [100.0, 89.0],
    )

    trades = simulate_trades([sig1, sig2], _provider({"A": bars_a, "B": bars_b}))
    assert len(trades) == 2
    reasons = {t.ticker: t.exit_reason for t in trades}
    assert reasons["A"] == "target"
    assert reasons["B"] == "stop"


# ── E14.1 — MAE / MFE / post-stop excursion ──────────────────────────────────

def test_mae_mfe_clean_target_hit():
    """MAE and MFE are correct for a clean target-hit trade."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # entry bar: low=99, high=101; exit bar: low=99, high=111 → target
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 111.0],
        lows   =[99.5,   99.0,  99.0],
        closes =[100.0, 100.5, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    # mae_r = (min_low 99 − entry 100) / risk 10 = −0.1
    # mfe_r = (max_high 111 − entry 100) / risk 10 = 1.1
    assert trade.mae_r == pytest.approx(-0.1)
    assert trade.mfe_r == pytest.approx(1.1)
    assert trade.post_stop_reached_target is None
    assert trade.post_stop_mfe_r is None


def test_mae_mfe_clean_stop_hit_no_post_bars():
    """Stop-out with no subsequent bars → post_stop False/0.0."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # entry bar: low=99; exit bar: low=89 → stop (no more bars)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 100.0],
        lows   =[99.5,   99.0,  89.0],
        closes =[100.0, 100.5,  89.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "stop"
    assert trade.mae_r == pytest.approx(-1.1)   # (89 − 100) / 10
    assert trade.mfe_r == pytest.approx(0.1)    # (101 − 100) / 10
    assert trade.post_stop_reached_target is False
    assert trade.post_stop_mfe_r == pytest.approx(0.0)


def test_post_stop_reaches_target():
    """Stop fires at bar 2; bar 3 rallies to target → post_stop_reached_target=True."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
        opens  =[100.0, 100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 100.0, 115.0],  # bar 3: high=115 ≥ target=110
        lows   =[99.5,   95.0,  89.0,  95.0],  # bar 2: low=89 ≤ stop=90
        closes =[100.0, 100.0,  89.5, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}), time_stop=10)

    assert trade.exit_reason == "stop"
    assert trade.r_multiple == pytest.approx(-1.0)   # exit at stop=90, risk=10
    assert trade.post_stop_reached_target is True
    # post_stop_mfe_r = (115 − 100) / 10 = 1.5
    assert trade.post_stop_mfe_r == pytest.approx(1.5)
    # MAE covers entry bar + stop bar; stop bar low=89
    assert trade.mae_r == pytest.approx(-1.1)   # (89 − 100) / 10
    assert trade.mfe_r == pytest.approx(0.1)    # (101 − 100) / 10


def test_post_stop_keeps_falling():
    """Stop fires at bar 2; subsequent bars stay below target → False."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
        opens  =[100.0, 100.0, 100.0,  85.0],
        highs  =[100.5, 101.0, 100.0,  88.0],  # bar 3: high=88 < target=110
        lows   =[99.5,   95.0,  89.0,  83.0],
        closes =[100.0, 100.0,  89.5,  84.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}), time_stop=10)

    assert trade.exit_reason == "stop"
    assert trade.post_stop_reached_target is False
    # post_stop_mfe_r = (88 − 100) / 10 = −1.2
    assert trade.post_stop_mfe_r == pytest.approx(-1.2)


def test_gap_skip_has_no_mae_mfe():
    """Gap-skip trades have all excursion fields as None."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens  =[100.0, 111.0],
        highs  =[100.5, 112.0],
        lows   =[99.5,  110.0],
        closes =[100.0, 111.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "gap_skip_up"
    assert trade.mae_r is None
    assert trade.mfe_r is None
    assert trade.post_stop_reached_target is None
    assert trade.post_stop_mfe_r is None


def test_e7_golden_fixtures_unchanged():
    """E7.1 golden exit outcomes are not altered by E14.1 instrumentation."""
    # Reuses clean_target_hit scenario — only checks original fields
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 111.0],
        lows   =[99.5,   99.0,  99.0],
        closes =[100.0, 100.5, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "target"
    assert trade.exit_px    == pytest.approx(110.0)
    assert trade.entry_px   == pytest.approx(100.0)
    assert trade.r_multiple == pytest.approx(1.0)


# ── E13.1 — target_r and target_atr fields ───────────────────────────────────

def test_target_r_and_atr_on_normal_trade():
    """target_r = target_dist/risk; target_atr = target_dist/atr (atr=1.0)."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    # entry_px=100, risk=10, target_dist=10 → target_r=1.0, target_atr=10.0
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 111.0],
        lows   =[99.5,   99.0,  99.0],
        closes =[100.0, 100.5, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.target_r   == pytest.approx(1.0)
    assert trade.target_atr == pytest.approx(10.0)


def test_target_r_same_regardless_of_exit():
    """target_r reflects setup geometry, not outcome — same for stop hit."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens  =[100.0, 100.0, 100.0],
        highs  =[100.5, 101.0, 100.0],
        lows   =[99.5,   99.0,  89.0],
        closes =[100.0, 100.5,  89.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "stop"
    assert trade.target_r   == pytest.approx(1.0)
    assert trade.target_atr == pytest.approx(10.0)


def test_target_r_none_for_gap_skip():
    """Gap-skip trades have target_r=None and target_atr=None."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens  =[100.0, 111.0],
        highs  =[100.5, 112.0],
        lows   =[99.5,  110.0],
        closes =[100.0, 111.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "gap_skip_up"
    assert trade.target_r   is None
    assert trade.target_atr is None


def test_target_r_none_for_incomplete():
    """Incomplete trades have target_r=None."""
    sig = _signal(sig_date=date(2026, 1, 5))
    bars = _bars([date(2026, 1, 5)], [100.0], [101.0], [99.0], [100.0])
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))

    assert trade.exit_reason == "incomplete"
    assert trade.target_r   is None
    assert trade.target_atr is None


# ── Near-miss signals preserve failed_gates in Trade ─────────────────────────

def test_near_miss_failed_gates_preserved():
    sig = Signal(
        date=date(2026, 1, 2),
        ticker="TEST",
        strategy="pullback",
        score=55.0,
        confidence=None,
        stop=90.0,
        target=110.0,
        atr=1.0,
        qualified=False,
        failed_gates=["RSI in range", "Volume contraction"],
        close=100.0,
    )
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        [100.0, 100.0], [101.0, 111.0], [99.0, 99.0], [100.0, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.qualified is False
    assert trade.failed_gates == ["RSI in range", "Volume contraction"]


# ── quick-260819-ko0 — entry-side stop floor regression block ────────────────
#
# All fixtures below use a signal geometry chosen to sit deep inside the
# sub-0.5x-ATR band: published stop 99.90, entry open 100.0, ATR 2.0. That
# gives a published risk of 0.10 against a 2.0 ATR (0.05x ATR) — squarely
# inside the collapsed-denominator band this task fixes. The effective stop
# apply_min_stop_floor(99.90, 100.0, 2.0) returns is 98.99 (floors one cent
# beyond the pure 0.5x ATR level of 99.00 — see targets.py), giving a
# widened risk of 1.01. Expected values are always derived from the helper
# or asserted as inequalities — never hardcoded as entry_px - 0.5 * atr.

def _collapsed_signal(
    ticker="TEST",
    sig_date=date(2026, 1, 2),
    stop=99.90,
    target=110.0,
    atr=2.0,
    entry_open=100.0,
) -> Signal:
    return Signal(
        date=sig_date,
        ticker=ticker,
        strategy="pullback",
        score=60.0,
        confidence="MEDIUM",
        stop=stop,
        target=target,
        atr=atr,
        qualified=True,
        close=entry_open,
    )


def test_ko0_stop_hit_detection_moves_with_widened_stop():
    """D-02 core: a low between the effective and published stop must NOT
    stop the trade out. On the pre-change code (stop_hit = low <= sig.stop)
    this same fixture (low=99.5 <= published 99.90) stops out; a passing
    assertion here is the proof the widened stop is a REAL stop, not just a
    wider denominator."""
    sig = _collapsed_signal()
    eff = apply_min_stop_floor(sig.stop, 100.0, sig.atr)
    assert 99.5 > eff  # low sits strictly above the effective stop
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 100.0],
        highs=[100.5, 100.5],
        lows=[99.6, 99.5],
        closes=[100.0, 100.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason != "stop"


def test_ko0_exit_price_and_denominator_agree():
    """D-02: exiting at the tighter published stop while dividing by the
    wider effective risk would fabricate an improvement that never
    happened. r_multiple staying exactly -1.0 while exit_px equals the
    effective (not published) stop is the invariant that makes that fake
    impossible."""
    sig = _collapsed_signal()
    eff = apply_min_stop_floor(sig.stop, 100.0, sig.atr)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 100.0],
        highs=[100.5, 100.5],
        lows=[99.6, 98.0],
        closes=[100.0, 98.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(eff)
    assert trade.exit_px != pytest.approx(sig.stop)
    assert trade.r_multiple == pytest.approx(-1.0)


def test_ko0_r_compression_sanity_demonstration():
    """Unit-level stand-in for the CONTEXT.md sanity target (max R falling
    from 56.0 to roughly 9, |R| > 10 going to about 0), measured on
    synthetic bars so no backtest run is required. Sanity check, not a
    tuning target: on the pre-change code this fixture scores roughly
    100.0 R (risk 0.10); after the fix it scores roughly 9.9 (risk 1.01)."""
    sig = _collapsed_signal()
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens=[100.0, 100.0, 100.0],
        highs=[100.5, 100.5, 111.0],
        lows=[99.6, 99.6, 99.6],
        closes=[100.0, 100.0, 110.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "target"
    assert trade.r_multiple == pytest.approx(9.9, abs=0.05)
    assert trade.r_multiple < 11


def test_ko0_widened_stop_does_not_rescue_gap_skip_down():
    """D-03: entry open 99.5 sits at/below the published stop 99.90 but
    above the effective stop 98.99. Widening before the guard (instead of
    after) would convert this into a tradeable trade — the specific
    scope-expansion bug the guard placement exists to prevent."""
    sig = _collapsed_signal()
    eff = apply_min_stop_floor(sig.stop, 99.5, sig.atr)
    assert eff < 99.5 <= sig.stop  # confirms the fixture sits in the gap band
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 99.5],
        highs=[100.5, 100.0],
        lows=[99.6, 99.0],
        closes=[100.0, 99.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "gap_skip_down"
    assert trade.r_multiple is None
    assert trade.flags.get("skipped_gap") is True


def test_ko0_gap_skip_up_untouched():
    """No stop value participates in gap_skip_up (D-03) — unaffected by
    this change."""
    sig = _collapsed_signal()
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 111.0],
        highs=[100.5, 112.0],
        lows=[99.6, 110.0],
        closes=[100.0, 111.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "gap_skip_up"
    assert trade.r_multiple is None


def test_ko0_mae_mfe_and_post_stop_shadow_use_widened_risk():
    """mae_r, mfe_r, and post_stop_mfe_r all inherit through `risk` rather
    than through a separate edit — this test is what would catch the
    denominator silently reverting to the published stop."""
    sig = _collapsed_signal()
    eff = apply_min_stop_floor(sig.stop, 100.0, sig.atr)
    risk = 100.0 - eff
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens=[100.0, 100.0, 100.0],
        highs=[100.5, 100.5, 103.0],
        lows=[99.6, 98.0, 99.0],
        closes=[100.0, 98.5, 102.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "stop"
    assert trade.mae_r == pytest.approx((98.0 - 100.0) / risk)
    assert trade.mfe_r == pytest.approx((100.5 - 100.0) / risk)
    assert trade.post_stop_reached_target is False
    assert trade.post_stop_mfe_r == pytest.approx((103.0 - 100.0) / risk)


def test_ko0_never_tightens_existing_geometry_byte_identical():
    """Planning measurement: the standard fixture (published stop 90.0,
    entry open 100.0, ATR 1.0) has a floor candidate of 99.50, so `min`
    keeps 90.0 unchanged — the floor cannot bind on any pre-existing
    fixture. exit_px, r_multiple, mae_r, and mfe_r are byte-identical to
    the pre-change suite's own assertions."""
    sig = _signal(sig_date=date(2026, 1, 2), stop=90.0, target=110.0)
    eff = apply_min_stop_floor(sig.stop, 100.0, sig.atr)
    assert eff == pytest.approx(90.0)  # floor does not bind
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        opens=[100.0, 100.0, 100.0],
        highs=[100.5, 101.0, 100.0],
        lows=[99.5, 99.0, 89.0],
        closes=[100.0, 100.5, 89.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(90.0)
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.mae_r == pytest.approx(-1.1)
    assert trade.mfe_r == pytest.approx(0.1)


@pytest.mark.parametrize("bad_atr", [0.0, -1.0, float("nan"), None])
def test_ko0_degenerate_atr_leaves_stop_unchanged(bad_atr):
    """scanner/backtest.py populates Signal.atr as `result.atr or 0.0`, so
    0.0 is a live production value, not a hypothetical. Degenerate ATR must
    leave the stop unchanged, raise nothing, and never yield a stop at or
    above entry."""
    sig = _collapsed_signal(atr=bad_atr)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 100.0],
        highs=[100.5, 100.5],
        lows=[99.6, 99.0],
        closes=[100.0, 99.5],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(99.90)  # unchanged published stop
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.exit_px < 100.0  # stop stayed strictly below entry


@pytest.mark.parametrize("atr", [0.1, 1.0, 2.0, 5.0])
def test_ko0_reuse_is_behavioral_not_incidental(atr):
    """Pins that simulate uses the SAME house rule as the close side rather
    than a divergent local constant: the risk implied by the simulated
    trade matches apply_min_stop_floor's output directly, and satisfies the
    MIN_STOP_ATR_MULT invariant whenever the floor binds."""
    sig = _collapsed_signal(atr=atr)
    expected_stop = apply_min_stop_floor(sig.stop, 100.0, atr)
    bars = _bars(
        [date(2026, 1, 2), date(2026, 1, 5)],
        opens=[100.0, 100.0],
        highs=[100.5, 100.5],
        lows=[99.6, 90.0],  # far below any possible effective stop
        closes=[100.0, 92.0],
    )
    [trade] = simulate_trades([sig], _provider({"TEST": bars}))
    assert trade.exit_reason == "stop"
    assert trade.exit_px == pytest.approx(expected_stop)
    implied_risk = 100.0 - trade.exit_px
    if expected_stop < sig.stop:  # floor bound
        assert implied_risk >= MIN_STOP_ATR_MULT * atr - 1e-6
