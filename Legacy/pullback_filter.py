"""
pullback_filter.py
High-quality pullback-to-support detector for US small/mid-caps.
Companion to breakout_filter.py.

Features all the criteria from the original + 7 enhancements:
  1. Relative Strength line vs SPY (gate + score bonus)
  2. Earnings calendar avoidance (gate)
  3. Pocket Pivot trigger (Gil Morales) (score bonus)
  4. Sector relative strength via SPDR ETFs (gate + bonus)
  5. NR7 volatility contraction (score bonus)
  6. Weekly trend confluence (gate)
  7. 200-MA distance check (gate + sweet-spot bonus)

CLI:
    python pullback_filter.py --ticker AAPL              # diagnose single name
    python pullback_filter.py --tickers AAPL,MSFT,NVDA   # scan list
    python pullback_filter.py --file tickers.txt         # scan from file
    python pullback_filter.py --csv results.csv          # save output
    python pullback_filter.py --show-all                 # include near-misses
    python pullback_filter.py                            # demo on sample

Evaluation semantics:
    Every check runs to completion regardless of failures along the way.
    The result includes `qualified` (True iff all gates passed),
    `failed_gates` (semicolon-joined names of failed gates), and
    `gates_passed`/`gates_total` counters. Score is always computed from
    whatever values are valid — useful as a tiebreaker among near-misses,
    but only meaningful if `qualified` is True.
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, SMAIndicator

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ============================================================
# Thresholds — tune per regime
# ============================================================

# Trend
TREND_LOOKBACK_HIGH    = 60
MA200_DIST_MIN         = 0.03   # < 3% = too close, fragile
MA200_DIST_MAX         = 0.30   # > 30% = extended
MA200_SWEET_SPOT       = (0.05, 0.25)

# Pullback geometry
SWING_HIGH_LOOKBACK    = 40
ADVANCE_WINDOW         = 30
PULLBACK_DEPTH_RANGE   = (0.04, 0.18)
PULLBACK_MIN_DAYS      = 3
PULLBACK_MAX_DAYS      = 20
SUPPORT_PROXIMITY_PCT  = 0.025

# Volume
VOL_CONTRACTION_MAX    = 0.85

# Momentum
RSI_PULLBACK_RANGE     = (40, 60)
ADX_MIN_TREND          = 20

# Quality
MARKET_CAP_RANGE       = (3e8, 5e9)
DOLLAR_VOL_MIN         = 5e6
DEBT_EQUITY_MAX        = 150.0

# Relative Strength
RS_LOOKBACK            = 60
RS_MIN                 = 0.90   # < 0.90 vs SPY = exclude

# Earnings
EARNINGS_BUFFER_DAYS   = 7      # exclude if earnings within N sessions

# Pocket Pivot
POCKET_PIVOT_LOOKBACK  = 10

# Weekly
WEEKLY_MA_PERIOD       = 30


# ============================================================
# Sector → SPDR ETF mapping (yfinance .info["sector"] keys)
# ============================================================

SECTOR_ETF_MAP = {
    "Technology":             "XLK",
    "Financial Services":     "XLF",
    "Healthcare":             "XLV",
    "Consumer Cyclical":      "XLY",
    "Communication Services": "XLC",
    "Industrials":            "XLI",
    "Consumer Defensive":     "XLP",
    "Energy":                 "XLE",
    "Utilities":              "XLU",
    "Real Estate":            "XLRE",
    "Basic Materials":        "XLB",
}


# ============================================================
# Result dataclass
# ============================================================

@dataclass
class PullbackResult:
    ticker: str
    close: float
    # trend
    sma50: float
    sma200: float
    ma200_distance_pct: float
    # pullback geometry
    swing_high: float
    pullback_depth_pct: float
    pullback_days: int
    support: str
    support_level: float
    distance_to_support_pct: float
    # volume / momentum
    vol_contraction: float
    rsi: float
    adx: float
    # bonuses
    trigger_candle: bool
    pocket_pivot: bool
    nr7: bool
    rs_strength: float
    rs_at_new_high: bool
    # context
    sector: Optional[str]
    sector_etf: Optional[str]
    sector_outperforming: bool
    weekly_above_30ma: bool
    weekly_30ma_rising: bool
    days_to_earnings: int
    # quality
    market_cap: float
    profitable: bool
    debt_equity: Optional[float]
    # verdict
    qualified: bool
    failed_gates: str       # semicolon-joined names of gates that failed
    gates_passed: int
    gates_total: int
    score: float


# ============================================================
# Market data cache (SPY + sector ETFs fetched once per scan)
# ============================================================

_market_data_cache: dict = {}


def _fetch_history(ticker: str, period: str = "1y",
                   interval: str = "1d") -> Optional[pd.DataFrame]:
    """Generic history fetcher with error handling."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval,
                                        auto_adjust=True)
        return df if df is not None and not df.empty else None
    except Exception:
        return None


