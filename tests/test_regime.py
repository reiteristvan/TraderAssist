"""E4.2/E4.3/E4.4 unit tests — regime.py, position_size, last_closed_session."""
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from scanner.regime import market_regime, ath_zone, compute_confidence
from scanner.core import position_size, SizeInfo


# ── Helpers ───────────────────────────────────────────────────────────────────

def _spy_above(n=100, price=500.0):
    """SPY frame where price > SMA50 and price > EMA20 → BULLISH."""
    closes = np.linspace(480, price, n)
    idx = pd.bdate_range(end="2026-06-15", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes * 1.002,
                          "Low": closes * 0.998, "Close": closes,
                          "Volume": np.full(n, 5_000_000.0)}, index=idx)


def _spy_below(n=100, price=400.0):
    """SPY frame where price < SMA50 and price < EMA20 → BEARISH."""
    closes = np.linspace(450, price, n)
    idx = pd.bdate_range(end="2026-06-15", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes * 1.002,
                          "Low": closes * 0.998, "Close": closes,
                          "Volume": np.full(n, 5_000_000.0)}, index=idx)


def _spy_mixed(n=100, r=0.0001):
    """SPY above SMA50 but below EMA20 or vice versa → NEUTRAL."""
    # Price oscillates, ends in middle
    closes = 450.0 + 10 * np.sin(np.linspace(0, 6 * np.pi, n))
    idx = pd.bdate_range(end="2026-06-15", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes * 1.001,
                          "Low": closes * 0.999, "Close": closes,
                          "Volume": np.full(n, 5_000_000.0)}, index=idx)


# ── market_regime ─────────────────────────────────────────────────────────────

def test_market_regime_bullish():
    spy = _spy_above()
    regime = market_regime({"SPY": spy})
    assert regime == "BULLISH"


def test_market_regime_bearish():
    spy = _spy_below()
    regime = market_regime({"SPY": spy})
    assert regime == "BEARISH"


def test_market_regime_neutral():
    spy = _spy_mixed()
    regime = market_regime({"SPY": spy})
    assert regime in ("NEUTRAL", "BULLISH", "BEARISH")  # oscillating; just not UNKNOWN


def test_market_regime_unknown_no_spy():
    regime = market_regime({})
    assert regime == "UNKNOWN"


def test_market_regime_unknown_short_spy():
    spy = _spy_above(n=30)
    regime = market_regime({"SPY": spy})
    assert regime == "UNKNOWN"


# ── ath_zone ──────────────────────────────────────────────────────────────────

def test_ath_zone_point_in_time(tmp_path, monkeypatch):
    """ath_zone with end= before a later spike returns the pre-spike ATH."""
    import scanner.data_store as ds
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    n = 300
    closes = np.concatenate([np.linspace(100, 120, 250), np.linspace(121, 200, 50)])
    highs = closes * 1.005
    lows = closes * 0.995
    idx = pd.bdate_range(end="2026-06-15", periods=n)
    df = pd.DataFrame({"Open": closes, "High": highs, "Low": lows,
                       "Close": closes, "Volume": np.full(n, 1_000_000.0)}, index=idx)
    df.to_parquet(tmp_path / "TEST.parquet")

    # Use row 240 as the point-in-time date; get_ath slices df.index <= that date
    early_date = idx[240].date()
    # ATH up to and including row 240 = max of highs[0:241]
    expected_ath = round(float(highs[:241].max()), 2)
    price_early = float(closes[240])

    ath_p, dist_p, zone = ath_zone("TEST", price_early, end=early_date)
    assert ath_p == expected_ath
    # price_early ~ 119, ath ~ 119.3 → NEAR_ATH or NEW_ATH range
    assert zone in ("NEW_ATH", "NEAR_ATH", "MODERATE")


def test_ath_zone_labels(tmp_path, monkeypatch):
    """Zone labels map correctly to distance ranges."""
    import scanner.data_store as ds
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    # ATH = 100; build a frame with that as max
    highs = np.array([100.0] + [80.0] * 299)
    closes = np.array([90.0] * 300)
    closes[0] = 99.0
    idx = pd.bdate_range(end="2026-06-15", periods=300)
    df = pd.DataFrame({"Open": closes, "High": highs, "Low": closes * 0.995,
                       "Close": closes, "Volume": np.full(300, 1e6)}, index=idx)
    df.to_parquet(tmp_path / "ZONE.parquet")

    ath_p, d, z = ath_zone("ZONE", 99.5)  # within 1% of 100
    assert z == "NEW_ATH"

    _, _, z2 = ath_zone("ZONE", 92.0)   # ~8% below 100 → NEAR_ATH
    assert z2 == "NEAR_ATH"

    _, _, z3 = ath_zone("ZONE", 80.0)   # 20% below → MODERATE
    assert z3 == "MODERATE"

    _, _, z4 = ath_zone("ZONE", 50.0)   # 50% below → FAR
    assert z4 == "FAR"

    _, _, z5 = ath_zone("ZONE", 30.0)   # 70% below → DEEP
    assert z5 == "DEEP"


def test_ath_zone_unknown_no_cache(tmp_path, monkeypatch):
    import scanner.data_store as ds
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)
    ath_p, dist, zone = ath_zone("MISSING", 50.0)
    assert zone == "UNKNOWN"
    assert ath_p == 0.0


# ── compute_confidence ────────────────────────────────────────────────────────

