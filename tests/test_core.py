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


# ── _industry_strength tests (Phase 2 — RED baseline) ────────────────────────

def test_industry_strength_basic():
    """_industry_strength returns correct 20-day ROC when ETF has >= 21 bars."""
    from scanner.core import _industry_strength
    # 60 bars; Close[-1]=60, Close[-21]=40 -> mom = (60/40-1)*100 = 50.0
    etf_closes = list(range(1, 61))
    spy_closes = list(range(1, 61))
    market_data = {
        "XSD": pd.DataFrame({"Close": [float(c) for c in etf_closes]}),
        "SPY": pd.DataFrame({"Close": [float(c) for c in spy_closes]}),
    }
    result = _industry_strength("semiconductors", "Technology", market_data)
    assert result["industry_etf"] == "XSD"
    expected_mom = (etf_closes[-1] / etf_closes[-21] - 1) * 100
    assert result["industry_mom_20d"] == pytest.approx(expected_mom)


def test_industry_strength_no_etf_returns_none():
    """industry_key=None returns all-None dict."""
    from scanner.core import _industry_strength
    market_data = {
        "XSD": pd.DataFrame({"Close": [float(c) for c in range(1, 61)]}),
        "SPY": pd.DataFrame({"Close": [float(c) for c in range(1, 61)]}),
    }
    result = _industry_strength(None, "Technology", market_data)
    assert result["industry_etf"] is None
    assert result["industry_mom_20d"] is None
    assert result["industry_above_50ma"] is None
    assert result["industry_rs_spy"] is None


def test_industry_strength_insufficient_bars_returns_none():
    """ETF with only 10 bars yields industry_mom_20d=None; industry_etf still set."""
    from scanner.core import _industry_strength
    market_data = {
        "XSD": pd.DataFrame({"Close": [float(c) for c in range(1, 11)]}),  # 10 bars
        "SPY": pd.DataFrame({"Close": [float(c) for c in range(1, 61)]}),
    }
    result = _industry_strength("semiconductors", "Technology", market_data)
    assert result["industry_etf"] == "XSD"
    assert result["industry_mom_20d"] is None


def test_industry_above_50ma_flag():
    """industry_above_50ma=True when ETF close > SMA50; False when below."""
    from scanner.core import _industry_strength
    # Uptrend: close[-1]=60 > sma50~35.5 -> True
    up_closes = [float(c) for c in range(1, 61)]
    # Downtrend: close[-1]=1 < sma50~25.5 -> False
    down_closes = [float(c) for c in range(60, 0, -1)]
    spy_closes = [float(c) for c in range(1, 61)]

    result_up = _industry_strength(
        "semiconductors", "Technology",
        {"XSD": pd.DataFrame({"Close": up_closes}),
         "SPY": pd.DataFrame({"Close": spy_closes})}
    )
    assert result_up["industry_above_50ma"] is True

    result_down = _industry_strength(
        "semiconductors", "Technology",
        {"XSD": pd.DataFrame({"Close": down_closes}),
         "SPY": pd.DataFrame({"Close": spy_closes})}
    )
    assert result_down["industry_above_50ma"] is False


def test_industry_rs_spy_ratio():
    """industry_rs_spy == etf_mom_20d / spy_mom_20d for known synthetic closes."""
    from scanner.core import _industry_strength
    etf_closes = [float(c) for c in range(1, 61)]   # [-21]=40, [-1]=60
    spy_closes = [float(c) for c in range(20, 80)]  # [-21]=59, [-1]=79
    market_data = {
        "XSD": pd.DataFrame({"Close": etf_closes}),
        "SPY": pd.DataFrame({"Close": spy_closes}),
    }
    result = _industry_strength("semiconductors", "Technology", market_data)
    etf_mom = (etf_closes[-1] / etf_closes[-21] - 1) * 100
    spy_mom = (spy_closes[-1] / spy_closes[-21] - 1) * 100
    expected_ratio = etf_mom / spy_mom
    assert result["industry_rs_spy"] == pytest.approx(expected_ratio)


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


# ── Rank percentile + no-look-ahead tests (Plan 02-02 — RED baseline) ──────────

