"""E1 — Parquet-cached OHLCV. The ONLY module that imports yfinance for prices.

Replaces pullback_filter._fetch_history/prefetch_market_data, breakout_filter._history,
and swing_scanner.fetch_data/fetch_ath. See CLAUDE.md EPIC E1.

Index convention: tz-naive daily DatetimeIndex (midnight). yfinance tz-aware
timestamps are stripped at write time.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

_log = logging.getLogger("scanner.data")

_CACHE_DIR = Path("data/ohlcv")
_MIN_ROWS = 220
_MARKET_SYMBOLS = [
    "SPY", "XLK", "XLF", "XLV", "XLY", "XLC",
    "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB",
]


# ── retry wrapper ─────────────────────────────────────────────────────────────

def fetch_with_retry(fn, *args, retries: int = 3, base_delay: float = 1.0, **kwargs):
    """Call fn(*args, **kwargs) up to `retries` times with exponential back-off."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                _log.warning("fetch_with_retry: attempt %d failed: %s", attempt + 1, exc)
                sleep_sec = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(sleep_sec)
    raise last_exc


# ── cache path helpers ────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.upper()}.parquet"


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Strip tz, keep OHLCV columns, set DatetimeIndex to tz-naive midnight."""
    df = df.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _write_cache(ticker: str, df: pd.DataFrame) -> None:
    path = _cache_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _read_cache(ticker: str) -> pd.DataFrame | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _fetch_raw(ticker: str, **kwargs) -> pd.DataFrame:
    """Fetch from yfinance; raise if empty."""
    df = yf.Ticker(ticker).history(auto_adjust=True, **kwargs)
    if df is None or df.empty:
        raise ValueError(f"Empty response for {ticker}")
    return df


def _do_full_fetch(ticker: str) -> pd.DataFrame:
    """Full history fetch (period=max), normalise, write to cache, return."""
    raw = fetch_with_retry(_fetch_raw, ticker, period="max")
    df = _normalise(raw)
    _write_cache(ticker, df)
    return df


# ── E1.1 ─────────────────────────────────────────────────────────────────────

@dataclass
class RefreshReport:
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    invalidated: list[str] = field(default_factory=list)


def refresh_ticker(ticker: str) -> str:
    """Incrementally update cached history for one ticker.

    Returns "ok" or "invalidated" on success; "ok" also when the tail fetch
    fails (existing cache preserved).
    """
    cached = _read_cache(ticker)
    if cached is None:
        _do_full_fetch(ticker)
        return "ok"

    last_cached = cached.index[-1]
    start_dt = (last_cached - pd.Timedelta(days=5)).date()

    try:
        raw_new = fetch_with_retry(_fetch_raw, ticker, start=str(start_dt))
        new = _normalise(raw_new)
    except Exception as exc:
        _log.warning("refresh_ticker: tail fetch failed for %s: %s", ticker, exc)
        return "ok"

    overlap = cached.index.intersection(new.index)
    if len(overlap) > 0:
        last_overlap = overlap[-1]
        old_close = float(cached.loc[last_overlap, "Close"])
        new_close = float(new.loc[last_overlap, "Close"])
        if old_close != 0 and abs(new_close - old_close) / abs(old_close) > 0.001:
            _log.warning(
                "refresh_ticker: split detected for %s (%.4f → %.4f), full re-fetch",
                ticker, old_close, new_close,
            )
            _do_full_fetch(ticker)
            return "invalidated"

    combined = pd.concat([cached[cached.index < new.index[0]], new])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    _write_cache(ticker, combined)
    return "ok"


def refresh_universe(tickers: Iterable[str], pause: float = 0.2) -> RefreshReport:
    """Refresh cached history for each ticker in `tickers`."""
    tickers = list(tickers)
    report = RefreshReport()
    for i, ticker in enumerate(tickers):
        try:
            result = refresh_ticker(ticker)
            if result == "invalidated":
                report.invalidated.append(ticker)
            else:
                report.succeeded.append(ticker)
        except Exception as exc:
            report.failed.append((ticker, str(exc)))
        if i < len(tickers) - 1:
            time.sleep(pause)
    return report


def get_history(
    ticker: str,
    end: date | None = None,
    refresh: bool = False,
) -> pd.DataFrame | None:
    """Return cached daily OHLCV, optionally sliced to end date."""
    if refresh:
        try:
            refresh_ticker(ticker)
        except Exception:
            pass

    df = _read_cache(ticker)
    if df is None:
        try:
            df = _do_full_fetch(ticker)
        except Exception:
            return None

    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]

    return df if len(df) >= _MIN_ROWS else None


# ── E1.2 ─────────────────────────────────────────────────────────────────────

def get_weekly(ticker: str, end: date | None = None) -> pd.DataFrame | None:
    """Resample cached daily bars to weekly (W-FRI). Drops trailing partial week."""
    daily = get_history(ticker, end=end)
    if daily is None:
        return None

    weekly = daily.resample("W-FRI").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    ).dropna(subset=["Close"])

    if len(weekly) > 0 and weekly.index[-1] > daily.index[-1]:
        weekly = weekly.iloc[:-1]

    return weekly if not weekly.empty else None


def get_ath(ticker: str, end: date | None = None) -> float | None:
    """Return all-time high of cached High series, optionally up to end date."""
    df = _read_cache(ticker)
    if df is None or df.empty:
        return None
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    if df.empty:
        return None
    return float(df["High"].max())


# ── E1.3 ─────────────────────────────────────────────────────────────────────

def get_market_data(end: date | None = None) -> dict[str, pd.DataFrame]:
    """Return cached frames for SPY + all sector ETFs, sliced to end date."""
    result: dict[str, pd.DataFrame] = {}
    for sym in _MARKET_SYMBOLS:
        df = get_history(sym, end=end)
        if df is not None:
            result[sym] = df
    return result
