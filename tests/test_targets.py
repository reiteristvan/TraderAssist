"""E4.1 unit tests — targets.py: stop rules, 5-method target engine, attach_risk."""
import math
import numpy as np
import pandas as pd
import pytest

from scanner.targets import (
    compute_targets,
    count_resistance_obstacles,
    attach_risk,
    find_swing_points,
    apply_min_stop_floor,
    MIN_STOP_ATR_MULT,
    TargetAnalysis,
)
from scanner.strategies.pullback import PullbackResult
from scanner.strategies.breakout import BreakoutResult


def _make_df(n=280, start=20.0, r=0.003, seed=42):
    """Simple trending frame for target tests."""
    rng = np.random.default_rng(seed)
    closes = start * (1 + r) ** np.arange(n) * (1 + rng.normal(0, 0.005, n))
    highs = closes * (1 + np.abs(rng.normal(0.003, 0.002, n)))
    lows = closes * (1 - np.abs(rng.normal(0.003, 0.002, n)))
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    vols = np.full(n, 1_500_000.0)
    idx = pd.bdate_range(end="2026-06-15", periods=n)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
        index=idx,
    )


def test_compute_targets_pullback_returns_analysis():
    df = _make_df()
    price = float(df["Close"].iloc[-1])
    stop = price * 0.95
    atr = price * 0.015
    analysis = compute_targets(df, price, stop, "PULLBACK", atr)
    assert isinstance(analysis, TargetAnalysis)
    assert len(analysis.methods) >= 1
    assert analysis.suggested_target > price
    assert analysis.risk_reward > 0


def test_compute_targets_breakout_returns_analysis():
    df = _make_df()
    price = float(df["Close"].iloc[-1])
    stop = price * 0.97
    atr = price * 0.01
    analysis = compute_targets(df, price, stop, "BREAKOUT", atr)
    assert isinstance(analysis, TargetAnalysis)
    # Breakout uses 3x ATR for Method 1
    atr_method = next(m for m in analysis.methods if "3" in m.name)
    assert abs(atr_method.price - (price + 3 * atr)) < 0.02


def test_five_target_methods_all_possible():
    """With enough data all 5 method types can fire."""
    df = _make_df(n=300, r=0.004)
    price = float(df["Close"].iloc[-1])
    stop = price * 0.94
    atr = price * 0.012
    analysis = compute_targets(df, price, stop, "PULLBACK", atr)
    names = [m.name for m in analysis.methods]
    # At least ATR, Prev High, Measured Move, and one Fib should appear
    assert any("ATR" in n for n in names)
    assert any("Prev" in n or "High" in n for n in names)
    assert any("Measured" in n for n in names)


def test_confluence_zone_is_ordered():
    df = _make_df()
    price = float(df["Close"].iloc[-1])
    stop = price * 0.95
    atr = price * 0.015
    analysis = compute_targets(df, price, stop, "PULLBACK", atr)
    lo, hi = analysis.confluence_zone
    assert lo <= hi


def test_stop_formula_pullback():
    """Pullback stop = EMA20 - ATR14."""
    df = _make_df()
    from ta.volatility import AverageTrueRange
    atr_val = float(AverageTrueRange(df["High"], df["Low"], df["Close"], 14)
                    .average_true_range().iloc[-1])
    ema20 = float(df["Close"].ewm(span=20).mean().iloc[-1])
    expected_stop = round(ema20 - atr_val, 2)

    # Create a minimal PullbackResult with just the fields attach_risk uses
    # We need a real PullbackResult; use a dummy evaluate()
    from datetime import date
    from scanner.core import EvalContext, QualityInfo
    qi = QualityInfo(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                     sector=None, float_shares=None)
    ctx = EvalContext(as_of=date(2026, 6, 15), market_data={}, weekly=None,
                      quality=qi, days_to_earnings=30)
    from scanner.strategies.pullback import evaluate as pb_eval
    res = pb_eval("TEST", df, ctx)
    enriched = attach_risk(res, df)
    assert enriched.suggested_stop == expected_stop


def test_stop_formula_breakout():
    """Breakout stop = high_20_prev - 0.5 * ATR14."""
    df = _make_df()
    from ta.volatility import AverageTrueRange
    atr_val = float(AverageTrueRange(df["High"], df["Low"], df["Close"], 14)
                    .average_true_range().iloc[-1])
    high_20_prev = float(df["High"].iloc[-21:-1].max())
    expected_stop = round(high_20_prev - 0.5 * atr_val, 2)

    from datetime import date
    from scanner.core import EvalContext, QualityInfo
    qi = QualityInfo(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                     sector=None, float_shares=None)
    ctx = EvalContext(as_of=date(2026, 6, 15), market_data={}, weekly=None,
                      quality=qi, days_to_earnings=30)
    from scanner.strategies.breakout import evaluate as br_eval
    res = br_eval("TEST", df, ctx)
    enriched = attach_risk(res, df)
    assert enriched.suggested_stop == expected_stop


