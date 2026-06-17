"""Tests for scanner.data_store (E1.1, E1.2, E1.3)."""
from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
import pytest

import scanner.data_store as ds
from scanner.data_store import (
    RefreshReport,
    _write_cache,
    fetch_with_retry,
    get_ath,
    get_history,
    get_market_data,
    get_weekly,
    refresh_ticker,
)


# ── local helper ──────────────────────────────────────────────────────────────

def _make_df(n=260, start="2025-01-02"):
    """n business-day OHLCV frame, tz-naive DatetimeIndex."""
    idx = pd.bdate_range(start=start, periods=n)
    closes = np.linspace(10.0, 20.0, n)
    return pd.DataFrame(
        {
            "Open": closes - 0.1,
            "High": closes + 0.2,
            "Low": closes - 0.2,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


# ── E1.1 tests ────────────────────────────────────────────────────────────────

def test_two_calls_one_fetch(tmp_path, monkeypatch):
    """Second get_history call hits the on-disk cache; _fetch_raw called once."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)
    call_count = {"n": 0}

    def fake_fetch_raw(ticker, **kwargs):
        call_count["n"] += 1
        return _make_df()

    monkeypatch.setattr(ds, "_fetch_raw", fake_fetch_raw)

    get_history("X")
    get_history("X")

    assert call_count["n"] == 1


def test_split_invalidation(tmp_path, monkeypatch):
    """A >0.1% close mismatch on the overlap date triggers a full re-fetch."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    # Write initial cache: 260 rows, last row Close = 10.0
    cached_df = _make_df(n=260)
    # Force last Close to exactly 10.0 for comparison clarity
    cached_df.iloc[-1, cached_df.columns.get_loc("Close")] = 10.0
    cached_df.iloc[-1, cached_df.columns.get_loc("High")] = 10.2
    cached_df.iloc[-1, cached_df.columns.get_loc("Low")] = 9.8
    _write_cache("X", cached_df)

    call_count = {"n": 0}

    def fake_fetch_raw(ticker, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Tail fetch: overlaps on last cached date with Close=12.0 (>0.1% diff)
            last_date = cached_df.index[-1]
            tail = pd.DataFrame(
                {
                    "Open": [11.9, 12.4],
                    "High": [12.2, 12.6],
                    "Low": [11.8, 12.2],
                    "Close": [12.0, 12.5],
                    "Volume": [1_000_000.0, 1_000_000.0],
                },
                index=pd.DatetimeIndex(
                    [last_date, last_date + pd.Timedelta(days=1)],
                    freq=None,
                ),
            )
            return tail
        else:
            # Full re-fetch
            return _make_df(n=300)

    monkeypatch.setattr(ds, "_fetch_raw", fake_fetch_raw)

    result = refresh_ticker("X")

    assert result == "invalidated"
    assert call_count["n"] == 2


def test_end_date_slicing(tmp_path, monkeypatch):
    """get_history(end=d) returns only rows with index.date <= d."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)
    df = _make_df(n=300, start="2025-01-02")
    _write_cache("X", df)

    # Patch _fetch_raw so it's never called (should use cache)
    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not fetch")))

    cutoff = date(2026, 1, 15)
    result = get_history("X", end=cutoff)

    assert result is not None
    assert all(d.date() <= cutoff for d in result.index)


def test_corrupt_parquet(tmp_path, monkeypatch):
    """Corrupt cache file is ignored; _fetch_raw is called to recover."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    # Write junk bytes
    (tmp_path / "X.parquet").write_bytes(b"this is not valid parquet data")

    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: _make_df())

    result = get_history("X")

    assert result is not None


def test_retry_warns_and_succeeds(caplog):
    """fetch_with_retry: 2 failures then success → result returned, 2 WARNINGs."""
    call_count = {"n": 0}

    def flaky():
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ValueError("transient")
        return "success"

    with caplog.at_level(logging.WARNING, logger="scanner.data"):
        result = fetch_with_retry(flaky, retries=3, base_delay=0.0)

    assert result == "success"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == "scanner.data"]
    assert len(warnings) == 2


def test_retry_raises_after_all_fail(caplog):
    """fetch_with_retry: always-failing fn raises after all retries."""
    def always_fail():
        raise RuntimeError("permanent")

    with caplog.at_level(logging.WARNING, logger="scanner.data"):
        with pytest.raises(RuntimeError, match="permanent"):
            fetch_with_retry(always_fail, retries=3, base_delay=0.0)


# ── E1.2 tests ────────────────────────────────────────────────────────────────

def _make_15day_df():
    """13 business days Jun 1–Jun 17, 2026 (ends Wed → partial Jun-19 week drops).

    Close = 1.0 to 13.0.
    """
    idx = pd.bdate_range("2026-06-01", periods=13)
    closes = np.arange(1.0, 14.0, dtype=float)
    return pd.DataFrame(
        {
            "Open": closes - 0.1,
            "High": closes + 0.2,
            "Low": closes - 0.2,
            "Close": closes,
            "Volume": np.full(len(closes), 1000.0),
        },
        index=idx,
    )


def test_weekly_resample_and_partial_drop(tmp_path, monkeypatch):
    """Weekly resampling drops the trailing partial week and aggregates correctly."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    daily = _make_15day_df()
    # Need >= _MIN_ROWS in cache to pass get_history; patch _MIN_ROWS
    monkeypatch.setattr(ds, "_MIN_ROWS", 5)
    _write_cache("X", daily)

    # Patch _fetch_raw so no network call is needed
    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no fetch")))

    weekly = get_weekly("X")

    assert weekly is not None
    # Jun 5 and Jun 12 are the Friday close dates; Jun 19 partial week dropped
    assert len(weekly) == 2

    # Week ending Jun 5 covers Mon Jun 1 – Fri Jun 5 (days 1–5, Close 1–5)
    w1 = weekly.iloc[0]
    # Week 1 (Jun 1-5): Close 1-5, Open 0.9-4.9, High 1.2-5.2, Low 0.8-4.8
    assert abs(w1["Open"] - 0.9) < 0.05      # first(Open) = Open on Jun 1 = 0.9
    assert abs(w1["High"] - 5.2) < 0.05      # max High = 5.2 (Fri Jun 5)
    assert abs(w1["Low"] - 0.8) < 0.05       # min Low = 0.8 (Mon Jun 1)
    assert abs(w1["Close"] - 5.0) < 0.05     # last Close = 5.0 (Fri Jun 5)
    assert w1["Volume"] == pytest.approx(5000.0)

    # Week ending Jun 12 covers Mon Jun 8 – Fri Jun 12 (days 6–10, Close 6–10)
    # Open 5.9-9.9, High 6.2-10.2, Low 5.8-9.8
    w2 = weekly.iloc[1]
    assert abs(w2["Open"] - 5.9) < 0.05
    assert abs(w2["High"] - 10.2) < 0.05
    assert abs(w2["Low"] - 5.8) < 0.05
    assert abs(w2["Close"] - 10.0) < 0.05
    assert w2["Volume"] == pytest.approx(5000.0)


def test_weekly_end_mid_week(tmp_path, monkeypatch):
    """get_weekly with end=Jun 12 returns 2 complete weekly bars."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(ds, "_MIN_ROWS", 5)

    daily = _make_15day_df()
    _write_cache("X", daily)
    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no fetch")))

    weekly = get_weekly("X", end=date(2026, 6, 12))

    assert weekly is not None
    assert len(weekly) == 2


def test_get_ath_point_in_time(tmp_path, monkeypatch):
    """get_ath respects end date for point-in-time correctness."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    df = _make_df(n=300, start="2024-01-02")
    # Spike High at row 200
    spike_date = df.index[200]
    df.iloc[200, df.columns.get_loc("High")] = 50.0

    _write_cache("X", df)

    # Before spike: ATH should be ~10.2 (max of first 200 rows, High = Close + 0.2)
    before_date = (spike_date - pd.Timedelta(days=1)).date()
    ath_before = get_ath("X", end=before_date)
    assert ath_before is not None
    assert ath_before < 30.0  # well below the 50.0 spike

    # At or after spike: ATH should be 50.0
    ath_after = get_ath("X", end=spike_date.date())
    assert ath_after is not None
    assert abs(ath_after - 50.0) < 0.01


# ── E1.3 tests ────────────────────────────────────────────────────────────────

def test_market_data_zero_fetches(tmp_path, monkeypatch):
    """get_market_data uses cache only; _fetch_raw is never called."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    for sym in ds._MARKET_SYMBOLS:
        _write_cache(sym, _make_df())

    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not fetch")))

    result = get_market_data()

    assert set(result.keys()) == set(ds._MARKET_SYMBOLS)


def test_market_data_end_alignment(tmp_path, monkeypatch):
    """All frames returned by get_market_data(end=d) have max date <= d."""
    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    for sym in ds._MARKET_SYMBOLS:
        _write_cache(sym, _make_df(n=300, start="2024-01-02"))

    monkeypatch.setattr(ds, "_fetch_raw", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not fetch")))

    cutoff = date(2025, 6, 15)
    result = get_market_data(end=cutoff)

    assert len(result) == len(ds._MARKET_SYMBOLS)
    for sym, df in result.items():
        max_date = df.index.max().date()
        assert max_date <= cutoff, f"{sym}: max date {max_date} > {cutoff}"
