"""Tests for scanner.earnings_store — E5.3."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scanner.earnings_store import days_to_earnings, get_earnings_dates


# ── days_to_earnings unit tests ───────────────────────────────────────────────

def _patch_dates(monkeypatch, ticker, dates):
    """Patch get_earnings_dates to return a fixed list without disk access."""
    monkeypatch.setattr(
        "scanner.earnings_store.get_earnings_dates",
        lambda t, refresh=False: dates if t == ticker else [],
    )


def test_days_to_earnings_2_days_before(monkeypatch):
    """as_of 2 days before an earnings date → returns 2."""
    _patch_dates(monkeypatch, "AAPL", [date(2026, 2, 1), date(2026, 5, 1)])
    result = days_to_earnings("AAPL", date(2026, 1, 30))
    assert result == 2


def test_days_to_earnings_after_last_known(monkeypatch):
    """as_of after the latest known date → None."""
    _patch_dates(monkeypatch, "AAPL", [date(2026, 1, 1)])
    result = days_to_earnings("AAPL", date(2026, 2, 15))
    assert result is None


def test_days_to_earnings_sparse_history(monkeypatch):
    """Latest known date predates as_of by >90 days → None."""
    _patch_dates(monkeypatch, "AAPL", [date(2025, 10, 1)])
    # as_of is 91+ days after latest known
    result = days_to_earnings("AAPL", date(2026, 1, 15))
    assert result is None


def test_days_to_earnings_empty_dates(monkeypatch):
    """No cached dates → None."""
    _patch_dates(monkeypatch, "AAPL", [])
    result = days_to_earnings("AAPL", date(2026, 1, 15))
    assert result is None


def test_days_to_earnings_exact_boundary(monkeypatch):
    """Exactly 90 days before as_of — should NOT be treated as sparse."""
    _patch_dates(monkeypatch, "AAPL", [date(2026, 4, 15), date(2026, 1, 15)])
    as_of = date(2026, 4, 1)
    # latest known = 2026-04-15 which is AFTER as_of → should return 14
    result = days_to_earnings("AAPL", as_of)
    assert result == 14


def test_days_to_earnings_no_future_dates(monkeypatch):
    """All known dates are in the past relative to as_of, but within 90 days → None."""
    _patch_dates(monkeypatch, "AAPL", [date(2026, 1, 1), date(2026, 1, 15)])
    result = days_to_earnings("AAPL", date(2026, 2, 1))
    # latest = 2026-01-15, as_of = 2026-02-01 → (2026-02-01 - 2026-01-15) = 17 days, not sparse
    # but no future dates after 2026-02-01 → None
    assert result is None


# ── get_earnings_dates with mock yfinance ─────────────────────────────────────

def test_get_earnings_dates_cached(tmp_path, monkeypatch):
    """Cached parquet is returned without calling yfinance."""
    import scanner.earnings_store as es
    monkeypatch.setattr(es, "_CACHE_DIR", tmp_path)

    # Write a fake cache
    dates = [date(2026, 2, 1), date(2026, 5, 1)]
    df = pd.DataFrame({"date": [pd.Timestamp(d) for d in dates]})
    df.to_parquet(tmp_path / "AAPL_earnings.parquet")

    # yfinance should NOT be called
    def _fail(*args, **kwargs):
        raise AssertionError("yfinance called unexpectedly")

    monkeypatch.setattr("yfinance.Ticker", _fail)

    result = get_earnings_dates("AAPL")
    assert result == dates


def test_get_earnings_dates_empty_response(tmp_path, monkeypatch):
    """Empty yfinance response → empty list, no crash."""
    import scanner.earnings_store as es
    monkeypatch.setattr(es, "_CACHE_DIR", tmp_path)

    class _MockTicker:
        def get_earnings_dates(self, limit=60):
            return pd.DataFrame()

    monkeypatch.setattr("yfinance.Ticker", lambda t: _MockTicker())
    monkeypatch.setattr(es, "fetch_with_retry", lambda fn, *a, **kw: fn())

    result = get_earnings_dates("EMPTY")
    assert result == []


def test_get_earnings_dates_fetch_fail(tmp_path, monkeypatch):
    """yfinance error → empty list, no crash."""
    import scanner.earnings_store as es
    monkeypatch.setattr(es, "_CACHE_DIR", tmp_path)

    def _always_fail():
        raise RuntimeError("network error")

    monkeypatch.setattr(es, "fetch_with_retry", lambda fn, *a, **kw: _always_fail())

    result = get_earnings_dates("FAIL")
    assert result == []