def prefetch_market_data() -> dict:
    """Fetch SPY + all sector ETFs once. Returns dict keyed by symbol."""
    global _market_data_cache
    _market_data_cache = {}
    symbols = ["SPY"] + list(SECTOR_ETF_MAP.values())
    for sym in symbols:
        _market_data_cache[sym] = _fetch_history(sym, period="1y")
        time.sleep(0.1)
    return _market_data_cache


# ============================================================
# Quality (extended with sector + float)
# ============================================================

def _quality(ticker: str) -> dict:
    out = {
        "profitable":   False,
        "market_cap":   None,
        "debt_equity":  None,
        "sector":       None,
        "float_shares": None,
    }
    try:
        info = yf.Ticker(ticker).info or {}
        op_inc  = info.get("operatingIncome") or 0
        fwd_eps = info.get("forwardEps") or 0
        out["profitable"]   = (op_inc > 0) or (fwd_eps > 0)
        out["market_cap"]   = info.get("marketCap")
        out["debt_equity"]  = info.get("debtToEquity")
        out["sector"]       = info.get("sector")
        out["float_shares"] = info.get("floatShares")
    except Exception:
        pass
    return out


# ============================================================
# Individual check functions
# ============================================================

def _bullish_reversal_candle(df: pd.DataFrame) -> bool:
    """Hammer, bullish engulfing, or inside-bar break on the current bar."""
    if len(df) < 3:
        return False
    last, prev, prev2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    rng = last["High"] - last["Low"]
    if rng <= 0:
        return False
    body = abs(last["Close"] - last["Open"])
    lower_wick = min(last["Open"], last["Close"]) - last["Low"]

    hammer = (
        last["Close"] > last["Open"] and body > 0
        and lower_wick > 2 * body and lower_wick / rng > 0.5
    )
    engulf = (
        prev["Close"] < prev["Open"] and last["Close"] > last["Open"]
        and last["Close"] > prev["Open"] and last["Open"] < prev["Close"]
    )
    inside_break = (
        prev["High"] < prev2["High"] and prev["Low"] > prev2["Low"]
        and last["Close"] > prev["High"]
    )
    return bool(hammer or engulf or inside_break)


def _pocket_pivot(df: pd.DataFrame, lookback: int = POCKET_PIVOT_LOOKBACK) -> bool:
    """Up day with volume > max volume of any DOWN day in last `lookback` sessions.
    The Gil Morales pattern — institutional accumulation overwhelming prior selling."""
    if len(df) < lookback + 2:
        return False
    last = df.iloc[-1]
    if last["Close"] <= last["Open"]:
        return False
    recent = df.iloc[-lookback - 1: -1]
    down_mask = recent["Close"] < recent["Close"].shift(1)
    down_volumes = recent.loc[down_mask, "Volume"]
    if down_volumes.empty:
        return float(last["Volume"]) > float(recent["Volume"].mean()) * 1.5
    return float(last["Volume"]) > float(down_volumes.max())