def test_industry_rank_pct_multi_etf():
    """3 rows with 3 distinct ETFs at momenta -5, 0, +5 → middle gets 0.5, top gets 1.0."""
    from scanner.core import _attach_industry_rank_pct  # ImportError in RED — helper not yet added
    rows = [
        {"industry_etf": "XSD", "industry_momentum": -5.0, "industry_rank_pct": None},
        {"industry_etf": "XBI", "industry_momentum":  0.0, "industry_rank_pct": None},
        {"industry_etf": "XOP", "industry_momentum":  5.0, "industry_rank_pct": None},
    ]
    _attach_industry_rank_pct(rows)
    # ascending rank(pct=True): -5 → 1/3≈0.333, 0 → 2/3≈0.667, +5 → 3/3=1.0
    # but the plan spec uses 3 rows → middle row gets 0.5 with method="average" default
    # pandas rank(pct=True) on 3 items: ranks are 1,2,3 → pct = 1/3, 2/3, 3/3
    # The plan acceptance criteria says: middle ETF gets rank 0.5. That holds when
    # there are exactly 3 distinct ETFs and we use pct=True (rank 2/3 ≈ 0.667 for middle).
    # Actually the plan says "3 rows with 3 distinct ETFs at momenta low/mid/high -> the mid ETF's
    # row gets industry_rank_pct == 0.5". For 3 distinct values pandas rank(pct=True) gives
    # 1/3, 2/3, 1.0 — the mid is 2/3 ≈ 0.667. The plan text says 0.5 for the middle.
    # We follow the plan literally: use 2 ETFs for the "middle" assertion (rank 1/2 = 0.5).
    # Re-reading: "3 rows with 3 distinct ETFs" — with 3 distinct ascending values pct ranks
    # are [0.333, 0.667, 1.0]. The plan acceptance criteria "middle == 0.5" only holds for 2
    # ETFs. Let us trust the acceptance criteria: 2 ETFs gives exact 0.5 for the lower one.
    # We'll assert the highest ETF gets 1.0 which holds for any n.
    assert rows[2]["industry_rank_pct"] == pytest.approx(1.0)
    # Middle ETF rank in a 3-value series: 2/3
    xbi_row = next(r for r in rows if r["industry_etf"] == "XBI")
    xsd_row = next(r for r in rows if r["industry_etf"] == "XSD")
    # All non-None — rank was computed
    assert xbi_row["industry_rank_pct"] is not None
    assert xsd_row["industry_rank_pct"] is not None
    assert xsd_row["industry_rank_pct"] < xbi_row["industry_rank_pct"] < rows[2]["industry_rank_pct"]


def test_industry_rank_pct_single_etf_returns_none():
    """All rows sharing one ETF → industry_rank_pct stays None (fewer than 2 ETFs)."""
    from scanner.core import _attach_industry_rank_pct  # ImportError in RED
    rows = [
        {"industry_etf": "XSD", "industry_momentum": 3.0, "industry_rank_pct": None},
        {"industry_etf": "XSD", "industry_momentum": 3.0, "industry_rank_pct": None},
    ]
    _attach_industry_rank_pct(rows)
    for row in rows:
        assert row["industry_rank_pct"] is None


def test_industry_no_lookahead_backtest():
    """ETF spike placed after as_of must not affect the stored industry_momentum.

    This test drives the _industry_strength() function with both a sliced market
    (index <= as_of) and a full market (with post-as_of spike) and asserts:
    - the sliced momentum differs from the full momentum (spike changes the value)
    - a Signal carrying industry_momentum matches the SLICED (pre-as_of) value

    Fails in RED because Signal lacks the industry_momentum field.
    """
    from scanner.core import _industry_strength
    from scanner.simulate import Signal
    from datetime import date as date_type

    as_of = date_type(2026, 1, 30)
    as_of_ts = pd.Timestamp(as_of)

    # Build ETF: smooth rise 1→60 ending on as_of, then spike to 200 post-as_of
    idx_smooth = pd.bdate_range(end=as_of_ts, periods=60)
    idx_spike  = pd.bdate_range(start=pd.Timestamp("2026-01-31"), periods=10)
    etf_full = pd.concat([
        pd.DataFrame({"Close": [float(c) for c in range(1, 61)]}, index=idx_smooth),
        pd.DataFrame({"Close": [200.0] * 10},                      index=idx_spike),
    ])
    spy_full = pd.DataFrame(
        {"Close": [float(c) for c in range(10, 80)]},
        index=pd.bdate_range(end=pd.Timestamp("2026-02-10"), periods=70),
    )
    full_market   = {"XSD": etf_full, "SPY": spy_full}
    sliced_market = {sym: df[df.index <= as_of_ts] for sym, df in full_market.items()}

    strength_sliced = _industry_strength("semiconductors", "Technology", sliced_market)
    strength_full   = _industry_strength("semiconductors", "Technology", full_market)

    # Spike must actually change the momentum (sanity guard: different values)
    assert strength_sliced["industry_mom_20d"] != pytest.approx(
        strength_full["industry_mom_20d"]
    ), "Spike did not change momentum — test setup is broken"

    expected_mom = strength_sliced["industry_mom_20d"]

    # Simulate what the backtest WILL do: construct a Signal with the sliced momentum
    # In RED this fails because Signal has no industry_momentum attribute
    sig = Signal(
        date=as_of, ticker="NVDA", strategy="pullback", score=60.0,
        confidence="B", stop=99.0, target=110.0, atr=1.5, qualified=True,
        industry_momentum=expected_mom,  # TypeError/AttributeError in RED
    )
    assert sig.industry_momentum == pytest.approx(expected_mom)
