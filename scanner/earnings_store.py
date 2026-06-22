"""E5.3 — Cached earnings dates.

Parquet-cached historical earnings dates, used to compute days_to_earnings
for historical EvalContexts. See CLAUDE.md EPIC E5.3.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from scanner.data_store import fetch_with_retry

_log = logging.getLogger("scanner.data")
_CACHE_DIR = Path("data/earnings")
_SPARSE_DAYS = 90  # if latest known date is >90 days before as_of, return None


def _cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.upper()}_earnings.parquet"


def get_earnings_dates(ticker: str, refresh: bool = False) -> list[date]:
    """Return cached list of known earnings dates for ticker.

    Fetches via yf.Ticker.get_earnings_dates(limit=60), Parquet-cached.
    Empty list if data unavailable or fetch fails.
    """
    path = _cache_path(ticker)

    if not refresh and path.exists():
        try:
            df = pd.read_parquet(path)
            return [
                ts.date() if hasattr(ts, "date") else ts
                for ts in df["date"].tolist()
            ]
        except Exception:
            pass

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        def _fetch():
            return yf.Ticker(ticker).get_earnings_dates(limit=60)

        df_raw = fetch_with_retry(_fetch)

        dates: list[date] = []
        if df_raw is not None and not df_raw.empty:
            if isinstance(df_raw.index, pd.DatetimeIndex):
                dates = [ts.date() for ts in df_raw.index if pd.notna(ts)]
            elif "Earnings Date" in df_raw.columns:
                dates = [
                    pd.Timestamp(d).date()
                    for d in df_raw["Earnings Date"]
                    if pd.notna(d)
                ]

        dates = sorted(set(dates))
        df_out = pd.DataFrame({"date": [pd.Timestamp(d) for d in dates]})
        df_out.to_parquet(path)
        return dates

    except Exception as exc:
        _log.warning("get_earnings_dates: %s failed: %s", ticker, exc)
        # Cache empty so we don't retry every call
        try:
            pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")}).to_parquet(path)
        except Exception:
            pass
        return []


def days_to_earnings(ticker: str, as_of: date) -> Optional[int]:
    """Days from as_of to the next known earnings date strictly after as_of.

    Returns None if:
    - No cached earnings data for this ticker
    - Latest known date predates as_of by >90 days (too sparse to trust)
    - No future date found after as_of
    """
    dates = get_earnings_dates(ticker)
    if not dates:
        return None

    latest = max(dates)
    as_of_ts = pd.Timestamp(as_of)
    if (as_of_ts - pd.Timestamp(latest)).days > _SPARSE_DAYS:
        return None

    future = [d for d in dates if d > as_of]
    if not future:
        return None

    return int((pd.Timestamp(min(future)) - as_of_ts).days)
