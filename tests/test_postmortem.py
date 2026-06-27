"""Tests for scanner.postmortem (E14.4)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from scanner.postmortem import (
    _spy_regime_at,
    _dist_above_20ma,
    loser_postmortem,
    dimension_analysis,
    render_postmortem,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(d: str) -> pd.Timestamp:
    return pd.Timestamp(d)


def _make_trade(r_multiple: float, exit_reason: str = "stop", signal_date: str = "2024-06-01",
                ticker: str = "AAPL", spy_regime: str = "BULLISH",
                dist_above_20ma: float = 3.0, rs_strength: float = 1.05,
                score: float = 80.0, confidence: str | None = "HIGH") -> dict:
    return {
        "ticker":          ticker,
        "signal_date":     date.fromisoformat(signal_date),
        "exit_reason":     exit_reason,
        "r_multiple":      r_multiple,
        "score":           score,
        "confidence":      confidence,
        "close":           100.0,
        "spy_regime":      spy_regime,
        "dist_above_20ma": dist_above_20ma,
        "rs_strength":     rs_strength,
    }


# ── Unit: SPY regime helper ───────────────────────────────────────────────────

def test_spy_regime_bullish():
    idx = pd.date_range("2023-01-01", periods=100, freq="B")
    close = pd.Series([100.0] * 100, index=idx)
    # Set last 50 bars above prior SMA50 → BULLISH (price > sma50 and price > ema20)
    # With flat series, SMA50 = EMA20 = price → borderline; use rising close
    close_rising = pd.Series(range(80, 180), index=idx, dtype=float)
    regime = _spy_regime_at(close_rising, idx[-1])
    assert regime == "BULLISH"


def test_spy_regime_bearish():
    idx = pd.date_range("2023-01-01", periods=100, freq="B")
    close_falling = pd.Series(range(180, 80, -1), index=idx, dtype=float)
    regime = _spy_regime_at(close_falling, idx[-1])
    assert regime == "BEARISH"


def test_spy_regime_insufficient_data():
    idx = pd.date_range("2023-01-01", periods=10, freq="B")
    close = pd.Series([100.0] * 10, index=idx)
    assert _spy_regime_at(close, idx[-1]) == "UNKNOWN"


# ── Unit: dist-above-20MA helper ─────────────────────────────────────────────

def test_dist_above_20ma_positive():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    close = pd.Series([100.0] * 30, index=idx)
    sma20 = close.rolling(20).mean()
    dist = _dist_above_20ma(sma20, close, idx[-1])
    # flat: close == sma20 → dist ≈ 0
    assert dist is not None
    assert abs(dist) < 0.01


def test_dist_above_20ma_extended():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    # Price jumps 10% above SMA during the last 5 bars
    vals = [100.0] * 25 + [110.0] * 5
    close = pd.Series(vals, index=idx)
    sma20 = close.rolling(20).mean()
    dist = _dist_above_20ma(sma20, close, idx[-1])
    assert dist is not None
    assert dist > 0, "price above SMA20 → positive dist"


# ── loser_postmortem ──────────────────────────────────────────────────────────

def test_loser_postmortem_worst_selection():
    # High-score HIGH-confidence stop-outs should appear first
    hi = [_make_trade(-1.0, "stop", score=120.0, confidence="HIGH") for _ in range(5)]
    lo = [_make_trade(-1.0, "stop", score=60.0,  confidence="LOW")  for _ in range(10)]
    winners = [_make_trade(+2.0, "target") for _ in range(20)]
    enriched = lo + hi + winners   # hi placed after lo to test ordering
    pm = loser_postmortem(enriched, n=5)
    assert pm["n_worst"] == 5
    assert pm["n_total"] == 35
    assert pm["n_stop_outs"] == 15
    # All selected should be the HIGH-confidence, high-score stop-outs
    assert all(t["score"] == 120.0 for t in pm["worst_trades"])


def test_loser_postmortem_regime_frequency():
    bearish = [_make_trade(-1.0, "stop", spy_regime="BEARISH") for _ in range(10)]
    bullish = [_make_trade(+2.0, "target", spy_regime="BULLISH") for _ in range(20)]
    enriched = bearish + bullish
    pm = loser_postmortem(enriched, n=10)
    # All worst 10 are BEARISH
    assert pm["spy_regime"]["worst"].get("BEARISH", 0) == pytest.approx(1.0)
    # In population: 10/30 = 33% bearish
    assert pm["spy_regime"]["all"].get("BEARISH", 0) == pytest.approx(10 / 30)


def test_loser_postmortem_dist_buckets():
    extended = [_make_trade(-1.0, "stop", dist_above_20ma=9.0) for _ in range(10)]
    normal   = [_make_trade(+2.0, "target", dist_above_20ma=3.0) for _ in range(10)]
    enriched = extended + normal
    pm = loser_postmortem(enriched, n=10)
    # All worst should be in >8% bucket
    assert pm["dist_20ma"]["worst"].get(">8%", 0) == pytest.approx(1.0)


# ── dimension_analysis ────────────────────────────────────────────────────────

def test_dimension_analysis_spy_regime():
    bullish = [_make_trade(+1.0, "target", spy_regime="BULLISH") for _ in range(10)]
    bearish = [_make_trade(-0.5, "stop",   spy_regime="BEARISH") for _ in range(10)]
    enriched = bullish + bearish
    overall_exp = sum(r["r_multiple"] for r in enriched) / len(enriched)
    dim = dimension_analysis(enriched, overall_exp)

    assert "spy_regime" in dim
    assert "BULLISH" in dim["spy_regime"]
    assert "BEARISH" in dim["spy_regime"]

    bull_exp = dim["spy_regime"]["BULLISH"]["expectancy_r"]
    bear_exp = dim["spy_regime"]["BEARISH"]["expectancy_r"]
    assert bull_exp > bear_exp, "BULLISH regime should have higher expectancy"


def test_dimension_analysis_dist_buckets():
    close_dist = [_make_trade(+1.5, "target", dist_above_20ma=1.0) for _ in range(10)]
    far_dist   = [_make_trade(-0.5, "stop",   dist_above_20ma=9.0) for _ in range(10)]
    enriched = close_dist + far_dist
    overall_exp = sum(r["r_multiple"] for r in enriched) / len(enriched)
    dim = dimension_analysis(enriched, overall_exp)

    assert "dist_above_20ma" in dim
    assert "<2%" in dim["dist_above_20ma"]
    assert ">8%" in dim["dist_above_20ma"]
    assert dim["dist_above_20ma"]["<2%"]["expectancy_r"] > dim["dist_above_20ma"][">8%"]["expectancy_r"]


def test_dimension_analysis_delta_r():
    trades = [_make_trade(+1.0, "target") for _ in range(10)] + \
             [_make_trade(-1.0, "stop")   for _ in range(10)]
    overall_exp = 0.0
    dim = dimension_analysis(trades, overall_exp)
    # delta_r should be 0 if all trades have same regime
    for regime, stats in dim.get("spy_regime", {}).items():
        assert "delta_r" in stats


# ── render_postmortem ─────────────────────────────────────────────────────────

def test_render_postmortem_contains_key_sections():
    enriched = (
        [_make_trade(-1.0, "stop",   spy_regime="BEARISH") for _ in range(10)] +
        [_make_trade(+2.0, "target", spy_regime="BULLISH") for _ in range(20)]
    )
    overall_exp = sum(r["r_multiple"] for r in enriched) / len(enriched)
    pm  = loser_postmortem(enriched, n=5)
    dim = dimension_analysis(enriched, overall_exp)
    md  = render_postmortem(pm, dim, overall_exp, run_label="test_run")

    assert "E14.4" in md
    assert "test_run" in md
    assert "Pattern 1" in md   # SPY Regime section
    assert "Pattern 2" in md   # Dist above 20-MA section
    assert "Dimension Analysis" in md
    assert "SPY Regime" in md
    assert "Distance Above 20-MA" in md
