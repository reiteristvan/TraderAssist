"""E2/E4 — GateLog, EvalContext, QualityInfo, shared indicators, context factory, scan loop.

See CLAUDE.md EPIC E2/E3/E4.
"""
from __future__ import annotations

import dataclasses
import math
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

# Industry-level ETF proxy map (industryKey slug -> ETF ticker).
# Two-tier resolution: check this map first; fall back to SECTOR_ETF_MAP.
# Sector-level fallback entries (e.g. 'oil-gas-integrated' -> 'XLE') are
# explicit entries here — the map is the single source of truth (D-01, D-03).
INDUSTRY_ETF_MAP: dict[str, str] = {
    # ── Technology ────────────────────────────────────────────────────────
    "semiconductors":                    "XSD",
    "semiconductor-equipment-materials": "XSD",
    "software-infrastructure":           "XSW",
    "software-application":              "XSW",
    "information-technology-services":   "XSW",
    # ── Healthcare ────────────────────────────────────────────────────────
    "biotechnology":                       "XBI",
    "drug-manufacturers-general":          "XPH",
    "drug-manufacturers-specialty-generic":"XPH",
    "medical-devices":                     "XHE",
    "medical-instruments-supplies":        "XHE",
    "healthcare-plans":                    "XHS",
    "medical-care-facilities":             "XHS",
    # ── Financial Services ────────────────────────────────────────────────
    "banks-regional":                    "KRE",
    "banks-diversified":                 "KBE",
    "insurance-property-casualty":       "KIE",
    "insurance-life":                    "KIE",
    "insurance-diversified":             "KIE",
    "capital-markets":                   "KCE",
    "financial-data-stock-exchanges":    "KCE",
    # ── Consumer Cyclical ─────────────────────────────────────────────────
    "residential-construction": "XHB",
    "specialty-retail":         "XRT",
    "department-stores":        "XRT",
    "internet-retail":          "XRT",
    # ── Industrials ───────────────────────────────────────────────────────
    "aerospace-defense": "XAR",
    # ── Energy ────────────────────────────────────────────────────────────
    "oil-gas-e-p":               "XOP",
    "oil-gas-integrated":        "XLE",   # sector-fallback encoded in map (D-03)
    "oil-gas-equipment-services":"XES",
    "oil-gas-midstream":         "XLE",   # sector-fallback encoded in map (D-03)
    # ── Basic Materials ───────────────────────────────────────────────────
    "gold":               "GDX",
    "specialty-chemicals":"XLB",          # sector-fallback encoded in map (D-03)
    "steel":              "XME",
    "copper":             "XME",
    "aluminum":           "XME",
}


def resolve_industry_etf(industry_key: Optional[str], sector: Optional[str]) -> Optional[str]:
    """Return the best ETF proxy for a stock's industry/sector classification.

    Two-step lookup chain (D-07):
    1. Direct hit in INDUSTRY_ETF_MAP.
    2. Fall through to SECTOR_ETF_MAP keyed by sector.

    Special case (D-06): if industry_key is None, return None immediately —
    no sector fallback is applied when the industry classification is absent.
    """
    if industry_key is None:
        return None
    etf = INDUSTRY_ETF_MAP.get(industry_key)
    if etf is not None:
        return etf
    return SECTOR_ETF_MAP.get(sector)


# ── GateLog (E2.1) ────────────────────────────────────────────────────────────

