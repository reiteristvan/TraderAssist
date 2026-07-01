"""Unit tests for scanner.core: GateLog (E2.1) and context factory (E2.4)."""
import numpy as np
import pandas as pd
import pytest
from datetime import date

from scanner.core import GateLog, QualityInfo, EvalContext, _days_to_earnings


# ── resolve_industry_etf tests ────────────────────────────────────────────────

def test_resolve_industry_etf_direct_hit():
    """Direct map hit: known industry key returns the mapped ETF."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf("semiconductors", "Technology") == "XSD"


def test_resolve_industry_etf_sector_fallback_encoded_in_map():
    """Sector-fallback entries are explicit in the map (D-03), not separate logic."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf("oil-gas-integrated", "Energy") == "XLE"


def test_resolve_industry_etf_none_industry_key():
    """industry_key=None returns None immediately — no sector fallback (D-06)."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf(None, "Technology") is None


def test_resolve_industry_etf_unknown_key_sector_fallback():
    """Key absent from INDUSTRY_ETF_MAP falls through to SECTOR_ETF_MAP (D-07)."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf("totally-unknown-key", "Technology") == "XLK"


def test_resolve_industry_etf_unknown_key_no_sector():
    """Key absent, sector=None — returns None."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf("totally-unknown-key", None) is None


def test_resolve_industry_etf_unknown_key_nonexistent_sector():
    """Key absent, sector not in SECTOR_ETF_MAP — returns None."""
    from scanner.core import resolve_industry_etf
    assert resolve_industry_etf("totally-unknown-key", "Nonexistent Sector") is None


# ── GateLog tests ─────────────────────────────────────────────────────────────

def test_gate_counts():
    log = GateLog("T")
    log.gate("A", True)
    log.gate("B", True)
    log.gate("C", True)
    log.gate("D", False)
    assert log.gates_total == 4
    assert log.gates_passed == 3
    assert log.qualified is False
    assert log.failed_gates == ["D"]


def test_skip_excluded_from_total():
    log = GateLog("T")
    log.gate("A", True)
    log.gate("B", False)
    log.skip("C", "no data")
    assert log.gates_total == 2
    assert len(log.skipped_gates) == 1
    assert log.skipped_gates == ["C"]
    assert "C" not in log.failed_gates


def test_verbose_output(capsys):
    log = GateLog("TEST", verbose=True)
    log.section("Section One")
    log.gate("Gate A", True, "pass detail")
    log.gate("Gate B", False, "fail detail")
    log.skip("Gate C", "no data")
    captured = capsys.readouterr()
    expected = (
        "\n=== TEST ===\n"
        "Section One:\n"
        "  ✓ Gate A (pass detail)\n"
        "  ✗ Gate B (fail detail)\n"
        "  – Gate C (skipped: no data)\n"
    )
    assert captured.out == expected


def test_qualified_all_pass():
    log = GateLog("T")
    log.gate("X", True)
    log.gate("Y", True)
    assert log.qualified is True
    assert log.failed_gates == []


# ── E12.2a — GateLog.to_detail_list() ────────────────────────────────────────

def test_to_detail_list_entries():
    log = GateLog("T")
    log.gate("Gate A", True, "some detail")
    log.gate("Gate B", False, "")
    log.skip("Gate C", "no data")
    log.bonus("Bonus X", True, "bonus detail")
    log.bonus("Bonus Y", False)
    detail = log.to_detail_list()
    assert len(detail) == 5
    assert detail[0] == {"name": "Gate A", "status": "pass", "detail": "some detail"}
    assert detail[1] == {"name": "Gate B", "status": "fail", "detail": ""}
    assert detail[2] == {"name": "Gate C", "status": "skip", "detail": "no data"}
    assert detail[3] == {"name": "Bonus X", "status": "bonus_pass", "detail": "bonus detail"}
    assert detail[4] == {"name": "Bonus Y", "status": "bonus_fail", "detail": ""}


def test_to_detail_list_is_copy():
    """Returns a new list each call; mutations don't affect the log."""
    log = GateLog("T")
    log.gate("A", True)
    d1 = log.to_detail_list()
    d1.append({"name": "INJECTED"})
    d2 = log.to_detail_list()
    assert len(d2) == 1  # injection not reflected


