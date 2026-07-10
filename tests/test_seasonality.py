"""Tests for scanner.seasonality — Phase 5 (SEAS-01..05), Phase 6 (SEAS-06..09, 14..15)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanner.core import SECTOR_ETF_MAP
from scanner.seasonality import (
    SeasonalityResult,
    bootstrap_week_ci,
    check_thin_data,
    compute_log_returns,
    resolve_sector,
    resolve_sector_universe,
    universe_path,
    valid_sectors,
    validate_history,
    load_sector_dataset,
    week_observed_stats,
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


# ── compute_log_returns ──────────────────────────────────────────────────────

def test_seasonality_result_instantiates_with_seven_fields():
    result = SeasonalityResult(
        sector="Technology",
        universe="sp500",
        baseline_mean_bps=1.5,
        n_years=6,
        bootstrap_iters=1000,
        seed=42,
    )
    assert result.sector == "Technology"
    assert result.universe == "sp500"
    assert result.baseline_mean_bps == 1.5
    assert result.n_years == 6
    assert result.bootstrap_iters == 1000
    assert result.seed == 42
    assert isinstance(result.weeks, pd.DataFrame)
    assert result.weeks.empty


def test_compute_log_returns_columns_and_values():
    close = [100.0, 101.0, 102.51, 100.0]
    idx = pd.date_range("2024-01-02", periods=len(close), freq="B")
    df = pd.DataFrame({"Close": close}, index=idx)

    panel = compute_log_returns({"AAA": df})

    assert panel.columns.tolist() == ["ticker", "date", "iso_year", "iso_week", "log_ret_bps"]
    # Leading NaN row dropped: one fewer row than the input frame.
    assert len(panel) == len(df) - 1

    expected = np.log(pd.Series(close)).diff().dropna().to_numpy() * 10_000
    assert panel["log_ret_bps"].to_numpy() == pytest.approx(expected)
    assert (panel["ticker"] == "AAA").all()


def test_compute_log_returns_pooling_two_tickers_sums_row_counts():
    df_a = _synthetic_frame("2024-01-02", 10)
    df_b = _synthetic_frame("2024-01-02", 15)

    panel = compute_log_returns({"AAA": df_a, "BBB": df_b})

    assert len(panel) == (len(df_a) - 1) + (len(df_b) - 1)
    assert set(panel["ticker"].unique()) == {"AAA", "BBB"}


def test_compute_log_returns_isocalendar_week53_merged_into_52():
    # 2020-12-28 is ISO week 53 of ISO year 2020 (Gregorian year still 2020).
    idx = pd.date_range("2020-12-21", periods=10, freq="B")
    df = pd.DataFrame({"Close": np.linspace(100.0, 110.0, len(idx))}, index=idx)

    panel = compute_log_returns({"AAA": df})

    assert not (panel["iso_week"] == 53).any()
    dec_28_row = panel[panel["date"] == pd.Timestamp("2020-12-28")]
    assert not dec_28_row.empty
    assert (dec_28_row["iso_week"] == 52).all()
    assert (dec_28_row["iso_year"] == 2020).all()


def test_compute_log_returns_isocalendar_year_boundary_maps_to_next_iso_year():
    # 2019-12-30 is ISO year 2020, ISO week 1 (Gregorian year still 2019).
    idx = pd.date_range("2019-12-23", periods=10, freq="B")
    df = pd.DataFrame({"Close": np.linspace(50.0, 55.0, len(idx))}, index=idx)

    panel = compute_log_returns({"AAA": df})

    dec_30_row = panel[panel["date"] == pd.Timestamp("2019-12-30")]
    assert not dec_30_row.empty
    assert (dec_30_row["iso_year"] == 2020).all()
    assert (dec_30_row["iso_week"] == 1).all()


# ── week_observed_stats ───────────────────────────────────────────────────────

def _build_week_panel() -> pd.DataFrame:
    """Hand-computable panel: week 10 is uniformly +50 bps across two years,
    week 20 is uniformly -50 bps across two years — pooled mean is 0.0 bps.
    """
    rows = []
    for year in (2021, 2022):
        for _ in range(4):
            rows.append({"ticker": "AAA", "iso_year": year, "iso_week": 10, "log_ret_bps": 50.0})
        for _ in range(4):
            rows.append({"ticker": "AAA", "iso_year": year, "iso_week": 20, "log_ret_bps": -50.0})
    panel = pd.DataFrame(rows)
    panel["date"] = pd.date_range("2021-01-01", periods=len(panel))
    return panel


def test_week_observed_stats_columns_exact():
    panel = _build_week_panel()
    stats = week_observed_stats(panel)
    assert stats.columns.tolist() == [
        "week",
        "mean_daily_ret_bps",
        "median_bps",
        "std_bps",
        "n_obs",
        "n_years",
        "delta_vs_baseline_bps",
    ]


def test_week_observed_stats_week10_mean_n_obs_n_years_and_baseline_delta():
    panel = _build_week_panel()
    stats = week_observed_stats(panel)

    week10 = stats[stats["week"] == 10].iloc[0]
    assert week10["mean_daily_ret_bps"] == pytest.approx(50.0)
    assert week10["n_obs"] == 8  # 4 obs/year * 2 years
    assert week10["n_years"] == 2
    # Pooled full-sample baseline is 0.0 bps (week 10 at +50, week 20 at -50,
    # equal counts) -> week 10's delta vs baseline == 40.0 per the plan's
    # hand-computable acceptance example structure (baseline here is 0.0, so
    # delta equals the mean itself: 50.0 - 0.0 == 50.0).
    baseline = panel["log_ret_bps"].mean()
    assert baseline == pytest.approx(0.0)
    assert week10["delta_vs_baseline_bps"] == pytest.approx(50.0)


def test_week_observed_stats_baseline_delta_matches_plan_hand_computed_example():
    # Week 10 uniformly +50 bps (2 obs); 8 other obs at 0.0 bps -> pooled
    # baseline = (2*50 + 8*0) / 10 == 10.0 bps -> week 10's delta == 40.0.
    rows = [{"ticker": "AAA", "iso_year": 2021, "iso_week": 10, "log_ret_bps": 50.0}] * 2
    rows += [{"ticker": "AAA", "iso_year": 2021, "iso_week": 30, "log_ret_bps": 0.0}] * 8
    panel = pd.DataFrame(rows)
    panel["date"] = pd.date_range("2021-01-01", periods=len(panel))

    stats = week_observed_stats(panel)
    baseline = panel["log_ret_bps"].mean()
    assert baseline == pytest.approx(10.0)

    week10 = stats[stats["week"] == 10].iloc[0]
    assert week10["delta_vs_baseline_bps"] == pytest.approx(40.0)


def test_week_observed_stats_sorted_ascending_by_week():
    panel = _build_week_panel()
    stats = week_observed_stats(panel)
    assert stats["week"].tolist() == sorted(stats["week"].tolist())


# ── check_thin_data ──────────────────────────────────────────────────────────

def _panel_with_years(years: list[int]) -> pd.DataFrame:
    """Minimal panel with one row per year, columns check_thin_data needs."""
    return pd.DataFrame(
        {
            "ticker": "AAA",
            "iso_year": years,
            "iso_week": 1,
            "log_ret_bps": 0.0,
        }
    )


def test_check_thin_data_four_years_raises():
    panel = _panel_with_years([2020, 2021, 2022, 2023])
    with pytest.raises(ValueError) as excinfo:
        check_thin_data(panel)
    message = str(excinfo.value)
    assert "4" in message
    assert "5" in message


def test_check_thin_data_five_years_returns_none():
    panel = _panel_with_years([2019, 2020, 2021, 2022, 2023])
    assert check_thin_data(panel) is None


def test_check_thin_data_twenty_years_returns_none():
    panel = _panel_with_years(list(range(2000, 2020)))
    assert check_thin_data(panel) is None


def test_check_thin_data_custom_min_years_honored():
    panel = _panel_with_years([2020, 2021, 2022, 2023])
    assert check_thin_data(panel, min_years=3) is None


def test_check_thin_data_dataset_wide_not_per_ticker():
    # Two tickers, each with only 2 distinct years individually, but 4 distinct
    # years combined across the whole panel -> still below the 5-year floor.
    rows = []
    for ticker, years in (("AAA", [2020, 2021]), ("BBB", [2022, 2023])):
        for year in years:
            rows.append(
                {"ticker": ticker, "iso_year": year, "iso_week": 1, "log_ret_bps": 0.0}
            )
    panel = pd.DataFrame(rows)
    with pytest.raises(ValueError):
        check_thin_data(panel)


# ── bootstrap_week_ci ─────────────────────────────────────────────────────────

def _build_bootstrap_panel(
    n_years: int, n_tickers: int, weeks: list[int], seed: int, noise_std_bps: float = 50.0
) -> pd.DataFrame:
    """Random-noise panel spanning `n_years` distinct ISO years for
    reproducibility/seed-sensitivity tests (variance across years so the
    bootstrap CI has nonzero width)."""
    rng = np.random.default_rng(seed)
    rows = []
    base_year = 2000
    for year_offset in range(n_years):
        year = base_year + year_offset
        for ticker_idx in range(n_tickers):
            for week in weeks:
                for _day in range(5):  # 5 obs per ticker-week-year
                    rows.append(
                        {
                            "ticker": f"T{ticker_idx}",
                            "iso_year": year,
                            "iso_week": week,
                            "log_ret_bps": rng.normal(0.0, noise_std_bps),
                        }
                    )
    panel = pd.DataFrame(rows)
    panel["date"] = pd.date_range("2000-01-01", periods=len(panel))
    return panel


def test_bootstrap_ci_columns_exact():
    panel = _build_bootstrap_panel(n_years=6, n_tickers=5, weeks=[1, 2, 3], seed=1)
    result = bootstrap_week_ci(panel, iters=200, seed=42)
    assert result.columns.tolist() == ["week", "ci_low_bps", "ci_high_bps", "significant"]


def test_bootstrap_ci_reproducible_same_seed():
    panel = _build_bootstrap_panel(n_years=6, n_tickers=5, weeks=[1, 2, 3], seed=1)
    result_a = bootstrap_week_ci(panel, iters=200, seed=42)
    result_b = bootstrap_week_ci(panel, iters=200, seed=42)
    pd.testing.assert_frame_equal(result_a, result_b)


def test_bootstrap_ci_different_seed_differs():
    panel = _build_bootstrap_panel(n_years=6, n_tickers=5, weeks=[1, 2, 3], seed=1)
    result_42 = bootstrap_week_ci(panel, iters=200, seed=42)
    result_7 = bootstrap_week_ci(panel, iters=200, seed=7)
    assert not result_42["ci_low_bps"].equals(result_7["ci_low_bps"])


def _build_no_variance_panel(n_years: int, week_means: dict[int, float]) -> pd.DataFrame:
    """Panel where each week's value is IDENTICAL across every year (zero
    across-year variance), so the year-block bootstrap CI collapses to a
    single deterministic point per week -- an exact, non-flaky way to test
    the significance boundary rule."""
    rows = []
    base_year = 2000
    for year_offset in range(n_years):
        year = base_year + year_offset
        for week, mean_bps in week_means.items():
            rows.append(
                {"ticker": "AAA", "iso_year": year, "iso_week": week, "log_ret_bps": mean_bps}
            )
    panel = pd.DataFrame(rows)
    panel["date"] = pd.date_range("2000-01-01", periods=len(panel))
    return panel


def test_bootstrap_ci_significance_rule():
    # week 10 strongly negative, week 20 flat (delta exactly 0 by construction),
    # week 30 strongly positive -- baseline = (-500 + 0 + 500) / 3 == 0.0.
    panel = _build_no_variance_panel(
        n_years=6, week_means={10: -500.0, 20: 0.0, 30: 500.0}
    )
    result = bootstrap_week_ci(panel, iters=200, seed=42)

    week10 = result[result["week"] == 10].iloc[0]
    week20 = result[result["week"] == 20].iloc[0]

    assert week10["ci_high_bps"] < 0
    assert week10["significant"] == True  # noqa: E712 (numpy bool, explicit compare)

    assert week20["ci_low_bps"] <= 0 <= week20["ci_high_bps"]
    assert week20["significant"] == False  # noqa: E712


def test_bootstrap_ci_iters_zero_raises():
    panel = _build_bootstrap_panel(n_years=6, n_tickers=2, weeks=[1], seed=1)
    with pytest.raises(ValueError):
        bootstrap_week_ci(panel, iters=0, seed=42)


def test_bootstrap_ci_iters_negative_raises():
    panel = _build_bootstrap_panel(n_years=6, n_tickers=2, weeks=[1], seed=1)
    with pytest.raises(ValueError):
        bootstrap_week_ci(panel, iters=-5, seed=42)