class GateLog:
    """Non-short-circuit gate accumulator for strategy evaluation."""

    def __init__(self, ticker: str, verbose: bool = False) -> None:
        self._verbose = verbose
        self._failed: list[str] = []
        self._skipped: list[str] = []
        self._total = 0
        self._log: list[dict] = []   # ordered record of every gate/skip/bonus call
        if verbose:
            print(f"\n=== {ticker} ===")

    def section(self, title: str) -> None:
        self._log.append({"name": title, "status": "section", "detail": ""})
        if self._verbose:
            print(f"{title}:")

    def gate(self, name: str, passed: bool, detail: str = "") -> bool:
        self._total += 1
        if not passed:
            self._failed.append(name)
        self._log.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
        if self._verbose:
            mark = "✓" if passed else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")
        return passed

    def skip(self, name: str, reason: str) -> None:
        self._skipped.append(name)
        self._log.append({"name": name, "status": "skip", "detail": reason})
        if self._verbose:
            print(f"  – {name} (skipped: {reason})")

    def bonus(self, name: str, present: bool, detail: str = "") -> None:
        self._log.append({"name": name, "status": "bonus_pass" if present else "bonus_fail", "detail": detail})
        if self._verbose:
            mark = "✓" if present else "✗"
            d = f" ({detail})" if detail else ""
            print(f"  {mark} {name}{d}")

    def to_detail_list(self) -> list[dict]:
        """Ordered list of {name, status, detail} for every gate/skip/bonus."""
        return list(self._log)

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
    industry: Optional[str] = None       # human-readable display name (D-04)
    industry_key: Optional[str] = None   # industryKey slug for ETF lookup (D-04, D-05)


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


# ── E4.3 helpers (for confidence scoring) ────────────────────────────────────

def _sma_slope(df: pd.DataFrame, period: int = 50, lookback: int = 5) -> float:
    """SMA slope as % change over `lookback` bars (verbatim swing_scanner SMA_50_Slope)."""
    sma = df["Close"].rolling(period).mean()
    cur = sma.iloc[-1]
    prev = sma.iloc[-1 - lookback]
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return 0.0
    return float((cur - prev) / prev * 100)


def _macd_bullish(df: pd.DataFrame) -> bool:
    """True when MACD line is above signal line (MACD histogram > 0)."""
    from ta.trend import MACD
    macd = MACD(df["Close"], window_slow=26, window_fast=12, window_sign=9)
    hist = macd.macd_diff().iloc[-1]
    return bool(not pd.isna(hist) and hist > 0)


# ── E4.4 — position sizing ────────────────────────────────────────────────────

@dataclass
class SizeInfo:
    shares: int
    position_value: float
    risk_amount: float
    capped: bool           # True when max-position cap bound
    zero_reason: str       # non-empty when shares==0


def position_size(
    entry: float,
    stop: float,
    account_size: float = 6500.0,
    risk_pct: float = 0.01,
    max_position: float = 650.0,
) -> SizeInfo:
    """Risk-based position sizing.

    shares = floor(account_size * risk_pct / (entry - stop)),
    capped at floor(max_position / entry).
    entry <= stop → 0 shares with message, no ZeroDivisionError.
    """
    if entry <= stop:
        return SizeInfo(shares=0, position_value=0.0, risk_amount=0.0,
                        capped=False, zero_reason="entry <= stop: invalid stop level")
    risk_per_share = entry - stop
    raw_shares = int(account_size * risk_pct / risk_per_share)
    cap_shares = int(max_position / entry) if entry > 0 else 0
    capped = raw_shares > cap_shares
    shares = min(raw_shares, cap_shares)
    return SizeInfo(
        shares=shares,
        position_value=round(shares * entry, 2),
        risk_amount=round(shares * risk_per_share, 2),
        capped=capped,
        zero_reason="",
    )


# ── E4.5 — calendar (market session) ─────────────────────────────────────────

def last_closed_session(now=None) -> date:
    """Return the most recent fully-closed NYSE trading session.

    Pass a tz-aware datetime for `now`, or None to use the current time.
    Handles holidays and half-days via pandas_market_calendars XNYS.
    Schedule close times are in UTC; comparison is done in UTC.
    """
    import pandas_market_calendars as mcal
    import pytz
    from datetime import timedelta, datetime as _dt

    et = pytz.timezone("America/New_York")
    utc = pytz.utc

    if now is None:
        now_dt = _dt.now(tz=et)
    elif isinstance(now, _dt):
        now_dt = now.astimezone(et) if now.tzinfo else et.localize(now)
    else:
        # bare date — treat as start of that day in ET (before market open)
        now_dt = et.localize(_dt(now.year, now.month, now.day, 0, 0))

    today = now_dt.date()
    now_utc = now_dt.astimezone(utc)

    cal = mcal.get_calendar("XNYS")
    sched = cal.schedule(start_date=str(today - timedelta(days=14)), end_date=str(today))
    if sched.empty:
        return today - timedelta(days=1)

    # Walk backwards; market_close is a UTC pd.Timestamp
    for idx in reversed(range(len(sched))):
        row = sched.iloc[idx]
        session_date = row.name.date()
        close_ts = row["market_close"]
        if hasattr(close_ts, "tzinfo") and close_ts.tzinfo is None:
            close_ts = utc.localize(close_ts.to_pydatetime())
        elif hasattr(close_ts, "to_pydatetime"):
            close_ts = close_ts.to_pydatetime().astimezone(utc)
        if now_utc >= close_ts:
            return session_date

    return sched.index[0].date()


