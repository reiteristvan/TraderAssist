"""Phase 5 (SEAS-01) — Cached ticker to GICS sector lookup.

Parquet-cached per-ticker sector classification, used by the seasonality
pipeline to filter a universe down to a single sector. Mirrors
scanner/earnings_store.py's cache pattern exactly. See
.planning/phases/05-sector-resolution-data-input/05-CONTEXT.md.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from scanner.data_store import fetch_with_retry, _is_reserved

_log = logging.getLogger("scanner.data")
_CACHE_DIR = Path("data/sectors")


def _cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.upper()}.parquet"


def get_sector(ticker: str, refresh: bool = False) -> Optional[str]:
    """Return cached GICS sector string for ticker.

    Fetches via yf.Ticker(ticker).info['sector'], Parquet-cached. Returns
    None if the sector can't be resolved or the fetch fails; an empty-cache
    sentinel is written so subsequent calls don't retry every run.
    """
    if _is_reserved(ticker):
        return None

    path = _cache_path(ticker)

    if not refresh and path.exists():
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return None
            return df["sector"].iloc[0]
        except Exception:
            pass

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        def _fetch():
            return yf.Ticker(ticker).info.get("sector")

        sector = fetch_with_retry(_fetch)

        if sector:
            pd.DataFrame({"sector": [sector]}).to_parquet(path)
            return sector

        # Unresolved sector — cache empty so we don't retry every call
        try:
            pd.DataFrame({"sector": pd.Series([], dtype="object")}).to_parquet(path)
        except Exception:
            pass
        return None

    except Exception as exc:
        _log.warning("get_sector: %s failed: %s", ticker, exc)
        # Cache empty so we don't retry every call
        try:
            pd.DataFrame({"sector": pd.Series([], dtype="object")}).to_parquet(path)
        except Exception:
            pass
        return None