def _nr7(df: pd.DataFrame) -> bool:
    """Today's range is the smallest of the last 7 sessions."""
    if len(df) < 7:
        return False
    ranges = df["High"] - df["Low"]
    return float(ranges.iloc[-1]) == float(ranges.iloc[-7:].min())


def _rs_metrics(stock_df: pd.DataFrame, spy_df: Optional[pd.DataFrame],
                lookback: int = RS_LOOKBACK) -> dict:
    """Compute RS line vs SPY. Returns strength (>1 = outperforming) and
    whether RS line is at a new lookback high (institutional accumulation signal)."""
    default = {"rs_strength": 1.0, "rs_at_new_high": False}
    if spy_df is None or len(spy_df) < lookback or len(stock_df) < lookback:
        return default
    aligned = pd.DataFrame({
        "stock": stock_df["Close"],
        "spy":   spy_df["Close"],
    }).dropna()
    if len(aligned) < lookback:
        return default
    rs_line = aligned["stock"] / aligned["spy"]
    rs_strength = float(rs_line.iloc[-1] / rs_line.iloc[-lookback])
    rs_high = float(rs_line.iloc[-lookback:].max())
    rs_at_high = float(rs_line.iloc[-1]) >= rs_high * 0.99
    return {"rs_strength": rs_strength, "rs_at_new_high": bool(rs_at_high)}


def _earnings_proximity(ticker: str) -> int:
    """Days until next earnings release. Returns 999 if unknown."""
    try:
        cal = yf.Ticker(ticker).calendar
        earnings_date = None
        if cal is None:
            return 999
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
        elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
            earnings_date = cal.loc["Earnings Date"].iloc[0]
        if isinstance(earnings_date, list):
            earnings_date = earnings_date[0] if earnings_date else None
        if earnings_date is None:
            return 999
        if isinstance(earnings_date, str):
            earnings_date = pd.Timestamp(earnings_date)
        if hasattr(earnings_date, "to_pydatetime"):
            earnings_date = pd.Timestamp(earnings_date)
        days = (earnings_date.normalize() - pd.Timestamp.now().normalize()).days
        return max(0, int(days))
    except Exception:
        return 999


def _sector_strength(sector: Optional[str], market_data: dict) -> dict:
    """Check if sector ETF is above its 50-MA and outperforming SPY."""
    out = {
        "sector_etf":           None,
        "sector_above_50ma":    False,
        "sector_outperforming": False,
    }
    if not sector:
        return out
    etf = SECTOR_ETF_MAP.get(sector)
    if not etf:
        return out
    out["sector_etf"] = etf
    etf_df = market_data.get(etf)
    spy_df = market_data.get("SPY")
    if etf_df is None or len(etf_df) < 50:
        return out
    sma50 = etf_df["Close"].rolling(50).mean().iloc[-1]
    out["sector_above_50ma"] = bool(etf_df["Close"].iloc[-1] > sma50)
    if spy_df is not None and len(spy_df) >= RS_LOOKBACK:
        etf_ret = etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-RS_LOOKBACK]
        spy_ret = spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-RS_LOOKBACK]
        out["sector_outperforming"] = bool(etf_ret > spy_ret)
    return out


def _weekly_trend(ticker: str) -> dict:
    """Higher-timeframe trend confluence: weekly close > weekly 30-MA, MA rising."""
    out = {"weekly_above_30ma": False, "weekly_30ma_rising": False}
    weekly = _fetch_history(ticker, period="2y", interval="1wk")
    if weekly is None or len(weekly) < WEEKLY_MA_PERIOD + 5:
        return out
    sma = weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
    out["weekly_above_30ma"]  = bool(weekly["Close"].iloc[-1] > sma.iloc[-1])
    out["weekly_30ma_rising"] = bool(sma.iloc[-1] > sma.iloc[-5])
    return out


