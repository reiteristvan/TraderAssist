"""Tests for seasonality_by_week.py — the thin CLI wrapper (SEAS-01, SEAS-02,
SEAS-10..13)."""
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
    # Only weeks 1-2 present (Phase 6's real weeks DataFrame only carries
    # observed weeks) -- exercises pad_weeks_table's 52-row padding and N/A
    # cells (SEAS-10). Carries insufficient_years like the real pipeline.
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
            "insufficient_years": [False, False],
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
    assert "none — no week deviates significantly from baseline" in captured.out


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


def _patch_fake_pipeline(monkeypatch):
    fake_ds = SectorDataset(
        sector="Technology",
        universe="sp500",
        frames={"AAPL": _tiny_frame(), "MSFT": _tiny_frame()},
        skipped=[],
    )

    def _fake_load(sector, universe, years=None, as_of=None):
        return fake_ds

    def _fake_compute(dataset, bootstrap_iters=None, seed=None):
        return _fake_result()

    monkeypatch.setattr("scanner.seasonality.load_sector_dataset", _fake_load)
    monkeypatch.setattr("scanner.seasonality.compute_seasonality_stats", _fake_compute)


def test_main_prints_survivorship_warning_header(monkeypatch, capsys):
    """SEAS-12: the survivorship-bias warning header prints on every run."""
    _patch_fake_pipeline(monkeypatch)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Survivorship" in captured.out


def test_main_prints_padded_52_row_table(monkeypatch, capsys):
    """SEAS-10: the printed table has all 9 display columns and is padded to
    52 weeks even though the fake result only carries weeks 1-2."""
    _patch_fake_pipeline(monkeypatch)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    for header in ("week", "mean_daily_ret_bps", "significant"):
        assert header in captured.out
    assert "52" in captured.out
    # Week 52 is padded in with N/A cells since only weeks 1-2 are present.
    assert "N/A" in captured.out


def test_main_prints_interpretive_summary(monkeypatch, capsys):
    """SEAS-11: the summary block (significant list or none-message, plus the
    multiple-comparison caveat) prints on every run."""
    _patch_fake_pipeline(monkeypatch)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    assert "none — no week deviates significantly from baseline" in captured.out
    assert "Multiple-comparison caveat" in captured.out


def test_main_output_writes_csv_and_still_prints_stdout(monkeypatch, capsys, tmp_path):
    """D-14/SEAS-13: --output writes a 52-row 9-column CSV AND stdout still
    prints the full table/summary output (additive, not a replacement)."""
    _patch_fake_pipeline(monkeypatch)
    out_path = tmp_path / "out.csv"

    result = cli.main(
        ["--sector", "Technology", "--universe", "sp500", "--output", str(out_path)]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert out_path.exists()
    assert "week" in captured.out
    assert "none — no week deviates significantly from baseline" in captured.out
    assert f"Saved → {out_path}" in captured.out

    written = pd.read_csv(out_path, keep_default_na=False)
    assert len(written) == 52
    expected_columns = [
        "week", "mean_daily_ret_bps", "delta_vs_baseline_bps", "ci_low_bps",
        "ci_high_bps", "median_bps", "n_obs", "n_years", "significant",
    ]
    assert list(written.columns) == expected_columns


def test_main_without_output_writes_no_file(monkeypatch, capsys, tmp_path):
    """SEAS-13: omitting --output prints stdout output and writes no file."""
    _patch_fake_pipeline(monkeypatch)

    result = cli.main(["--sector", "Technology", "--universe", "sp500"])

    captured = capsys.readouterr()
    assert result == 0
    assert "week" in captured.out
    assert list(tmp_path.iterdir()) == []


def test_main_output_creates_missing_parent_dir(monkeypatch, tmp_path):
    """D-13: a non-existent --output parent directory is auto-created."""
    _patch_fake_pipeline(monkeypatch)
    out_path = tmp_path / "nested" / "does_not_exist_yet" / "out.csv"
    assert not out_path.parent.exists()

    result = cli.main(
        ["--sector", "Technology", "--universe", "sp500", "--output", str(out_path)]
    )

    assert result == 0
    assert out_path.exists()
