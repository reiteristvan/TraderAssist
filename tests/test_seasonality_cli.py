"""Tests for seasonality_by_week.py — the thin CLI wrapper (SEAS-01, SEAS-02)."""
from __future__ import annotations

import pandas as pd

import seasonality_by_week as cli
from scanner.seasonality import SectorDataset, SeasonalityResult


def _tiny_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [1.0, 2.0]},
        index=pd.date_range("2020-01-01", periods=2),
    )


def _fake_result() -> SeasonalityResult:
    weeks = pd.DataFrame(
        {
            "week": [1, 2],
            "mean_daily_ret_bps": [1.0, -1.0],
            "delta_vs_baseline_bps": [0.5, -0.5],
            "ci_low_bps": [-1.0, -2.0],
            "ci_high_bps": [2.0, 1.0],
            "median_bps": [1.0, -1.0],
            "n_obs": [10, 10],
            "n_years": [5, 5],
            "significant": [False, False],
            "std_bps": [1.0, 1.0],
        }
    )
    return SeasonalityResult(
        sector="Technology",
        universe="sp500",
        baseline_mean_bps=0.25,
        n_years=5,
        bootstrap_iters=1000,
        seed=42,
        weeks=weeks,
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

    def _fake_compute(dataset, bootstrap_iters=None, seed=None):
        return _fake_result()

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)
    monkeypatch.setattr("scanner.seasonality.compute_seasonality_stats", _fake_compute)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Technology" in captured.out
    assert "Admitted: 2" in captured.out
    assert "Skipped: 1" in captured.out
    assert "Bootstrap iters: 1000" in captured.out
    assert "Seed: 42" in captured.out
    assert "Significant weeks: 0 of 2" in captured.out


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


def test_main_thin_data_value_error_exits_2(monkeypatch, capsys):
    """A ValueError from compute_seasonality_stats (thin-data/iters guard) exits 2."""
    fake_ds = SectorDataset(sector="Technology", universe="sp500")

    def _fake_load(sector, universe, years=None, as_of=None):
        return fake_ds

    def _fake_compute(dataset, bootstrap_iters=None, seed=None):
        raise ValueError("Too few distinct years for an honest bootstrap: found 2, need >= 5.")

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)
    monkeypatch.setattr("scanner.seasonality.compute_seasonality_stats", _fake_compute)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 2
    assert "Too few distinct years" in captured.err


def test_main_default_universe_is_sp500(monkeypatch):
    """--universe defaults to sp500 when omitted."""
    recorded = {}

    def _fake_load(sector, universe, years=None, as_of=None):
        recorded["universe"] = universe
        return SectorDataset(sector="Technology", universe=universe)

    def _fake_compute(dataset, bootstrap_iters=None, seed=None):
        return _fake_result()

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)
    monkeypatch.setattr("scanner.seasonality.compute_seasonality_stats", _fake_compute)

    result = cli.main(["--sector", "Technology"])

    assert result == 0
    assert recorded["universe"] == "sp500"