# ============================================================
# Main evaluator
# ============================================================

def _evaluate(ticker: str, df: pd.DataFrame, q: dict,
              market_data: dict, verbose: bool = False) -> PullbackResult:
    """Run EVERY check (no short-circuit). Returns a PullbackResult with
    `qualified=True` only if all gates passed; otherwise still returns the
    full result with `failed_gates` populated. Verbose mode prints the
    complete log."""

    if verbose:
        print(f"\n=== {ticker} ===")

    failed_gates: list[str] = []
    gate_count = 0

    def gate(name: str, passed: bool, detail: str = "") -> bool:
        """Record a gate. Always continues — never returns early."""
        nonlocal gate_count
        gate_count += 1
        if verbose:
            mark = "✓" if passed else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")
        if not passed:
            failed_gates.append(name)
        return passed

    def bonus(name: str, present: bool, detail: str = "") -> None:
        if verbose:
            mark = "✓" if present else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")

    def section(title: str) -> None:
        if verbose:
            print(f"{title}:")

    close = float(df["Close"].iloc[-1])

    # ===== Trend context =====
    section("Trend context")

    sma50_s  = SMAIndicator(df["Close"], 50).sma_indicator()
    sma200_s = SMAIndicator(df["Close"], 200).sma_indicator()
    sma50    = float(sma50_s.iloc[-1])
    sma200   = float(sma200_s.iloc[-1])

    gate("Uptrend (SMA50 > SMA200)", sma50 > sma200,
         f"${sma50:.2f} vs ${sma200:.2f}")
    gate("SMA50 rising (20 sessions)",
         bool(sma50_s.iloc[-1] > sma50_s.iloc[-20]))

    high_52w = float(df["High"].rolling(252, min_periods=200).max().iloc[-1])
    near_high_recently = bool(
        (df["High"].iloc[-TREND_LOOKBACK_HIGH:] >= 0.98 * high_52w).any()
    )
    gate(f"Near 52w high in last {TREND_LOOKBACK_HIGH}d",
         near_high_recently, f"52w high ${high_52w:.2f}")

    ma200_dist = (close - sma200) / sma200
    in_sweet_spot = MA200_SWEET_SPOT[0] <= ma200_dist <= MA200_SWEET_SPOT[1]
    in_range = MA200_DIST_MIN <= ma200_dist <= MA200_DIST_MAX
    gate("200-MA distance in range", in_range,
         f"{ma200_dist*100:.1f}% — "
         f"{'sweet spot' if in_sweet_spot else 'acceptable' if in_range else 'out of range'}")

    # ===== Pullback geometry =====
    section("Pullback structure")

    sh_window = df.iloc[-SWING_HIGH_LOOKBACK:]
    swing_high = float(sh_window["High"].max())
    swing_high_idx = sh_window["High"].idxmax()
    swing_high_loc = df.index.get_loc(swing_high_idx)
    pullback_days = len(df) - 1 - swing_high_loc

    duration_ok = PULLBACK_MIN_DAYS <= pullback_days <= PULLBACK_MAX_DAYS
    gate(f"Pullback duration {pullback_days}d", duration_ok,
         f"target {PULLBACK_MIN_DAYS}-{PULLBACK_MAX_DAYS}d, swing high ${swing_high:.2f}")

    depth = (swing_high - close) / swing_high
    depth_ok = PULLBACK_DEPTH_RANGE[0] <= depth <= PULLBACK_DEPTH_RANGE[1]
    gate("Pullback depth", depth_ok,
         f"{depth*100:.1f}% — target "
         f"{PULLBACK_DEPTH_RANGE[0]*100:.0f}-{PULLBACK_DEPTH_RANGE[1]*100:.0f}%")

    # Compute windows defensively
    advance_start = max(0, swing_high_loc - ADVANCE_WINDOW)
    advance_window = df.iloc[advance_start: swing_high_loc + 1]
    pullback_window = df.iloc[swing_high_loc + 1:]
    have_windows = len(advance_window) >= 5 and len(pullback_window) >= 1

    if have_windows:
        prior_swing_low = float(advance_window["Low"].min())
        pullback_low = float(pullback_window["Low"].min())
        gate("Swing low intact", pullback_low >= prior_swing_low,
             f"pullback low ${pullback_low:.2f} vs prior ${prior_swing_low:.2f}")
    else:
        prior_swing_low = float("nan")
        pullback_low = float("nan")
        gate("Swing low intact", False, "insufficient window data")

    # ===== Volume & support =====
    section("Volume & support")

    if have_windows:
        avg_vol_adv = float(advance_window["Volume"].mean())
        avg_vol_pb  = float(pullback_window["Volume"].mean())
        vol_contraction = (avg_vol_pb / avg_vol_adv) if avg_vol_adv else float("nan")
        if pd.notna(vol_contraction):
            gate("Volume contraction", vol_contraction <= VOL_CONTRACTION_MAX,
                 f"{vol_contraction:.2f} (target ≤{VOL_CONTRACTION_MAX})")
        else:
            gate("Volume contraction", False, "no advance volume")
    else:
        vol_contraction = float("nan")
        gate("Volume contraction", False, "insufficient window data")

    # Support proximity — always compute
    sma20 = SMAIndicator(df["Close"], 20).sma_indicator()
    fib_anchor = prior_swing_low if pd.notna(prior_swing_low) else swing_high * 0.92
    fib_range = swing_high - fib_anchor
    candidates = {
        "SMA20":  float(sma20.iloc[-1]),
        "SMA50":  sma50,
        "fib_38": swing_high - 0.382 * fib_range,
        "fib_50": swing_high - 0.500 * fib_range,
        "fib_62": swing_high - 0.618 * fib_range,
    }
    valid = [(n, l, (close - l) / close)
             for n, l in candidates.items()
             if l > 0 and close >= l and (close - l) / close <= SUPPORT_PROXIMITY_PCT]
    if valid:
        support_name, support_level, distance_to_support = min(valid, key=lambda x: x[2])
        gate(f"At {support_name} support", True,
             f"${support_level:.2f}, {distance_to_support*100:.2f}% above")
    else:
        # Find the nearest support below price for diagnostic info
        below = [(n, l) for n, l in candidates.items() if l > 0 and close >= l]
        if below:
            nearest_n, nearest_l = min(below, key=lambda x: (close - x[1]) / close)
            support_name = nearest_n
            support_level = nearest_l
            distance_to_support = (close - nearest_l) / close
            gate("At a logical support level", False,
                 f"closest is {nearest_n} at ${nearest_l:.2f}, "
                 f"{distance_to_support*100:.1f}% below price (>{SUPPORT_PROXIMITY_PCT*100:.1f}% limit)")
        else:
            support_name = "none"
            support_level = float("nan")
            distance_to_support = float("nan")
            gate("At a logical support level", False,
                 "price is below all support candidates")

    # ===== Momentum =====
    section("Momentum")

    rsi = float(RSIIndicator(df["Close"], 14).rsi().iloc[-1])
    rsi_ok = RSI_PULLBACK_RANGE[0] <= rsi <= RSI_PULLBACK_RANGE[1]
    gate("RSI(14) reset", rsi_ok,
         f"{rsi:.1f} — target {RSI_PULLBACK_RANGE[0]}-{RSI_PULLBACK_RANGE[1]}")

    adx = float(ADXIndicator(df["High"], df["Low"], df["Close"], 14).adx().iloc[-1])
    adx_ok = adx >= ADX_MIN_TREND
    gate("ADX(14) trend strength", adx_ok,
         f"{adx:.1f} — min {ADX_MIN_TREND}")

    # ===== Filters =====
    section("Filters")

    days_to_earnings = _earnings_proximity(ticker)
    earnings_ok = days_to_earnings > EARNINGS_BUFFER_DAYS
    gate("Earnings clear", earnings_ok,
         f"{days_to_earnings}d away" if days_to_earnings < 999 else "no upcoming date")

    spy_df = market_data.get("SPY")
    rs = _rs_metrics(df, spy_df)
    rs_ok = rs["rs_strength"] >= RS_MIN
    gate("Relative strength vs SPY", rs_ok,
         f"60d RS={rs['rs_strength']:.2f}"
         f"{', at new high' if rs['rs_at_new_high'] else ''}")

    sector_info = _sector_strength(q.get("sector"), market_data)
    if sector_info["sector_etf"] is None:
        # Sector unknown — don't block, but log it
        gate("Sector strength", True, "sector unknown — skipped")
    else:
        gate(f"Sector ({sector_info['sector_etf']}) above 50MA",
             sector_info["sector_above_50ma"],
             f"vs SPY={'leading' if sector_info['sector_outperforming'] else 'lagging'}")

    weekly = _weekly_trend(ticker)
    gate("Weekly above 30-MA", weekly["weekly_above_30ma"],
         f"30MA rising={weekly['weekly_30ma_rising']}")

    avg_dollar_vol = float((df["Close"] * df["Volume"]).rolling(50).mean().iloc[-1])
    gate("Liquidity", avg_dollar_vol >= DOLLAR_VOL_MIN,
         f"${avg_dollar_vol/1e6:.1f}M avg daily $-vol")

    mc = q.get("market_cap")
    cap_ok = mc is not None and MARKET_CAP_RANGE[0] <= mc <= MARKET_CAP_RANGE[1]
    gate("Market cap in range", cap_ok,
         f"${mc/1e9:.2f}B" if mc else "unknown")

    gate("Profitable", bool(q.get("profitable")))

    de = q.get("debt_equity")
    de_ok = de is None or de <= DEBT_EQUITY_MAX
    gate("Debt/equity acceptable", de_ok,
         f"{de:.1f}" if de is not None else "unknown")

    # ===== Bonus signals (no gates) =====
    section("Bonus signals")
    trigger = _bullish_reversal_candle(df)
    pp = _pocket_pivot(df)
    nr7 = _nr7(df)
    bonus("Bullish reversal candle", trigger)
    bonus("Pocket Pivot trigger", pp)
    bonus("NR7 contraction", nr7)
    bonus("RS line at 60d high", rs["rs_at_new_high"])
    bonus("Sector outperforming SPY", sector_info["sector_outperforming"])
    bonus("Weekly 30-MA rising", weekly["weekly_30ma_rising"])
    bonus("200-MA in sweet spot", in_sweet_spot)

    # ===== Composite score (defensive against NaN) =====
    def _safe(v: float, fallback: float = 0.0) -> float:
        return fallback if pd.isna(v) else float(v)

    optimal_depth = 0.08
    vc_safe = _safe(vol_contraction, 1.0)        # missing -> no bonus
    dist_safe = _safe(distance_to_support, SUPPORT_PROXIMITY_PCT)
    score = (
        max(0, 30 - abs(depth - optimal_depth) * 200)
        + (1.0 - vc_safe) * 50
        + (1.0 - dist_safe / SUPPORT_PROXIMITY_PCT) * 20
        + (50 - abs(rsi - 50)) * 0.5
        + (15 if trigger else 0)
        + (25 if pp else 0)
        + (10 if nr7 else 0)
        + (30 if rs["rs_at_new_high"] else 0)
        + (rs["rs_strength"] - 1.0) * 30
        + (10 if sector_info["sector_outperforming"] else 0)
        + (10 if weekly["weekly_30ma_rising"] else 0)
        + (10 if in_sweet_spot else 0)
        + (adx - 20) * 0.5
    )

    qualified = len(failed_gates) == 0
    gates_passed = gate_count - len(failed_gates)

    if verbose:
        if qualified:
            print(f"\n  VERDICT: ✓ QUALIFIES — score {score:.1f} "
                  f"({gates_passed}/{gate_count} gates passed)\n")
        else:
            print(f"\n  VERDICT: ✗ DOES NOT QUALIFY — "
                  f"{gates_passed}/{gate_count} gates passed")
            print(f"  Failed gates: {', '.join(failed_gates)}")
            print(f"  Score (informational only): {score:.1f}\n")

    return PullbackResult(
        ticker                  = ticker,
        close                   = round(close, 2),
        sma50                   = round(sma50, 2),
        sma200                  = round(sma200, 2),
        ma200_distance_pct      = round(ma200_dist * 100, 2),
        swing_high              = round(swing_high, 2),
        pullback_depth_pct      = round(depth * 100, 2),
        pullback_days           = pullback_days,
        support                 = support_name,
        support_level           = round(support_level, 2) if pd.notna(support_level) else float("nan"),
        distance_to_support_pct = round(distance_to_support * 100, 2) if pd.notna(distance_to_support) else float("nan"),
        vol_contraction         = round(vol_contraction, 2) if pd.notna(vol_contraction) else float("nan"),
        rsi                     = round(rsi, 1),
        adx                     = round(adx, 1),
        trigger_candle          = trigger,
        pocket_pivot            = pp,
        nr7                     = nr7,
        rs_strength             = round(rs["rs_strength"], 3),
        rs_at_new_high          = rs["rs_at_new_high"],
        sector                  = q.get("sector"),
        sector_etf              = sector_info.get("sector_etf"),
        sector_outperforming    = sector_info["sector_outperforming"],
        weekly_above_30ma       = weekly["weekly_above_30ma"],
        weekly_30ma_rising      = weekly["weekly_30ma_rising"],
        days_to_earnings        = days_to_earnings,
        market_cap              = mc if mc is not None else float("nan"),
        profitable              = bool(q.get("profitable")),
        debt_equity             = de,
        qualified               = qualified,
        failed_gates            = "; ".join(failed_gates),
        gates_passed            = gates_passed,
        gates_total             = gate_count,
        score                   = round(score, 1),
    )


