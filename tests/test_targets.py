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