def test_to_detail_list_ordering():
    """Entries are in call order."""
    log = GateLog("T")
    names = ["First", "Second", "Third"]
    for n in names:
        log.gate(n, True)
    detail = log.to_detail_list()
    assert [d["name"] for d in detail] == names


# ── Earnings parser tests ─────────────────────────────────────────────────────

def _patch_calendar(monkeypatch, cal_value):
    """Monkeypatch yf.Ticker(...).calendar to return cal_value."""
    import yfinance as yf

    class FakeTicker:
        def __init__(self, *a, **kw):
            self.calendar = cal_value
        def __getattr__(self, name):
            return None

    monkeypatch.setattr(yf, "Ticker", FakeTicker)


def test_earnings_parser_dict(monkeypatch):
    as_of = date(2026, 1, 1)
    future = pd.Timestamp("2026-01-11")
    _patch_calendar(monkeypatch, {"Earnings Date": [future]})
    result = _days_to_earnings("X", as_of)
    assert result == 10


def test_earnings_parser_dataframe(monkeypatch):
    as_of = date(2026, 1, 1)
    future = pd.Timestamp("2026-01-11")
    cal_df = pd.DataFrame({"col": [future]}, index=["Earnings Date"])
    _patch_calendar(monkeypatch, cal_df)
    result = _days_to_earnings("X", as_of)
    assert result == 10


def test_earnings_parser_none(monkeypatch):
    _patch_calendar(monkeypatch, None)
    result = _days_to_earnings("X", date(2026, 1, 1))
    assert result is None


def test_earnings_parser_normal_future(monkeypatch):
    as_of = date(2026, 1, 1)
    future = pd.Timestamp("2026-1-20")
    _patch_calendar(monkeypatch, {"Earnings Date": [future]})
    result = _days_to_earnings("X", as_of)
    assert result == 19


# ── Historical context slicing test ──────────────────────────────────────────

# ── QualityInfo industry classification fields (Plan 01-02) ──────────────────

def test_quality_info_industry_default():
    """Five-arg positional construction: industry and industry_key default to None (D-04)."""
    qi = QualityInfo(False, None, None, None, None)
    assert qi.industry is None
    assert qi.industry_key is None


def test_quality_info_industry_roundtrip():
    """Explicit keyword args round-trip correctly through the frozen dataclass (D-04)."""
    qi = QualityInfo(
        profitable=True,
        market_cap=2.5e9,
        debt_equity=50.0,
        sector="Technology",
        float_shares=50e6,
        industry="Semiconductors",
        industry_key="semiconductors",
    )
    assert qi.industry == "Semiconductors"
    assert qi.industry_key == "semiconductors"


def test_quality_info_no_classification_is_none_not_empty_string():
    """No classification yields None — not empty string (success criterion 3)."""
    qi = QualityInfo(profitable=True, market_cap=1e9, debt_equity=None,
                     sector=None, float_shares=None)
    assert qi.industry is None
    assert qi.industry_key is None


# ── Historical context slicing test ──────────────────────────────────────────

def test_historical_context_sliced(tmp_path, monkeypatch):
    import scanner.data_store as ds
    import scanner.core as core

    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    # 400 rows ending 2026-06-15 so sliced to 2026-01-15 still has ≥220 rows
    idx = pd.bdate_range(end=pd.Timestamp("2026-06-15"), periods=400)
    closes = np.linspace(10.0, 30.0, 400)
    full_df = pd.DataFrame({
        "Open": closes - 0.1, "High": closes + 0.2, "Low": closes - 0.2,
        "Close": closes, "Volume": np.full(400, 1_000_000.0),
    }, index=idx)

    # Write cache for SYN + all market symbols
    for sym in ["SYN"] + ds._MARKET_SYMBOLS:
        ds._write_cache(sym, full_df)

    # Stub out quality (no network)
    monkeypatch.setattr(core, "_make_quality_info",
                        lambda t: QualityInfo(True, 2.5e9, 50.0, "Technology", 50e6))

    as_of = date(2026, 1, 15)
    ctx = core.make_context("SYN", as_of=as_of)

    assert ctx is not None
    assert ctx.as_of == as_of
    assert ctx.days_to_earnings is None  # historical mode
    for sym, df_sym in ctx.market_data.items():
        assert df_sym.index.max().date() <= as_of, f"{sym} has data past as_of"
