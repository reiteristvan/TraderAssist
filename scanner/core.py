"""E2 — GateLog, EvalContext, QualityInfo, shared indicators, context factory, scan loop.

See CLAUDE.md EPIC E2/E3.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Thresholds (E2.3) ─────────────────────────────────────────────────────────

TREND_LOOKBACK_HIGH   = 60
MA200_DIST_MIN        = 0.03
MA200_DIST_MAX        = 0.30
MA200_SWEET_SPOT      = (0.05, 0.25)

SWING_HIGH_LOOKBACK   = 40
ADVANCE_WINDOW        = 30
PULLBACK_DEPTH_RANGE  = (0.04, 0.18)
PULLBACK_MIN_DAYS     = 3
PULLBACK_MAX_DAYS     = 20
SUPPORT_PROXIMITY_PCT = 0.025

VOL_CONTRACTION_MAX   = 0.85

RSI_PULLBACK_RANGE    = (40, 60)
ADX_MIN_TREND         = 20

MARKET_CAP_RANGE      = (3e8, 5e9)
DOLLAR_VOL_MIN        = 5e6
DEBT_EQUITY_MAX       = 150.0

RS_LOOKBACK           = 60
RS_MIN                = 0.90

EARNINGS_BUFFER_DAYS  = 7   # single definition — imported by both strategies

POCKET_PIVOT_LOOKBACK = 10
WEEKLY_MA_PERIOD      = 30

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

# ── GateLog (E2.1) ────────────────────────────────────────────────────────────

class GateLog:
    """Non-short-circuit gate accumulator for strategy evaluation."""

    def __init__(self, ticker: str, verbose: bool = False) -> None:
        self._verbose = verbose
        self._failed: list[str] = []
        self._skipped: list[str] = []
        self._total = 0
        if verbose:
            print(f"\n=== {ticker} ===")

    def section(self, title: str) -> None:
        if self._verbose:
            print(f"{title}:")

    def gate(self, name: str, passed: bool, detail: str = "") -> bool:
        self._total += 1
        if not passed:
            self._failed.append(name)
        if self._verbose:
            mark = "✓" if passed else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")
        return passed

    def skip(self, name: str, reason: str) -> None:
        self._skipped.append(name)
        if self._verbose:
            print(f"  – {name} (skipped: {reason})")

    def bonus(self, name: str, present: bool, detail: str = "") -> None:
        if self._verbose:
            mark = "✓" if present else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")

    @property
    def failed_gates(self) -> list[str]:
        return list(self._failed)

    @property
    def skipped_gates(self) -> list[str]:
        return list(self._skipped)

    @property
    def gates_total(self) -> int:
        return self._total

    @property
    def gates_passed(self) -> int:
        return self._total - len(self._failed)

    @property
    def qualified(self) -> bool:
        return len(self._failed) == 0


# ── Dataclasses (E2.2) ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QualityInfo:
    profitable: bool
    market_cap: Optional[float]
    debt_equity: Optional[float]
    sector: Optional[str]
    float_shares: Optional[float]


@dataclass(frozen=True)
class EvalContext:
    as_of: date
    market_data: dict[str, pd.DataFrame]
    weekly: Optional[pd.DataFrame]      # weekly OHLCV; None = unavailable
    quality: QualityInfo
    days_to_earnings: Optional[int]     # None = UNKNOWN


# ── Helper indicators (E2.3) ──────────────────────────────────────────────────

def _bullish_reversal_candle(df: pd.DataFrame) -> bool:
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
    if len(df) < 7:
        return False
    ranges = df["High"] - df["Low"]
    return float(ranges.iloc[-1]) == float(ranges.iloc[-7:].min())


def _rs_metrics(stock_df: pd.DataFrame, spy_df: Optional[pd.DataFrame],
                lookback: int = RS_LOOKBACK) -> dict:
    default = {"rs_strength": 1.0, "rs_at_new_high": False}
    if spy_df is None or len(spy_df) < lookback or len(stock_df) < lookback:
        return default
    aligned = pd.DataFrame({"stock": stock_df["Close"], "spy": spy_df["Close"]}).dropna()
    if len(aligned) < lookback:
        return default
    rs_line = aligned["stock"] / aligned["spy"]
    rs_strength = float(rs_line.iloc[-1] / rs_line.iloc[-lookback])
    rs_high = float(rs_line.iloc[-lookback:].max())
    rs_at_high = float(rs_line.iloc[-1]) >= rs_high * 0.99
    return {"rs_strength": rs_strength, "rs_at_new_high": bool(rs_at_high)}


def _sector_strength(sector: Optional[str], market_data: dict) -> dict:
    out = {"sector_etf": None, "sector_above_50ma": False, "sector_outperforming": False}
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


# ── Context factory (E2.4) ────────────────────────────────────────────────────

def _make_quality_info(ticker: str) -> QualityInfo:
    profitable = False
    market_cap = None
    debt_equity = None
    sector = None
    float_shares = None
    try:
        info = yf.Ticker(ticker).info or {}
        op_inc  = info.get("operatingIncome") or 0
        fwd_eps = info.get("forwardEps") or 0
        profitable   = (op_inc > 0) or (fwd_eps > 0)
        market_cap   = info.get("marketCap")
        debt_equity  = info.get("debtToEquity")
        sector       = info.get("sector")
        float_shares = info.get("floatShares")
    except Exception:
        pass
    return QualityInfo(
        profitable=profitable, market_cap=market_cap, debt_equity=debt_equity,
        sector=sector, float_shares=float_shares,
    )


def _days_to_earnings(ticker: str, as_of: date) -> Optional[int]:
    """Days to next earnings from as_of. Returns None if unknown."""
    try:
        cal = yf.Ticker(ticker).calendar
        earnings_date = None
        if cal is None:
            return None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
        elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
            earnings_date = cal.loc["Earnings Date"].iloc[0]
        if isinstance(earnings_date, list):
            earnings_date = earnings_date[0] if earnings_date else None
        if earnings_date is None:
            return None
        if isinstance(earnings_date, str):
            earnings_date = pd.Timestamp(earnings_date)
        if hasattr(earnings_date, "to_pydatetime"):
            earnings_date = pd.Timestamp(earnings_date)
        days = (earnings_date.normalize() - pd.Timestamp(as_of).normalize()).days
        return max(0, int(days))
    except Exception:
        return None


def make_context(ticker: str, as_of: date | None = None) -> Optional[EvalContext]:
    """Build EvalContext for one ticker.

    as_of=None (live): uses last date of cached history; fetches earnings.
    Historical as_of: frames sliced to that date; days_to_earnings=None (E5.3).
    """
    from scanner.data_store import get_history, get_weekly, get_market_data
    df = get_history(ticker, end=as_of)
    if df is None:
        return None
    as_of_date = as_of if as_of is not None else df.index[-1].date()
    market_data = get_market_data(end=as_of_date)
    weekly = get_weekly(ticker, end=as_of_date)
    quality = _make_quality_info(ticker)
    days = _days_to_earnings(ticker, as_of_date) if as_of is None else None
    return EvalContext(
        as_of=as_of_date, market_data=market_data,
        weekly=weekly, quality=quality, days_to_earnings=days,
    )


def make_contexts(tickers: Iterable[str],
                  as_of: date | None = None) -> dict[str, EvalContext]:
    """Batch context builder — loads market data once."""
    from scanner.data_store import get_history, get_weekly, get_market_data
    market_data = get_market_data(end=as_of)
    result: dict[str, EvalContext] = {}
    for ticker in tickers:
        df = get_history(ticker, end=as_of)
        if df is None:
            continue
        as_of_date = as_of if as_of is not None else df.index[-1].date()
        weekly = get_weekly(ticker, end=as_of_date)
        quality = _make_quality_info(ticker)
        days = _days_to_earnings(ticker, as_of_date) if as_of is None else None
        result[ticker] = EvalContext(
            as_of=as_of_date, market_data=market_data,
            weekly=weekly, quality=quality, days_to_earnings=days,
        )
    return result


# ── Shared scan loop (E3.2) ───────────────────────────────────────────────────

def run_scan(
    tickers: Iterable[str],
    strategy_fn,
    as_of: date | None = None,
    verbose: bool = False,
    capture_all: bool = True,
    history_provider=None,
) -> pd.DataFrame:
    """Evaluate each ticker with strategy_fn and return a sorted DataFrame.

    Live mode (as_of=None): refreshes universe cache first.
    history_provider: callable(ticker, end) -> df|None; defaults to data_store.get_history.
    No sleeps in this loop — they live in refresh_universe.
    """
    from dataclasses import asdict
    from scanner.data_store import get_history, refresh_universe

    if history_provider is None:
        history_provider = lambda t, end=None: get_history(t, end=end)

    tickers_list = list(tickers)

    if as_of is None:
        refresh_universe(tickers_list, pause=0.2)

    contexts = make_contexts(tickers_list, as_of=as_of)
    n = len(contexts)
    rows = []

    for i, (ticker, ctx) in enumerate(contexts.items(), 1):
        if n > 1 and not verbose:
            print(f"[{i}/{n}] {ticker}", end="\r")
        df = history_provider(ticker, end=as_of)
        if df is None:
            continue
        result = strategy_fn(ticker, df, ctx, verbose=verbose)
        if result is not None:
            rows.append(asdict(result))

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    if not capture_all and "qualified" in df_out.columns:
        df_out = df_out[df_out["qualified"]]
    if "qualified" in df_out.columns and "score" in df_out.columns:
        df_out = df_out.sort_values(["qualified", "score"], ascending=[False, False])
    return df_out.reset_index(drop=True)