# ============================================================
# Entry points
# ============================================================

def scan_pullbacks(tickers: Iterable[str], verbose: bool = False,
                   sleep_sec: float = 0.2) -> pd.DataFrame:
    """Batch scan. Pre-fetches market data once, then evaluates each ticker."""
    if not _market_data_cache:
        if verbose:
            print("Fetching market data (SPY + sector ETFs)...")
        prefetch_market_data()

    rows = []
    tickers = list(tickers)
    for i, tkr in enumerate(tickers, 1):
        if verbose and not _is_single_mode(tickers):
            print(f"[{i}/{len(tickers)}] {tkr}", end="\r")
        df = _fetch_history(tkr)
        if df is None or len(df) < 220:
            continue
        q = _quality(tkr)
        result = _evaluate(tkr, df, q, _market_data_cache, verbose=verbose)
        if result is not None:
            rows.append(asdict(result))
        time.sleep(sleep_sec)

    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .sort_values("score", ascending=False)
            .reset_index(drop=True))


def _is_single_mode(tickers) -> bool:
    return hasattr(tickers, "__len__") and len(tickers) == 1


def diagnose_ticker(ticker: str) -> Optional[PullbackResult]:
    """Verbose single-ticker diagnostic. Always prints the full check log."""
    if not _market_data_cache:
        print("Fetching market data (SPY + sector ETFs)...")
        prefetch_market_data()
    df = _fetch_history(ticker)
    if df is None or len(df) < 220:
        print(f"\n=== {ticker} ===")
        print(f"  ✗ Insufficient price history available")
        return None
    q = _quality(ticker)
    return _evaluate(ticker, df, q, _market_data_cache, verbose=True)


