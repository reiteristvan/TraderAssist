"""Tests for scanner.seasonality — Phase 5 (SEAS-01..05)."""
from __future__ import annotations

import pandas as pd
import pytest

from scanner.core import SECTOR_ETF_MAP
from scanner.seasonality import (
    resolve_sector,
    resolve_sector_universe,
    universe_path,
    valid_sectors,
    validate_history,
    load_sector_dataset,
)


def _synthetic_frame(start: str, periods: int) -> pd.DataFrame:
    """Build a synthetic OHLCV frame spanning `periods` business days from `start`."""
    idx = pd.date_range(start=start, periods=periods, freq="B")
    return pd.DataFrame(
        {
            "Open": 1.0,
            "High": 1.0,
            "Low": 1.0,
            "Close": 1.0,
            "Volume": 1000,
        },
        index=idx,
    )


# ── resolve_sector / valid_sectors ──────────────────────────────────────────

def test_resolve_sector_case_insensitive():
    assert resolve_sector("technology") == "Technology"
    assert resolve_sector("HEALTHCARE") == "Healthcare"
    assert resolve_sector("  Financial Services  ") == "Financial Services"


def test_resolve_sector_unknown_lists_all_names():
    with pytest.raises(ValueError) as excinfo:
        resolve_sector("Widgets")
    message = str(excinfo.value)
    for name in SECTOR_ETF_MAP.keys():
        assert name in message


def test_valid_sectors_sorted_matches_sector_etf_map():
    assert valid_sectors() == sorted(SECTOR_ETF_MAP.keys())


# ── universe_path ────────────────────────────────────────────────────────────

def test_universe_path_valid_mappings():
    assert universe_path("sp500").as_posix() == "universes/sp500.txt"
    assert universe_path("all").as_posix() == "universes/sp_all.txt"
    assert universe_path("SP400").as_posix() == "universes/sp400.txt"
    assert universe_path("sp600").as_posix() == "universes/sp600.txt"


def test_universe_path_unknown_raises():
    with pytest.raises(ValueError):
        universe_path("bogus")
    with pytest.raises(ValueError):
        universe_path("../etc/passwd")


# ── resolve_sector_universe ──────────────────────────────────────────────────

def test_resolve_sector_universe_matched_dropped_skipped(monkeypatch):
    sectors = {"AAPL": "Technology", "JPM": "Financial Services"}

    def fake_get_sector(ticker):
        return sectors.get(ticker)  # XYZ → None

    monkeypatch.setattr("scanner.seasonality.sector_store.get_sector", fake_get_sector)

    matched, skipped = resolve_sector_universe("Technology", ["AAPL", "JPM", "XYZ"])

    assert matched == ["AAPL"]
    assert ("XYZ", "unresolved-sector") in skipped
    assert "JPM" not in matched
    assert all(t != "JPM" for t, _ in skipped)


# ── validate_history ──────────────────────────────────────────────────────────

def test_validate_history_admits_long_history(monkeypatch):
    long_frame = _synthetic_frame("2020-01-01", 780)  # ~3 years

    def fake_get_history(ticker, end=None):
        return long_frame if ticker == "AAPL" else None

    monkeypatch.setattr("scanner.data_store.get_history", fake_get_history)

    frames, skipped = validate_history(["AAPL"])
    assert "AAPL" in frames
    assert skipped == []


def test_validate_history_skips_insufficient_history(monkeypatch):
    short_frame = _synthetic_frame("2025-01-01", 250)  # ~1 year

    def fake_get_history(ticker, end=None):
        return short_frame

    monkeypatch.setattr("scanner.data_store.get_history", fake_get_history)

    frames, skipped = validate_history(["SHRT"])
    assert "SHRT" not in frames
    assert ("SHRT", "insufficient-history") in skipped


def test_validate_history_skips_no_data(monkeypatch):
    def fake_get_history(ticker, end=None):
        return None

    monkeypatch.setattr("scanner.data_store.get_history", fake_get_history)

    frames, skipped = validate_history(["MISSING"])
    assert frames == {}
    assert ("MISSING", "no-data") in skipped


def test_validate_history_no_data_does_not_abort_batch(monkeypatch):
    long_frame = _synthetic_frame("2020-01-01", 780)

    def fake_get_history(ticker, end=None):
        if ticker == "BAD":
            return None
        return long_frame

    monkeypatch.setattr("scanner.data_store.get_history", fake_get_history)

    frames, skipped = validate_history(["BAD", "GOOD"])
    assert "GOOD" in frames
    assert ("BAD", "no-data") in skipped


def test_validate_history_years_trim(monkeypatch):
    long_frame = _synthetic_frame("2020-01-01", 780)  # ~3 years

    def fake_get_history(ticker, end=None):
        return long_frame

    monkeypatch.setattr("scanner.data_store.get_history", fake_get_history)

    frames, skipped = validate_history(["AAPL"], years=1)
    assert "AAPL" in frames
    trimmed = frames["AAPL"]
    span_days = (trimmed.index.max() - trimmed.index.min()).days
    # Trimmed to ~1 year, well under the full ~3-year raw span.
    assert span_days <= 370
    assert skipped == []


# ── load_sector_dataset ───────────────────────────────────────────────────────

def test_load_sector_dataset_invalid_sector_raises_before_get_history(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("get_history called unexpectedly")

    monkeypatch.setattr("scanner.data_store.get_history", _fail)

    with pytest.raises(ValueError):
        load_sector_dataset("Widgets", "sp500")
