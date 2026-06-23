"""E3.1/E3.3 — Full (non-short-circuit) breakout evaluate() on GateLog/EvalContext.

Gate-for-gate parity with breakout_filter._evaluate, plus E3.3 earnings gate.
Zero network I/O. See CLAUDE.md EPIC E3.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, SMAIndicator
from ta.volatility import BollingerBands

from scanner.core import (
    ADX_MIN_TREND,
    DEBT_EQUITY_MAX,
    DOLLAR_VOL_MIN,
    EARNINGS_BUFFER_DAYS,
    MARKET_CAP_RANGE,
    EvalContext,
    GateLog,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Breakout-specific thresholds (verbatim from breakout_filter.py)
NEAR_HIGH_PCT    = 0.97
CONSOL_LOOKBACK  = 20
VOL_RATIO_MIN    = 1.5
RSI_RANGE        = (55, 75)
ADX_MIN          = 20
BB_WIDTH_PCTILE  = 0.40


@dataclass
class BreakoutResult:
    # Original fields — kept in same positions for golden-master compatibility
    ticker: str
    close: float
    pct_to_52w_high: float
    vol_ratio: float
    rsi: float
    adx: float
    bb_width: float
    market_cap: float
    profitable: bool
    debt_equity: Optional[float]
    score: float
    # New fields (E3.1/E3.3)
    qualified: bool
    failed_gates: list[str]
    skipped_gates: list[str]
    gates_passed: int
    gates_total: int
    as_of: date
    days_to_earnings: Optional[int]
    # E4.1 — populated by attach_risk(); None until then
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    risk_reward: Optional[float] = None
    atr: Optional[float] = None
    # E4.3 — populated by run_scan(); None until then
    confidence: Optional[str] = None
    # E12.2a — ordered gate log for UI diagnosis view; JSON-serialized when stored
    gate_detail: list = field(default_factory=list)


def evaluate(ticker: str, df: pd.DataFrame, ctx: EvalContext,
             verbose: bool = False) -> BreakoutResult:
    """Evaluate a breakout setup. Pure — no network I/O, no wall clock."""
    log = GateLog(ticker, verbose=verbose)
    close = float(df["Close"].iloc[-1])

    # ── Trend & momentum ───────────────────────────────────────────────────────
    log.section("Trend & momentum")

    high_52w = df["High"].rolling(252, min_periods=200).max().iloc[-1]
    pct_to_high = close / float(high_52w)
    log.gate("Near 52w high", pct_to_high >= NEAR_HIGH_PCT,
             f"{pct_to_high*100:.2f}% of 52w high")

    consol_high = float(df["High"].iloc[-CONSOL_LOOKBACK - 1: -1].max())
    log.gate("Consolidation breakout", close >= consol_high,
             f"close ${close:.2f} vs consol high ${consol_high:.2f}")

    vol_sma50 = df["Volume"].rolling(50).mean().iloc[-1]
    vol_ratio = float(df["Volume"].iloc[-1] / vol_sma50) if vol_sma50 else 0.0
    log.gate("Volume confirmation", vol_ratio >= VOL_RATIO_MIN,
             f"{vol_ratio:.2f}x SMA50 volume (min {VOL_RATIO_MIN}x)")

    sma50  = float(SMAIndicator(df["Close"], 50).sma_indicator().iloc[-1])
    sma200 = float(SMAIndicator(df["Close"], 200).sma_indicator().iloc[-1])
    log.gate("Trend alignment", close > sma50 > sma200,
             f"close {close:.2f} > SMA50 {sma50:.2f} > SMA200 {sma200:.2f}")

    rsi = float(RSIIndicator(df["Close"], 14).rsi().iloc[-1])
    log.gate("RSI in breakout range", RSI_RANGE[0] <= rsi <= RSI_RANGE[1],
             f"{rsi:.1f} (target {RSI_RANGE[0]}-{RSI_RANGE[1]})")

    adx = float(ADXIndicator(df["High"], df["Low"], df["Close"], 14).adx().iloc[-1])
    log.gate("ADX trend strength", adx >= ADX_MIN,
             f"{adx:.1f} (min {ADX_MIN})")

    # ── Volatility ─────────────────────────────────────────────────────────────
    log.section("Volatility")

    bb = BollingerBands(df["Close"], 20, 2)
    bb_width_s = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    bb_width_now = float(bb_width_s.iloc[-1])
    bb_threshold = float(bb_width_s.iloc[-60:].quantile(BB_WIDTH_PCTILE))
    log.gate("BB squeeze", bb_width_now <= bb_threshold,
             f"width {bb_width_now:.4f} vs {BB_WIDTH_PCTILE*100:.0f}th pctile {bb_threshold:.4f}")

    # ── Filters ────────────────────────────────────────────────────────────────
    log.section("Filters")

    avg_dollar_vol = float((df["Close"] * df["Volume"]).rolling(50).mean().iloc[-1])
    log.gate("Liquidity", avg_dollar_vol >= DOLLAR_VOL_MIN,
             f"${avg_dollar_vol/1e6:.1f}M avg daily $-vol")

    # E3.3: earnings gate — skip when unknown, gate when known
    if ctx.days_to_earnings is None:
        log.skip("Earnings clear", "no earnings data")
    else:
        log.gate("Earnings clear", ctx.days_to_earnings > EARNINGS_BUFFER_DAYS,
                 f"{ctx.days_to_earnings}d away")

    mc = ctx.quality.market_cap
    if mc is None:
        log.skip("Market cap in range", "unknown")
    else:
        log.gate("Market cap in range", MARKET_CAP_RANGE[0] <= mc <= MARKET_CAP_RANGE[1],
                 f"${mc/1e9:.2f}B")

    # Profitable is always a hard gate
    log.gate("Profitable", bool(ctx.quality.profitable))

    de = ctx.quality.debt_equity
    if de is None:
        log.skip("Debt/equity acceptable", "unknown")
    else:
        log.gate("Debt/equity acceptable", de <= DEBT_EQUITY_MAX, f"{de:.1f}")

    # ── Score (verbatim from breakout_filter lines 148-153) ───────────────────
    score = (
        (vol_ratio - 1.0) * 30
        + (pct_to_high - NEAR_HIGH_PCT) * 400
        + (adx - 20) * 1.0
        + (10 if ctx.quality.profitable else 0)
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

    return BreakoutResult(
        ticker          = ticker,
        close           = round(close, 2),
        pct_to_52w_high = round(pct_to_high * 100, 2),
        vol_ratio       = round(vol_ratio, 2),
        rsi             = round(rsi, 1),
        adx             = round(adx, 1),
        bb_width        = round(bb_width_now, 4),
        market_cap      = mc if mc is not None else float("nan"),
        profitable      = bool(ctx.quality.profitable),
        debt_equity     = de,
        score           = round(score, 1),
        qualified       = log.qualified,
        failed_gates    = log.failed_gates,
        skipped_gates   = log.skipped_gates,
        gates_passed    = log.gates_passed,
        gates_total     = log.gates_total,
        as_of           = ctx.as_of,
        days_to_earnings = ctx.days_to_earnings,
        gate_detail     = log.to_detail_list(),
    )
