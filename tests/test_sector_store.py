"""Tests for scanner.sector_store — Phase 5 (SEAS-01)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scanner.sector_store import get_sector


def test_get_sector_cached(tmp_path, monkeypatch):
    """Cached parquet is returned without calling yfinance."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)

    df = pd.DataFrame({"sector": ["Technology"]})
    df.to_parquet(tmp_path / "AAPL.parquet")

    def _fail(*args, **kwargs):
        raise AssertionError("yfinance called unexpectedly")

    monkeypatch.setattr("yfinance.Ticker", _fail)

    result = get_sector("AAPL")
    assert result == "Technology"


def test_get_sector_cache_miss(tmp_path, monkeypatch):
    """Cache miss fetches via fetch_with_retry, writes parquet, returns sector."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(ss, "fetch_with_retry", lambda fn, *a, **kw: "Healthcare")

    result = get_sector("NEW")
    assert result == "Healthcare"
    assert (tmp_path / "NEW.parquet").exists()


def test_get_sector_unresolved_writes_sentinel(tmp_path, monkeypatch):
    """Unresolved sector (None from fetch) → None, sentinel written, no re-fetch."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(ss, "fetch_with_retry", lambda fn, *a, **kw: None)

    result = get_sector("BADSEC")
    assert result is None
    assert (tmp_path / "BADSEC.parquet").exists()

    # Anti-retry-storm: second call must not re-fetch
    def _fail(*args, **kwargs):
        raise AssertionError("fetch_with_retry called unexpectedly on cache hit")

    monkeypatch.setattr(ss, "fetch_with_retry", _fail)
    result2 = get_sector("BADSEC")
    assert result2 is None


def test_get_sector_fetch_failure(tmp_path, monkeypatch):
    """fetch_with_retry raises → None, no exception propagates."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)

    def _always_fail(fn, *a, **kw):
        raise RuntimeError("network error")

    monkeypatch.setattr(ss, "fetch_with_retry", _always_fail)

    result = get_sector("FAIL")
    assert result is None
    assert (tmp_path / "FAIL.parquet").exists()


def test_get_sector_reserved_name(tmp_path, monkeypatch):
    """Reserved Windows device name → None, guarded before any fetch/path build."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)

    def _fail(*args, **kwargs):
        raise AssertionError("fetch_with_retry called unexpectedly for reserved name")

    monkeypatch.setattr(ss, "fetch_with_retry", _fail)

    result = get_sector("CON")
    assert result is None


def test_get_sector_corrupt_cache_falls_through(tmp_path, monkeypatch):
    """A corrupt/unreadable cached parquet falls through to refetch instead of raising."""
    import scanner.sector_store as ss
    monkeypatch.setattr(ss, "_CACHE_DIR", tmp_path)

    bad_path = tmp_path / "CORRUPT.parquet"
    bad_path.write_text("not a real parquet file")

    monkeypatch.setattr(ss, "fetch_with_retry", lambda fn, *a, **kw: "Energy")

    result = get_sector("CORRUPT")
    assert result == "Energy"
