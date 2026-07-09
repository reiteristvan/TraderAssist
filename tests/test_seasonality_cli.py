"""Tests for seasonality_by_week.py — the thin CLI wrapper (SEAS-01, SEAS-02)."""
from __future__ import annotations

import pandas as pd

import seasonality_by_week as cli
from scanner.seasonality import SectorDataset


def _tiny_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [1.0, 2.0]},
        index=pd.date_range("2020-01-01", periods=2),
    )


def test_main_happy_path_prints_summary(monkeypatch, capsys):
    """Success: resolved sector, admitted count, and skipped count are printed; returns 0."""
    fake_ds = SectorDataset(
        sector="Technology",
        universe="sp500",
        frames={"AAPL": _tiny_frame(), "MSFT": _tiny_frame()},
        skipped=[("XYZ", "unresolved-sector")],
    )

    def _fake_load(sector, universe, years=None, as_of=None):
        return fake_ds

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Technology" in captured.out
    assert "Admitted: 2" in captured.out
    assert "Skipped: 1" in captured.out


def test_main_invalid_sector_exits_nonzero_no_analysis(monkeypatch, capsys):
    """SEAS-02: unknown --sector exits non-zero, lists valid sectors, runs no analysis."""

    def _raise(*args, **kwargs):
        raise AssertionError("get_history called unexpectedly — no analysis should run")

    # load_sector_dataset is left REAL — resolve_sector must raise before any
    # universe/history work happens. Patching get_history proves that if the
    # pipeline proceeded past sector validation, this test would fail loudly.
    monkeypatch.setattr("scanner.data_store.get_history", _raise)

    result = cli.main(["--sector", "Widgets", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result != 0
    assert result == 2

    err = captured.err
    valid_names = [
        "Technology", "Healthcare", "Financial Services", "Energy", "Industrials",
    ]
    matches = [name for name in valid_names if name in err]
    assert len(matches) >= 3


def test_main_default_universe_is_sp500(monkeypatch):
    """--universe defaults to sp500 when omitted."""
    recorded = {}

    def _fake_load(sector, universe, years=None, as_of=None):
        recorded["universe"] = universe
        return SectorDataset(sector="Technology", universe=universe)

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)

    result = cli.main(["--sector", "Technology"])

    assert result == 0
    assert recorded["universe"] == "sp500"
