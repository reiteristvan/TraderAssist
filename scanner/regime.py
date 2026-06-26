"""E4.2/E4.3 — Market regime, ATH zones, and confidence rating.

market_regime(): display + confidence input only — never a gate.
ath_zone(): point-in-time ATH zone labeling on top of data_store.get_ath.
compute_confidence(): verbatim from swing_scanner, inputs adapted.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

import pandas as pd


def market_regime(
    market_data: dict[str, pd.DataFrame],
) -> Literal["BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"]:
    """Classify market regime from the E1.3 market data bundle.

    Logic: SPY close vs SMA50 and EMA20 (verbatim from swing_scanner check_market_regime).
    <50 SPY rows → UNKNOWN.
    """
    spy_df = market_data.get("SPY")
    if spy_df is None or len(spy_df) < 50:
        return "UNKNOWN"

    sma50 = float(spy_df["Close"].rolling(50).mean().iloc[-1])
    ema20 = float(spy_df["Close"].ewm(span=20).mean().iloc[-1])
    price = float(spy_df["Close"].iloc[-1])

    if price > sma50 and price > ema20:
        return "BULLISH"
    elif price < sma50 and price < ema20:
        return "BEARISH"
    else:
        return "NEUTRAL"


def _ath_zone_label(
    close: float,
    ath: float | None,
) -> tuple[float, float, str]:
    """Compute ATH zone from a known ATH value — no disk access.

    Separated from ath_zone() so the backtest loop can use a pre-computed
    ATH series (expanding max) without re-reading parquet on every iteration.
    """
    if ath is None or ath == 0:
        return (0.0, 0.0, "UNKNOWN")

    dist_pct = ((close - ath) / ath) * 100  # negative = below ATH

    if dist_pct >= -1:
        zone = "NEW_ATH"
    elif dist_pct >= -10:
        zone = "NEAR_ATH"
    elif dist_pct >= -30:
        zone = "MODERATE"
    elif dist_pct >= -60:
        zone = "FAR"
    else:
        zone = "DEEP"

    return (round(ath, 2), round(dist_pct, 1), zone)


def ath_zone(
    ticker: str,
    close: float,
    end: date | None = None,
) -> tuple[float, float, str]:
    """Return (ath_price, dist_pct, zone_label) for a ticker.

    Zone labels (verbatim from swing_scanner fetch_ath):
      NEW_ATH  — within 1%   (clear skies, no resistance)
      NEAR_ATH — within 10%  (minimal overhead supply)
      MODERATE — 10–30% below ATH
      FAR      — 30–60% below ATH
      DEEP     — 60%+ below ATH
    Returns (0, 0, "UNKNOWN") on data shortage.
    """
    from scanner.data_store import get_ath as _get_ath
    return _ath_zone_label(close, _get_ath(ticker, end=end))


def compute_confidence(
    score: float,
    adx: float,
    weekly_aligned: bool,
    market_regime_str: str,
    obstacles: int,
    rr: float,
    sma_slope: float,
    macd_bullish: bool,
    ath_zone_label: str = "",
) -> str:
    """Composite confidence rating: HIGH / MEDIUM / LOW.

    Verbatim point system from swing_scanner.compute_confidence (lines 742–814).
    Max ~18 points. ≥12 → HIGH, ≥7 → MEDIUM, else LOW.
    """
    points = 0

    # Score contribution (0–3)
    if score >= 80:
        points += 3
    elif score >= 70:
        points += 2
    elif score >= 60:
        points += 1

    # Trend strength (0–3)
    if adx >= 30:
        points += 3
    elif adx >= 25:
        points += 2
    elif adx >= 20:
        points += 1

    # Weekly alignment (0–2)
    if weekly_aligned:
        points += 2

    # Market regime (0–2)
    if market_regime_str == "BULLISH":
        points += 2
    elif market_regime_str == "NEUTRAL":
        points += 1

    # Obstacles (−1 to 0)
    if obstacles >= 3:
        points -= 1

    # R/R ratio (0–2)
    if rr >= 3.0:
        points += 2
    elif rr >= 2.0:
        points += 1

    # SMA slope (0–1)
    if sma_slope > 0.5:
        points += 1

    # MACD (0–1)
    if macd_bullish:
        points += 1

    # ATH zone (−2 to +3)
    if ath_zone_label == "NEW_ATH":
        points += 3
    elif ath_zone_label == "NEAR_ATH":
        points += 2
    elif ath_zone_label == "MODERATE":
        points += 0
    elif ath_zone_label == "FAR":
        points -= 1
    elif ath_zone_label == "DEEP":
        points -= 2

    if points >= 12:
        return "HIGH"
    elif points >= 7:
        return "MEDIUM"
    else:
        return "LOW"
