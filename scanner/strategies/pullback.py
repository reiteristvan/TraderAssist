"""E2.2 — Pure pullback evaluate() on GateLog/EvalContext.

Replaces pullback_filter._evaluate. Zero network I/O, zero wall clock.
See CLAUDE.md EPIC E2.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, SMAIndicator

from scanner.core import (
    ADVANCE_WINDOW,
    ADX_MIN_TREND,
    DEBT_EQUITY_MAX,
    DOLLAR_VOL_MIN,
    EARNINGS_BUFFER_DAYS,
    MA200_DIST_MAX,
    MA200_DIST_MIN,
    MA200_SWEET_SPOT,
    MARKET_CAP_RANGE,
    PULLBACK_DEPTH_RANGE,
    PULLBACK_MAX_DAYS,
    PULLBACK_MIN_DAYS,
    RSI_PULLBACK_RANGE,
    RS_MIN,
    SECTOR_ETF_MAP,
    SUPPORT_PROXIMITY_PCT,
    SWING_HIGH_LOOKBACK,
    TREND_LOOKBACK_HIGH,
    VOL_CONTRACTION_MAX,
    WEEKLY_MA_PERIOD,
    EvalContext,
    GateLog,
    _bullish_reversal_candle,
    _nr7,
    _pocket_pivot,
    _rs_metrics,
    _sector_strength,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


@dataclass
class PullbackResult:
    ticker: str
    close: float
    sma50: float
    sma200: float
    ma200_distance_pct: float
    swing_high: float
    pullback_depth_pct: float
    pullback_days: int
    support: str
    support_level: float
    distance_to_support_pct: float
    vol_contraction: float
    rsi: float
    adx: float
    trigger_candle: bool
    pocket_pivot: bool
    nr7: bool
    rs_strength: float
    rs_at_new_high: bool
    sector: Optional[str]
    sector_etf: Optional[str]
    sector_outperforming: bool
    weekly_above_30ma: bool
    weekly_30ma_rising: bool
    days_to_earnings: Optional[int]
    market_cap: float
    profitable: bool
    debt_equity: Optional[float]
    qualified: bool
    failed_gates: list[str]    # list; join with "; " only at CSV export time
    skipped_gates: list[str]
    gates_passed: int
    gates_total: int
    score: float
    as_of: date


def evaluate(ticker: str, df: pd.DataFrame, ctx: EvalContext,
             verbose: bool = False) -> PullbackResult:
    """Evaluate a pullback setup. Pure — no network I/O, no wall clock."""
    log = GateLog(ticker, verbose=verbose)
    close = float(df["Close"].iloc[-1])

    # ── Trend context ──────────────────────────────────────────────────────────
    log.section("Trend context")

    sma50_s  = SMAIndicator(df["Close"], 50).sma_indicator()
    sma200_s = SMAIndicator(df["Close"], 200).sma_indicator()
    sma50    = float(sma50_s.iloc[-1])
    sma200   = float(sma200_s.iloc[-1])

    log.gate("Uptrend (SMA50 > SMA200)", sma50 > sma200,
             f"${sma50:.2f} vs ${sma200:.2f}")
    log.gate("SMA50 rising (20 sessions)",
             bool(sma50_s.iloc[-1] > sma50_s.iloc[-20]))

    high_52w = float(df["High"].rolling(252, min_periods=200).max().iloc[-1])
    near_high_recently = bool(
        (df["High"].iloc[-TREND_LOOKBACK_HIGH:] >= 0.98 * high_52w).any()
    )
    log.gate(f"Near 52w high in last {TREND_LOOKBACK_HIGH}d",
             near_high_recently, f"52w high ${high_52w:.2f}")

    ma200_dist = (close - sma200) / sma200
    in_sweet_spot = MA200_SWEET_SPOT[0] <= ma200_dist <= MA200_SWEET_SPOT[1]
    in_range = MA200_DIST_MIN <= ma200_dist <= MA200_DIST_MAX
    log.gate("200-MA distance in range", in_range,
             f"{ma200_dist*100:.1f}% — "
             f"{'sweet spot' if in_sweet_spot else 'acceptable' if in_range else 'out of range'}")

    # ── Pullback structure ─────────────────────────────────────────────────────
    log.section("Pullback structure")

    sh_window = df.iloc[-SWING_HIGH_LOOKBACK:]
    swing_high = float(sh_window["High"].max())
    swing_high_idx = sh_window["High"].idxmax()
    swing_high_loc = df.index.get_loc(swing_high_idx)
    pullback_days = len(df) - 1 - swing_high_loc

    duration_ok = PULLBACK_MIN_DAYS <= pullback_days <= PULLBACK_MAX_DAYS
    log.gate(f"Pullback duration {pullback_days}d", duration_ok,
             f"target {PULLBACK_MIN_DAYS}-{PULLBACK_MAX_DAYS}d, swing high ${swing_high:.2f}")

    depth = (swing_high - close) / swing_high
    depth_ok = PULLBACK_DEPTH_RANGE[0] <= depth <= PULLBACK_DEPTH_RANGE[1]
    log.gate("Pullback depth", depth_ok,
             f"{depth*100:.1f}% — target "
             f"{PULLBACK_DEPTH_RANGE[0]*100:.0f}-{PULLBACK_DEPTH_RANGE[1]*100:.0f}%")

    advance_start = max(0, swing_high_loc - ADVANCE_WINDOW)
    advance_window = df.iloc[advance_start: swing_high_loc + 1]
    pullback_window = df.iloc[swing_high_loc + 1:]
    have_windows = len(advance_window) >= 5 and len(pullback_window) >= 1

    if have_windows:
        prior_swing_low = float(advance_window["Low"].min())
        pullback_low = float(pullback_window["Low"].min())
        log.gate("Swing low intact", pullback_low >= prior_swing_low,
                 f"pullback low ${pullback_low:.2f} vs prior ${prior_swing_low:.2f}")
    else:
        prior_swing_low = float("nan")
        pullback_low = float("nan")
        log.gate("Swing low intact", False, "insufficient window data")

    # ── Volume & support ───────────────────────────────────────────────────────
    log.section("Volume & support")

    if have_windows:
        avg_vol_adv = float(advance_window["Volume"].mean())
        avg_vol_pb  = float(pullback_window["Volume"].mean())
        vol_contraction = (avg_vol_pb / avg_vol_adv) if avg_vol_adv else float("nan")
        if pd.notna(vol_contraction):
            log.gate("Volume contraction", vol_contraction <= VOL_CONTRACTION_MAX,
                     f"{vol_contraction:.2f} (target ≤{VOL_CONTRACTION_MAX})")
        else:
            log.gate("Volume contraction", False, "no advance volume")
    else:
        vol_contraction = float("nan")
        log.gate("Volume contraction", False, "insufficient window data")

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
        log.gate(f"At {support_name} support", True,
                 f"${support_level:.2f}, {distance_to_support*100:.2f}% above")
    else:
        below = [(n, l) for n, l in candidates.items() if l > 0 and close >= l]
        if below:
            nearest_n, nearest_l = min(below, key=lambda x: (close - x[1]) / close)
            support_name = nearest_n
            support_level = nearest_l
            distance_to_support = (close - nearest_l) / close
            log.gate("At a logical support level", False,
                     f"closest is {nearest_n} at ${nearest_l:.2f}, "
                     f"{distance_to_support*100:.1f}% below price (>{SUPPORT_PROXIMITY_PCT*100:.1f}% limit)")
        else:
            support_name = "none"
            support_level = float("nan")
            distance_to_support = float("nan")
            log.gate("At a logical support level", False,
                     "price is below all support candidates")

    # ── Momentum ───────────────────────────────────────────────────────────────
    log.section("Momentum")

    rsi = float(RSIIndicator(df["Close"], 14).rsi().iloc[-1])
    log.gate("RSI(14) reset", RSI_PULLBACK_RANGE[0] <= rsi <= RSI_PULLBACK_RANGE[1],
             f"{rsi:.1f} — target {RSI_PULLBACK_RANGE[0]}-{RSI_PULLBACK_RANGE[1]}")

    adx = float(ADXIndicator(df["High"], df["Low"], df["Close"], 14).adx().iloc[-1])
    log.gate("ADX(14) trend strength", adx >= ADX_MIN_TREND,
             f"{adx:.1f} — min {ADX_MIN_TREND}")

    # ── Filters ────────────────────────────────────────────────────────────────
    log.section("Filters")

    # (a) Earnings: skip when unknown; gate when known
    if ctx.days_to_earnings is None:
        log.skip("Earnings clear", "no earnings data")
    else:
        log.gate("Earnings clear", ctx.days_to_earnings > EARNINGS_BUFFER_DAYS,
                 f"{ctx.days_to_earnings}d away")

    spy_df = ctx.market_data.get("SPY")
    rs = _rs_metrics(df, spy_df)
    log.gate("Relative strength vs SPY", rs["rs_strength"] >= RS_MIN,
             f"60d RS={rs['rs_strength']:.2f}"
             f"{', at new high' if rs['rs_at_new_high'] else ''}")

    # (b) Sector: skip when sector unknown or ETF data unavailable
    sector = ctx.quality.sector
    sector_outperforming = False
    if sector is None or sector not in SECTOR_ETF_MAP:
        log.skip("Sector strength", "sector unknown")
        sector_info = {"sector_etf": None, "sector_above_50ma": False,
                       "sector_outperforming": False}
    else:
        etf = SECTOR_ETF_MAP[sector]
        etf_df = ctx.market_data.get(etf)
        if etf_df is None or len(etf_df) < 50:
            log.skip("Sector strength", "ETF data unavailable")
            sector_info = {"sector_etf": etf, "sector_above_50ma": False,
                           "sector_outperforming": False}
        else:
            sector_info = _sector_strength(sector, ctx.market_data)
            log.gate(f"Sector ({sector_info['sector_etf']}) above 50MA",
                     sector_info["sector_above_50ma"],
                     f"vs SPY={'leading' if sector_info['sector_outperforming'] else 'lagging'}")
            sector_outperforming = sector_info["sector_outperforming"]

    # (c) Weekly: skip when unavailable or too short (<35 bars for MA+lookback)
    weekly_above_30ma = False
    weekly_30ma_rising = False
    if ctx.weekly is None or len(ctx.weekly) < 35:
        log.skip("Weekly above 30-MA", "insufficient weekly data")
    else:
        sma_w = ctx.weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
        weekly_above_30ma = bool(ctx.weekly["Close"].iloc[-1] > sma_w.iloc[-1])
        weekly_30ma_rising = bool(sma_w.iloc[-1] > sma_w.iloc[-5])
        log.gate("Weekly above 30-MA", weekly_above_30ma,
                 f"30MA rising={weekly_30ma_rising}")

    avg_dollar_vol = float((df["Close"] * df["Volume"]).rolling(50).mean().iloc[-1])
    log.gate("Liquidity", avg_dollar_vol >= DOLLAR_VOL_MIN,
             f"${avg_dollar_vol/1e6:.1f}M avg daily $-vol")

    mc = ctx.quality.market_cap
    # (d) Market cap: skip when unknown
    if mc is None:
        log.skip("Market cap in range", "unknown")
    else:
        log.gate("Market cap in range", MARKET_CAP_RANGE[0] <= mc <= MARKET_CAP_RANGE[1],
                 f"${mc/1e9:.2f}B")

    # Profitable is always a hard gate — profitable=False is the conservative default
    # when data is unavailable (not skipped; missing data should not unlock a setup)
    log.gate("Profitable", bool(ctx.quality.profitable))

    de = ctx.quality.debt_equity
    # (d) D/E: skip when unknown
    if de is None:
        log.skip("Debt/equity acceptable", "unknown")
    else:
        log.gate("Debt/equity acceptable", de <= DEBT_EQUITY_MAX, f"{de:.1f}")

    # ── Bonus signals ──────────────────────────────────────────────────────────
    log.section("Bonus signals")
    trigger = _bullish_reversal_candle(df)
    pp = _pocket_pivot(df)
    nr7 = _nr7(df)
    log.bonus("Bullish reversal candle", trigger)
    log.bonus("Pocket Pivot trigger", pp)
    log.bonus("NR7 contraction", nr7)
    log.bonus("RS line at 60d high", rs["rs_at_new_high"])
    log.bonus("Sector outperforming SPY", sector_outperforming)
    log.bonus("Weekly 30-MA rising", weekly_30ma_rising)
    log.bonus("200-MA in sweet spot", in_sweet_spot)

    # ── Score ──────────────────────────────────────────────────────────────────
    def _safe(v: float, fallback: float = 0.0) -> float:
        return fallback if pd.isna(v) else float(v)

    optimal_depth = 0.08
    vc_safe   = _safe(vol_contraction, 1.0)
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
        + (10 if sector_outperforming else 0)
        + (10 if weekly_30ma_rising else 0)
        + (10 if in_sweet_spot else 0)
        + (adx - 20) * 0.5
    )

    if verbose:
        if log.qualified:
            print(f"\n  VERDICT: ✓ QUALIFIES — score {score:.1f} "
                  f"({log.gates_passed}/{log.gates_total} gates passed)\n")
        else:
            print(f"\n  VERDICT: ✗ DOES NOT QUALIFY — "
                  f"{log.gates_passed}/{log.gates_total} gates passed")
            print(f"  Failed gates: {', '.join(log.failed_gates)}")
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
        sector                  = sector,
        sector_etf              = sector_info.get("sector_etf"),
        sector_outperforming    = sector_outperforming,
        weekly_above_30ma       = weekly_above_30ma,
        weekly_30ma_rising      = weekly_30ma_rising,
        days_to_earnings        = ctx.days_to_earnings,
        market_cap              = mc if mc is not None else float("nan"),
        profitable              = bool(ctx.quality.profitable),
        debt_equity             = de,
        qualified               = log.qualified,
        failed_gates            = log.failed_gates,
        skipped_gates           = log.skipped_gates,
        gates_passed            = log.gates_passed,
        gates_total             = log.gates_total,
        score                   = round(score, 1),
        as_of                   = ctx.as_of,
    )
