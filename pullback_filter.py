"""DEPRECATED — replaced by scanner/strategies/pullback.py.

This module is a thin compatibility wrapper so legacy callers and test_fixtures.py
continue to work without modification. Use scan.py for new code.

Legacy API preserved:
    _evaluate(ticker, df, quality_dict, market_data_dict, verbose=False) -> PullbackResult
    _earnings_proximity(ticker) -> int   # monkeypatchable
    _weekly_trend(ticker) -> dict        # monkeypatchable
    SECTOR_ETF_MAP                       # re-exported from scanner.core
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from scanner.core import (
    EARNINGS_BUFFER_DAYS,
    SECTOR_ETF_MAP,
    QualityInfo,
    EvalContext,
    WEEKLY_MA_PERIOD,
)
from scanner.strategies.pullback import evaluate as _new_evaluate, PullbackResult


# ── Monkeypatchable network functions ─────────────────────────────────────────

def _earnings_proximity(ticker: str) -> int:
    """Days to next earnings. Returns 999 when unknown (old sentinel)."""
    from scanner.core import _days_to_earnings
    days = _days_to_earnings(ticker, date.today())
    return days if days is not None else 999


def _weekly_trend(ticker: str) -> dict:
    """Return weekly trend alignment dict. Monkeypatchable for offline tests."""
    from scanner.data_store import get_weekly
    weekly = get_weekly(ticker)
    if weekly is None or len(weekly) < 35:
        return {"weekly_above_30ma": False, "weekly_30ma_rising": False}
    wma = weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
    above = bool(weekly["Close"].iloc[-1] > wma.iloc[-1])
    rising = bool(wma.iloc[-1] > wma.iloc[-5])
    return {"weekly_above_30ma": above, "weekly_30ma_rising": rising}


def _make_weekly_from_dict(d: dict) -> pd.DataFrame:
    """Build a synthetic weekly DataFrame satisfying the weekly gate conditions.

    Used by the adapter _evaluate so the patched _weekly_trend dict feeds the
    new evaluate() which expects a DataFrame, not a dict.
    """
    above = d.get("weekly_above_30ma", False)
    rising = d.get("weekly_30ma_rising", False)
    n = 40
    if above and rising:
        # Ascending series: close[-1] > MA[-1] and MA[-1] > MA[-6]
        closes = np.linspace(85, 124, n)
    else:
        # Descending series: fails above and/or rising
        closes = np.linspace(125, 86, n)

    idx = pd.date_range(end=pd.Timestamp("2026-06-12"), periods=n, freq="W-FRI")  # must end on Friday
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": np.ones(n) * 1_000_000},
        index=idx,
    )


# ── Legacy _evaluate adapter ──────────────────────────────────────────────────

def _evaluate(
    ticker: str,
    df: pd.DataFrame,
    quality: dict,
    market_data: dict,
    verbose: bool = False,
) -> PullbackResult:
    """Legacy 4-argument signature. Internally calls scanner.strategies.pullback.evaluate."""
    # Convert quality dict → QualityInfo
    qi = QualityInfo(
        profitable=bool(quality.get("profitable", False)),
        market_cap=quality.get("market_cap"),
        debt_equity=quality.get("debt_equity"),
        sector=quality.get("sector"),
        float_shares=quality.get("float_shares"),
    )

    # Earnings: use the monkeypatchable _earnings_proximity
    raw_days = _earnings_proximity(ticker)
    days_to_earnings: Optional[int] = None if raw_days == 999 else raw_days

    # Weekly: use the monkeypatchable _weekly_trend, convert to DataFrame
    weekly_info = _weekly_trend(ticker)
    weekly_df = _make_weekly_from_dict(weekly_info)

    ctx = EvalContext(
        as_of=df.index[-1].date(),
        market_data=market_data,
        weekly=weekly_df,
        quality=qi,
        days_to_earnings=days_to_earnings,
    )

    return _new_evaluate(ticker, df, ctx, verbose=verbose)


# ── Expose any constants callers may reference ────────────────────────────────
# (kept for import compatibility)
from scanner.core import (
    RSI_PULLBACK_RANGE,
    PULLBACK_DEPTH_RANGE,
    ADX_MIN_TREND,
    SWING_HIGH_LOOKBACK,
    MA200_DIST_MIN,
    MA200_DIST_MAX,
)