# ============================================================
# CLI
# ============================================================

SAMPLE_UNIVERSE = [
    "RKLB", "CELH", "ELF",  "CVNA", "DUOL",
    "HIMS", "FTAI", "SOUN", "IOT",  "BWXT",
    "CAVA", "MARA", "RIOT", "PLAY", "GTLB",
]


def _print_results(df: pd.DataFrame, csv_path: Optional[str] = None,
                   show_all: bool = False) -> None:
    """Print results. By default shows only qualified candidates; use show_all=True
    to also show near-misses with their failed gates."""
    if df.empty:
        print("No tickers evaluated (data fetch failed for all).")
        return

    qualified = df[df["qualified"]].copy() if "qualified" in df.columns else df
    failed    = df[~df["qualified"]].copy() if "qualified" in df.columns else pd.DataFrame()

    cols = ["ticker", "close", "swing_high", "pullback_depth_pct", "pullback_days",
            "support", "vol_contraction", "rsi", "adx", "rs_strength",
            "rs_at_new_high", "pocket_pivot", "nr7", "trigger_candle",
            "sector_etf", "gates_passed", "gates_total", "score"]
    cols_present = [c for c in cols if c in df.columns]

    if not qualified.empty:
        print("=== QUALIFIED ===")
        print(qualified[cols_present].to_string(index=False))
        print(f"\n{len(qualified)} qualified candidate(s).")
    else:
        print("No qualified candidates this scan.")

    if show_all and not failed.empty:
        print("\n=== NEAR-MISSES (failed at least one gate) ===")
        # Sort failures by how close they came: gates_passed desc, then score desc
        near = failed.sort_values(
            ["gates_passed", "score"], ascending=[False, False]
        )
        near_cols = cols_present + (["failed_gates"] if "failed_gates" in df.columns else [])
        # Show top 20 near-misses to avoid spam
        print(near[near_cols].head(20).to_string(index=False))
        print(f"\n{len(failed)} near-miss(es) (showing top 20).")

    if csv_path:
        df.to_csv(csv_path, index=False)
        print(f"\nFull results (qualified + near-misses) saved to {csv_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pullback-to-support setup detector for US small/mid-caps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  pullback_filter.py --ticker AAPL\n"
               "  pullback_filter.py --tickers AAPL,MSFT,NVDA --csv out.csv\n"
               "  pullback_filter.py --file my_universe.txt --verbose",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--ticker", help="Single ticker — diagnoses it verbosely")
    src.add_argument("--tickers", help="Comma-separated list to scan")
    src.add_argument("--file", help="Path to file with one ticker per line")
    parser.add_argument("--csv", help="Save full results to CSV")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-criterion log for every ticker")
    parser.add_argument("--show-all", action="store_true", dest="show_all",
                        help="Also show near-misses (tickers that failed >=1 gate)")
    args = parser.parse_args()

    if args.ticker:
        result = diagnose_ticker(args.ticker.upper().strip())
        if result and args.csv:
            pd.DataFrame([asdict(result)]).to_csv(args.csv, index=False)
            print(f"Saved to {args.csv}")
        return 0

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.file:
        with open(args.file) as f:
            tickers = [line.strip().upper() for line in f
                       if line.strip() and not line.startswith("#")]
    else:
        print(f"No input given — running on sample universe ({len(SAMPLE_UNIVERSE)} tickers).")
        print("Use --ticker, --tickers, or --file for real scans.\n")
        tickers = SAMPLE_UNIVERSE

    df = scan_pullbacks(tickers, verbose=args.verbose)
    print()  # newline after progress indicator
    _print_results(df, args.csv, show_all=args.show_all)
    return 0


if __name__ == "__main__":
    sys.exit(main())