def test_attach_risk_stop_above_entry_safe():
    """When stop >= entry, attach_risk returns stop/atr but target/rr are None."""
    df = _make_df(r=-0.005)  # declining — high_20_prev may be above current close
    from datetime import date
    from scanner.core import EvalContext, QualityInfo
    qi = QualityInfo(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                     sector=None, float_shares=None)
    ctx = EvalContext(as_of=date(2026, 6, 15), market_data={}, weekly=None,
                      quality=qi, days_to_earnings=30)
    from scanner.strategies.breakout import evaluate as br_eval
    res = br_eval("TEST", df, ctx)
    enriched = attach_risk(res, df)
    # If stop >= entry the result should not crash and target/rr may be None
    assert enriched.suggested_stop is not None
    assert enriched.atr is not None


def test_count_resistance_obstacles():
    df = _make_df()
    price = float(df["Close"].iloc[-1]) * 0.90
    target = float(df["Close"].iloc[-1]) * 1.10
    count, levels = count_resistance_obstacles(df, price, target)
    assert isinstance(count, int)
    assert isinstance(levels, list)
    assert count >= 0


def test_find_swing_points_returns_valid():
    df = _make_df(n=100)
    sl, sh, sl_idx, sh_idx = find_swing_points(df)
    # May be None for short/flat series; for trending series they should be found
    if sl is not None and sh is not None:
        assert sl < sh


# --- quick-260819-g5h: minimum stop-distance floor (0.5x ATR) regression block ---


def test_apply_min_stop_floor_epac_case():
    """Real-world regression: EPAC 2024-01-16, entry 28.91 / stop 28.89 / ATR 0.71.

    Raw risk was 2.4 cents (0.03x ATR), producing 72.7R. The floor must widen
    this to at least 0.5x ATR while keeping the stop strictly below entry.
    """
    result = apply_min_stop_floor(28.89, 28.91, 0.71)
    assert 28.91 - result >= 0.5 * 0.71
    assert result < 28.91


def test_apply_min_stop_floor_gnw_case():
    """Real-world regression: GNW 2025-07-16, entry 7.30 / stop 7.29 / ATR 0.20.

    Raw risk was 1.0 cent (0.05x ATR), producing 50.0R.
    """
    result = apply_min_stop_floor(7.29, 7.30, 0.20)
    assert 7.30 - result >= 0.5 * 0.20
    assert result < 7.30


def test_apply_min_stop_floor_never_tightens():
    """A stop already beyond 0.5x ATR is returned unchanged (D-02: widen, never tighten)."""
    result = apply_min_stop_floor(44.53, 46.19, 0.3764)
    assert result == 44.53


@pytest.mark.parametrize("bad_atr", [0.0, -1.0, float("nan"), None])
def test_apply_min_stop_floor_degenerate_atr_returns_input_unchanged(bad_atr):
    """Degenerate ATR (0, negative, NaN, None) must return the input stop unchanged
    and must never raise.

    This is total-function safety: an exception here would be silently
    swallowed by the broad `except (ValueError, AttributeError, KeyError,
    IndexError)` at scanner/backtest.py:376 and the bare `except Exception`
    at scanner/core.py:669, dropping the signal with no log. The helper must
    be total rather than defensive-by-raising.
    """
    result = apply_min_stop_floor(5.0, 6.0, bad_atr)
    assert result == 5.0


def test_apply_min_stop_floor_quantization_invariant():
    """Floor-to-cent (not round-to-cent) guarantees price - result >= mult * atr
    strictly whenever the floor binds, across a spread of ATR values."""
    price = 46.19
    for atr in [0.05, 0.1237, 0.3764, 0.71, 1.005, 2.5]:
        raw_stop = price - 0.01  # deliberately inside the floor for small atr
        result = apply_min_stop_floor(raw_stop, price, atr)
        if result != raw_stop:
            # the floor bound; the invariant must hold strictly
            assert price - result >= MIN_STOP_ATR_MULT * atr


def test_attach_risk_breakout_floor_applied():
    """Standard _make_df() breakout fixture measures 0.243x ATR raw stop distance,
    so the floor genuinely binds here. This test fails against pre-floor code."""
    df = _make_df()
    from datetime import date
    from scanner.core import EvalContext, QualityInfo
    qi = QualityInfo(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                     sector=None, float_shares=None)
    ctx = EvalContext(as_of=date(2026, 6, 15), market_data={}, weekly=None,
                      quality=qi, days_to_earnings=30)
    from scanner.strategies.breakout import evaluate as br_eval
    res = br_eval("TEST", df, ctx)
    enriched = attach_risk(res, df)
    assert enriched.close - enriched.suggested_stop >= 0.5 * enriched.atr


def test_attach_risk_stop_above_entry_guard_order_preserved():
    """The floor must NOT rescue a raw stop-at-or-above-entry signal into a
    tradeable one. Uses the declining _make_df(r=-0.005) fixture where the
    raw breakout stop sits above entry (see test_attach_risk_stop_above_entry_safe)."""
    df = _make_df(r=-0.005)
    from datetime import date
    from scanner.core import EvalContext, QualityInfo
    qi = QualityInfo(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                     sector=None, float_shares=None)
    ctx = EvalContext(as_of=date(2026, 6, 15), market_data={}, weekly=None,
                      quality=qi, days_to_earnings=30)
    from scanner.strategies.breakout import evaluate as br_eval
    res = br_eval("TEST", df, ctx)
    enriched = attach_risk(res, df)
    assert enriched.suggested_target is None
    assert enriched.risk_reward is None