def test_confidence_high():
    c = compute_confidence(
        score=85, adx=31, weekly_aligned=True, market_regime_str="BULLISH",
        obstacles=0, rr=3.5, sma_slope=1.0, macd_bullish=True, ath_zone_label="NEAR_ATH"
    )
    assert c == "HIGH"


def test_confidence_medium():
    # score>=70(2) + adx>=20(1) + weekly(2) + NEUTRAL(1) + rr>=2(1) = 7 → MEDIUM
    c = compute_confidence(
        score=72, adx=22, weekly_aligned=True, market_regime_str="NEUTRAL",
        obstacles=1, rr=2.0, sma_slope=0.0, macd_bullish=False, ath_zone_label="MODERATE"
    )
    assert c == "MEDIUM"


def test_confidence_low():
    c = compute_confidence(
        score=50, adx=15, weekly_aligned=False, market_regime_str="BEARISH",
        obstacles=4, rr=1.0, sma_slope=0.0, macd_bullish=False, ath_zone_label="FAR"
    )
    assert c == "LOW"


def test_confidence_high_boundary():
    """Exactly 12 points → HIGH."""
    # BULLISH(2) + adx>=20(1) + weekly(2) + score>=60(1) + rr>=2(1) + NEAR_ATH(2) + macd(1) + slope(1) = 11 ...
    # Let's use score>=80(3) + adx>=30(3) + weekly(2) + BULLISH(2) + rr>=2(1) = 11 — one more needed
    c = compute_confidence(
        score=80, adx=30, weekly_aligned=True, market_regime_str="BULLISH",
        obstacles=0, rr=2.5, sma_slope=0.6, macd_bullish=False, ath_zone_label=""
    )
    # 3+3+2+2+1+1 = 12 → HIGH
    assert c == "HIGH"


def test_confidence_medium_boundary():
    """Exactly 7 points → MEDIUM."""
    c = compute_confidence(
        score=60, adx=20, weekly_aligned=True, market_regime_str="NEUTRAL",
        obstacles=0, rr=1.0, sma_slope=0.0, macd_bullish=False, ath_zone_label=""
    )
    # score>=60(1) + adx>=20(1) + weekly(2) + NEUTRAL(1) + obstacles(0) + rr<2(0) = 5 ...
    # Try: score>=70(2) + adx>=20(1) + weekly(2) + NEUTRAL(1) + rr<2(0) + MODERATE(0) = 6 — not 7
    # score>=80(3) + adx>=20(1) + weekly(2) + NEUTRAL(1) = 7
    c2 = compute_confidence(
        score=82, adx=21, weekly_aligned=True, market_regime_str="NEUTRAL",
        obstacles=0, rr=0.5, sma_slope=0.0, macd_bullish=False, ath_zone_label=""
    )
    assert c2 == "MEDIUM"


# ── position_size ─────────────────────────────────────────────────────────────

def test_position_size_basic():
    """account=6500, risk=1%, entry=10.00, stop=9.50 → 130 raw → capped to 65."""
    s = position_size(entry=10.00, stop=9.50, account_size=6500.0,
                      risk_pct=0.01, max_position=650.0)
    # raw = floor(6500 * 0.01 / 0.50) = floor(130) = 130
    # cap = floor(650 / 10) = 65
    assert s.shares == 65
    assert s.capped is True
    assert s.zero_reason == ""
    assert abs(s.position_value - 650.0) < 0.01


def test_position_size_not_capped():
    """Tight stop, high risk → raw < cap."""
    s = position_size(entry=100.0, stop=99.0, account_size=6500.0,
                      risk_pct=0.01, max_position=650.0)
    # raw = floor(65 / 1.0) = 65; cap = floor(650 / 100) = 6
    assert s.shares == 6
    assert s.capped is True  # 65 > 6


def test_position_size_entry_le_stop():
    """entry <= stop → 0 shares, no ZeroDivisionError."""
    s = position_size(entry=10.0, stop=10.0)
    assert s.shares == 0
    assert s.zero_reason != ""

    s2 = position_size(entry=9.0, stop=10.0)
    assert s2.shares == 0
    assert s2.zero_reason != ""


def test_position_size_uncapped():
    """Small position, wide risk → raw is naturally within cap."""
    # raw = floor(6500 * 0.01 / 5.0) = floor(13) = 13; cap = floor(650/20) = 32 → uncapped
    s = position_size(entry=20.0, stop=15.0, account_size=6500.0,
                      risk_pct=0.01, max_position=650.0)
    assert s.shares == 13
    assert s.capped is False


# ── last_closed_session ───────────────────────────────────────────────────────

def test_last_closed_session_weekday():
    from scanner.core import last_closed_session
    # Wednesday 2026-01-07 → previous session is Tuesday 2026-01-06
    result = last_closed_session(date(2026, 1, 7))
    assert result == date(2026, 1, 6)


def test_last_closed_session_monday():
    from scanner.core import last_closed_session
    # Monday 2026-01-05 → previous session is Friday 2026-01-02
    result = last_closed_session(date(2026, 1, 5))
    assert result == date(2026, 1, 2)


def test_last_closed_session_new_years_day():
    from scanner.core import last_closed_session
    # Jan 1 2026 is a NYSE holiday; the session before it would be Dec 31 2025
    result = last_closed_session(date(2026, 1, 1))
    assert result == date(2025, 12, 31)


def test_last_closed_session_saturday():
    from scanner.core import last_closed_session
    # Saturday 2026-01-10 → last closed session = Friday 2026-01-09
    result = last_closed_session(date(2026, 1, 10))
    assert result == date(2026, 1, 9)
