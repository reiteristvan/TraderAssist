"""DEPRECATED — replaced by scanner/strategies/breakout.py.

This module is a thin compatibility wrapper so legacy callers and test_fixtures.py
continue to work without modification. Use scan.py for new code.

Legacy API preserved:
    _evaluate(ticker, df, quality_dict) -> BreakoutResult | None
        Returns None when the setup does NOT qualify (old short-circuit behaviour).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from scanner.core import QualityInfo, EvalContext
from scanner.strategies.breakout import (
    evaluate as _new_evaluate,
    BreakoutResult,
    NEAR_HIGH_PCT,
    CONSOL_LOOKBACK,
    VOL_RATIO_MIN,
    RSI_RANGE,
    ADX_MIN,
    BB_WIDTH_PCTILE,
)


def _evaluate(
    ticker: str,
    df: pd.DataFrame,
    quality: dict,
) -> BreakoutResult | None:
    """Legacy 3-argument signature. Returns None when setup does not qualify."""
    qi = QualityInfo(
        profitable=bool(quality.get("profitable", False)),
        market_cap=quality.get("market_cap"),
        debt_equity=quality.get("debt_equity"),
        sector=quality.get("sector"),
        float_shares=quality.get("float_shares"),
    )
    ctx = EvalContext(
        as_of=df.index[-1].date(),
        market_data={},
        weekly=None,
        quality=qi,
        days_to_earnings=None,  # unknown → skip earnings gate
    )
    result = _new_evaluate(ticker, df, ctx)
    return result if result.qualified else None