# ── Context factory (E2.4) ────────────────────────────────────────────────────

def _make_quality_info(ticker: str) -> QualityInfo:
    import time, random, logging as _logging
    _qlog = _logging.getLogger("scanner.quality")
    profitable = False
    market_cap = None
    debt_equity = None
    sector = None
    float_shares = None
    info: dict = {}
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info or {}
            # yfinance returns a near-empty dict (just {quoteType, ...}) when
            # rate-limited; treat that as a failed fetch and retry.
            if info.get("operatingIncome") is None and info.get("forwardEps") is None \
                    and info.get("marketCap") is None and attempt < 2:
                raise ValueError("empty info — likely rate-limited")
            break
        except Exception as exc:
            wait = 2 ** attempt + random.uniform(0, 1)
            _qlog.warning("quality fetch %s attempt %d failed (%s) — retry in %.1fs",
                          ticker, attempt + 1, exc, wait)
            time.sleep(wait)
    op_inc  = info.get("operatingIncome") or 0
    fwd_eps = info.get("forwardEps") or 0
    if op_inc or fwd_eps:
        profitable = (op_inc > 0) or (fwd_eps > 0)
    # profitable stays False (conservative default) when info unfetchable — intentional.
    market_cap   = info.get("marketCap")
    debt_equity  = info.get("debtToEquity")
    sector       = info.get("sector")
    float_shares = info.get("floatShares")
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

    as_of=None (live): uses last date of cached history; fetches earnings via yfinance.calendar.
    Historical as_of: frames sliced to that date; days_to_earnings via earnings_store (E5.3).
    """
    from scanner.data_store import get_history, get_weekly, get_market_data
    from scanner.earnings_store import days_to_earnings as _earn_days_hist
    df = get_history(ticker, end=as_of)
    if df is None:
        return None
    as_of_date = as_of if as_of is not None else df.index[-1].date()
    market_data = get_market_data(end=as_of_date)
    weekly = get_weekly(ticker, end=as_of_date)
    quality = _make_quality_info(ticker)
    if as_of is None:
        days = _days_to_earnings(ticker, as_of_date)
    else:
        days = _earn_days_hist(ticker, as_of_date)
    return EvalContext(
        as_of=as_of_date, market_data=market_data,
        weekly=weekly, quality=quality, days_to_earnings=days,
    )


def make_contexts(tickers: Iterable[str],
                  as_of: date | None = None,
                  quality_pause: float = 0.15) -> dict[str, EvalContext]:
    """Batch context builder — loads market data once.

    quality_pause: seconds between yfinance .info calls to avoid rate-limiting.
    Set to 0 in tests (monkeypatched) or when running against a local cache.
    """
    import time
    from scanner.data_store import get_history, get_weekly, get_market_data
    from scanner.earnings_store import days_to_earnings as _earn_days_hist
    market_data = get_market_data(end=as_of)
    result: dict[str, EvalContext] = {}
    for ticker in tickers:
        df = get_history(ticker, end=as_of)
        if df is None:
            continue
        as_of_date = as_of if as_of is not None else df.index[-1].date()
        weekly = get_weekly(ticker, end=as_of_date)
        if quality_pause > 0:
            time.sleep(quality_pause)
        quality = _make_quality_info(ticker)
        if as_of is None:
            days = _days_to_earnings(ticker, as_of_date)
        else:
            days = _earn_days_hist(ticker, as_of_date)
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
    attach_risk: bool = True,
    compute_conf: bool = True,
    account_size: float = 6500.0,
    risk_pct: float = 0.01,
    max_position: float = 650.0,
) -> pd.DataFrame:
    """Evaluate each ticker with strategy_fn and return a sorted DataFrame.

    Live mode (as_of=None): refreshes universe cache first.
    history_provider: callable(ticker, end) -> df|None; defaults to data_store.get_history.
    No sleeps in this loop — they live in refresh_universe.
    attach_risk: call targets.attach_risk() on every result.
    compute_conf: compute confidence rating and ath_zone column.
    """
    from dataclasses import asdict
    from scanner.data_store import get_history, refresh_universe
    from scanner.regime import market_regime as _market_regime, ath_zone as _ath_zone
    from scanner.regime import compute_confidence as _compute_confidence
    import scanner.targets as _targets

    if history_provider is None:
        history_provider = lambda t, end=None: get_history(t, end=end)

    tickers_list = list(tickers)
    n_requested = len(tickers_list)

    if as_of is None:
        print(f"  Refreshing {n_requested} ticker(s)...", flush=True)
        report = refresh_universe(tickers_list, pause=0.2)
        parts = [f"{len(report.succeeded)} ok"]
        if report.invalidated:
            parts.append(f"{len(report.invalidated)} re-fetched")
        if report.failed:
            parts.append(f"{len(report.failed)} failed")
        print(f"\r  Refresh complete: {', '.join(parts)}" + " " * 30)
    else:
        print(f"  Using cached data (as of {as_of})", flush=True)

    print(f"  Building evaluation contexts...", flush=True)
    contexts = make_contexts(tickers_list, as_of=as_of)
    n = len(contexts)
    skipped = n_requested - n
    suffix = f" ({skipped} skipped — insufficient history)" if skipped else ""
    print(f"  {n} contexts ready{suffix}")

    rows = []
    qualified_count = 0

    for i, (ticker, ctx) in enumerate(contexts.items(), 1):
        if n > 1 and not verbose:
            print(f"  [{i}/{n}] {ticker:<8}  {qualified_count} qualified so far", end="\r", flush=True)
        df = history_provider(ticker, end=as_of)
        if df is None:
            continue
        result = strategy_fn(ticker, df, ctx, verbose=verbose)
        if result is None:
            continue
        if getattr(result, "qualified", False):
            qualified_count += 1

        if attach_risk:
            try:
                result = _targets.attach_risk(result, df)
            except Exception:
                pass

        zone_label: Optional[str] = None
        if compute_conf and result.suggested_stop is not None and result.risk_reward is not None:
            try:
                from scanner.strategies.pullback import PullbackResult
                regime = _market_regime(ctx.market_data)
                _, _, zone_label = _ath_zone(ticker, result.close, end=ctx.as_of)
                obstacles, _ = _targets.count_resistance_obstacles(
                    df, result.close,
                    result.suggested_target if result.suggested_target else result.close * 1.10
                )
                sma_slope_val = _sma_slope(df)
                macd_val = _macd_bullish(df)
                weekly_aligned = False
                if isinstance(result, PullbackResult):
                    weekly_aligned = result.weekly_above_30ma
                elif ctx.weekly is not None and len(ctx.weekly) >= 35:
                    wma = ctx.weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
                    weekly_aligned = bool(ctx.weekly["Close"].iloc[-1] > wma.iloc[-1])
                conf = _compute_confidence(
                    score=result.score,
                    adx=result.adx,
                    weekly_aligned=weekly_aligned,
                    market_regime_str=regime,
                    obstacles=obstacles,
                    rr=result.risk_reward,
                    sma_slope=sma_slope_val,
                    macd_bullish=macd_val,
                    ath_zone_label=zone_label,
                )
                result = dataclasses.replace(result, confidence=conf)
            except Exception:
                pass

        row = asdict(result)
        row["ath_zone"] = zone_label
        rows.append(row)

    if n > 1 and not verbose:
        print(f"  [{n}/{n}] Done.  {qualified_count} qualified out of {n} evaluated." + " " * 20)

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    if not capture_all and "qualified" in df_out.columns:
        df_out = df_out[df_out["qualified"]]
    if "qualified" in df_out.columns and "score" in df_out.columns:
        df_out = df_out.sort_values(["qualified", "score"], ascending=[False, False])
    return df_out.reset_index(drop=True)
