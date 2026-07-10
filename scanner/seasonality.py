"""Phase 5 (SEAS-01..05) — Weekly Seasonality Analyzer data-loading pipeline.

Validates the requested sector name, resolves a universe file to a ticker
list, filters that list to the sector via the sector_store cache, validates
each ticker has enough cached daily OHLCV history, and hands back a clean
{ticker: DataFrame} set plus a skip report. Holds all Phase 5 logic; the
root seasonality_by_week.py CLI (Plan 03) stays thin. See
.planning/phases/05-sector-resolution-data-input/05-CONTEXT.md.

Phase 6 (SEAS-06..09, 14..15) extends this same module with the statistics
stage: pooling every admitted ticker's daily log returns into one ISO-week/
ISO-year-tagged panel (`compute_log_returns`) and computing observed per-week
mean/median/std/n_obs/n_years plus each week's delta vs. the pooled
full-sample baseline (`week_observed_stats`). See
.planning/phases/06-seasonality-statistics-verification/06-CONTEXT.md.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scanner.core import SECTOR_ETF_MAP
from scanner.universe import load_universe_file
from scanner import sector_store

_log = logging.getLogger("scanner.seasonality")

_UNIVERSE_PATHS = {
    "sp400": Path("universes/sp400.txt"),
    "sp500": Path("universes/sp500.txt"),
    "sp600": Path("universes/sp600.txt"),
    "all": Path("universes/sp_all.txt"),
}

_MIN_HISTORY_DAYS = 730

# Separate, higher bar than the 2-year admission floor above (_MIN_HISTORY_DAYS):
# this gates the bootstrap's statistical validity, not ticker admission (D-05).
_MIN_BOOTSTRAP_YEARS = 5

# D-03/D-04: defaults live in the engine, keeping the CLI thin.
_DEFAULT_BOOTSTRAP_ITERS = 1000
_DEFAULT_SEED = 42

# WR-02: a documented sane ceiling on user-supplied --bootstrap-iters. Without
# it, a large/typo'd value drives a (iters, n_years)/(iters, 52)-shaped
# allocation straight to an unhandled MemoryError/_ArrayMemoryError instead of
# the descriptive ValueError-with-message path every other validation in this
# module uses.
_MAX_BOOTSTRAP_ITERS = 100_000


@dataclass
class SectorDataset:
    sector: str
    universe: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SeasonalityResult:
    """Final Phase 6 output shape (populated by Plan 03's orchestrator).

    `weeks` carries the per-week DataFrame (week_observed_stats plus
    bootstrap CI/significance columns added by later plans).
    """

    sector: str
    universe: str
    baseline_mean_bps: float
    n_years: int
    bootstrap_iters: int
    seed: int
    weeks: pd.DataFrame = field(default_factory=pd.DataFrame)


def valid_sectors() -> list[str]:
    """Return the canonical GICS sector names, sorted."""
    return sorted(SECTOR_ETF_MAP.keys())


def resolve_sector(sector_arg: str) -> str:
    """Canonicalize a user-supplied sector name, case-insensitively.

    Raises ValueError listing all valid GICS sector names on miss (SEAS-02).
    """
    lookup = {name.lower(): name for name in SECTOR_ETF_MAP.keys()}
    canonical = lookup.get(sector_arg.strip().lower())
    if canonical is None:
        raise ValueError(
            f"Unknown sector '{sector_arg}'. Valid GICS sectors: "
            + ", ".join(valid_sectors())
        )
    return canonical


def universe_path(universe_arg: str) -> Path:
    """Map a --universe arg to a fixed whitelisted path.

    Never interpolates the raw arg into a Path — the whitelist is the
    path-traversal mitigation (T-05-03).
    """
    path = _UNIVERSE_PATHS.get(universe_arg.strip().lower())
    if path is None:
        raise ValueError(
            f"Unknown universe '{universe_arg}'. Valid: sp400, sp500, sp600, all"
        )
    return path


def resolve_sector_universe(
    sector: str, tickers: list[str]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Filter tickers to those whose cached sector matches `sector`.

    Returns (matched, skipped). A ticker whose sector can't be resolved is
    recorded in skipped with reason 'unresolved-sector' (D-03 skip-not-fail).
    A ticker resolved to a *different* sector is dropped silently — it is
    not a skip, just a non-match.
    """
    matched: list[str] = []
    skipped: list[tuple[str, str]] = []
    for ticker in tickers:
        try:
            ticker_sector = sector_store.get_sector(ticker)
        except Exception as exc:
            _log.warning("resolve_sector_universe: %s failed: %s", ticker, exc)
            skipped.append((ticker, "unresolved-sector"))
            continue

        if ticker_sector is None:
            skipped.append((ticker, "unresolved-sector"))
        elif ticker_sector == sector:
            matched.append(ticker)
        # else: different sector — drop silently, not a skip

    return matched, skipped


def validate_history(
    tickers: list[str],
    years: int | None = None,
    as_of: date | None = None,
) -> tuple[dict[str, pd.DataFrame], list[tuple[str, str]]]:
    """Validate each ticker has >= 2 years of raw cached history (SEAS-04).

    A missing/corrupt cache (get_history returns None) is skipped with
    reason 'no-data' (SEAS-05) rather than aborting the batch. The >=2yr
    admission check runs on the RAW cached history, independent of
    `years` (D-05/D-06); `years`, if given, only trims an admitted frame
    afterward.
    """
    from scanner.data_store import get_history

    frames: dict[str, pd.DataFrame] = {}
    skipped: list[tuple[str, str]] = []

    for ticker in tickers:
        try:
            df = get_history(ticker, end=as_of)
            if df is None:
                skipped.append((ticker, "no-data"))
                continue

            span_days = (df.index.max() - df.index.min()).days
            if span_days < _MIN_HISTORY_DAYS:
                skipped.append((ticker, "insufficient-history"))
                continue

            if years is not None:
                cutoff = df.index.max() - pd.DateOffset(years=years)
                df = df[df.index >= cutoff]

            frames[ticker] = df
        except Exception as exc:
            _log.warning("validate_history: %s failed: %s", ticker, exc)
            skipped.append((ticker, "error"))

    _log.info("validate_history: %d admitted, %d skipped", len(frames), len(skipped))
    return frames, skipped


def load_sector_dataset(
    sector: str,
    universe: str,
    years: int | None = None,
    as_of: date | None = None,
) -> SectorDataset:
    """Resolve sector + universe, filter to sector, validate history.

    Validates the sector FIRST so an invalid sector raises before any
    universe/history work is done (SEAS-02 "without running any analysis").
    """
    canonical = resolve_sector(sector)
    path = universe_path(universe)
    tickers = load_universe_file(path)
    matched, skipped_sector = resolve_sector_universe(canonical, tickers)
    frames, skipped_hist = validate_history(matched, years=years, as_of=as_of)
    return SectorDataset(
        sector=canonical,
        universe=universe.lower(),
        frames=frames,
        skipped=skipped_sector + skipped_hist,
    )


def compute_log_returns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Pool every ticker's daily log return into one ISO-tagged panel (SEAS-06).

    Returns a long panel with columns [ticker, date, iso_year, iso_week,
    log_ret_bps]. For each ticker, log_ret_bps = np.log(Close).diff() * 10_000;
    the leading NaN row (one per ticker) is dropped. Week 53 is remapped to 52
    and the year label is the ISO year from the SAME .isocalendar() call — never
    df.index.year (RESEARCH.md Pitfall 2). All labels derive from the frame's
    own DatetimeIndex; no wall-clock date is read here (CLAUDE.md convention).

    WR-03: a zero or negative `Close` value produces `-inf`/`NaN` (and, on the
    following row, `inf`/`NaN`) rather than a plain `NaN` -- an `inf` poisons
    every downstream sum/mean it touches (in `week_observed_stats` and
    `bootstrap_week_ci`), not just its own row. `-inf`/`inf` are explicitly
    replaced with `NaN` before the leading-NaN dropna below, so any bad
    zero/negative `Close` value is dropped like any other missing row instead
    of silently corrupting every aggregate downstream.
    """
    columns = ["ticker", "date", "iso_year", "iso_week", "log_ret_bps"]
    parts: list[pd.DataFrame] = []

    for ticker, df in frames.items():
        log_ret_bps = np.log(df["Close"]).diff() * 10_000
        log_ret_bps = log_ret_bps.replace([np.inf, -np.inf], np.nan)
        iso = df.index.isocalendar()
        iso_week = iso["week"].where(iso["week"] != 53, 52)
        iso_year = iso["year"]

        part = pd.DataFrame(
            {
                "ticker": ticker,
                "date": df.index,
                "iso_year": iso_year.to_numpy(),
                "iso_week": iso_week.to_numpy(),
                "log_ret_bps": log_ret_bps.to_numpy(),
            }
        )
        # Multi-day internal gaps within a ticker's cached history are not
        # specially handled — an accepted simplification (RESEARCH.md Pitfall 5,
        # no silent smoothing/interpolation). Also drops any inf-derived rows
        # (WR-03, replaced with NaN above).
        parts.append(part.dropna(subset=["log_ret_bps"]))

    if not parts:
        return pd.DataFrame(columns=columns)

    return pd.concat(parts, ignore_index=True)[columns]


def week_observed_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute pooled per-week mean/median/std/n_obs/n_years (SEAS-06) plus
    each week's delta vs. the pooled full-sample baseline mean (SEAS-07).

    The baseline is the flat mean over EVERY ticker-day row in `panel` (D-01)
    — not an average of per-week means. Only weeks actually present in the
    panel are returned; padding to a fixed 52 rows is Phase 7's concern.
    """
    baseline = panel["log_ret_bps"].mean()

    grouped = panel.groupby("iso_week")["log_ret_bps"].agg(
        mean_daily_ret_bps="mean",
        median_bps="median",
        std_bps="std",
        n_obs="count",
    )
    grouped["n_years"] = panel.groupby("iso_week")["iso_year"].nunique()
    grouped["delta_vs_baseline_bps"] = grouped["mean_daily_ret_bps"] - baseline

    result = grouped.reset_index().rename(columns={"iso_week": "week"})
    result = result.sort_values("week").reset_index(drop=True)
    return result[
        [
            "week",
            "mean_daily_ret_bps",
            "median_bps",
            "std_bps",
            "n_obs",
            "n_years",
            "delta_vs_baseline_bps",
        ]
    ]


def check_thin_data(panel: pd.DataFrame, min_years: int = _MIN_BOOTSTRAP_YEARS) -> None:
    """Abort before any bootstrap work if too few distinct years exist (D-05, SEAS-08).

    Counts distinct `iso_year` values across the WHOLE panel (all tickers
    combined), not per ticker. This is the "abort the whole run" tier — it
    does NOT log-and-continue or append to a skip list, unlike the per-ticker
    tolerances in `validate_history`/`resolve_sector_universe` (different
    philosophy, per 06-CONTEXT.md). Mirrors `resolve_sector`'s descriptive
    ValueError-with-message abort pattern.
    """
    n_distinct = panel["iso_year"].nunique()
    if n_distinct < min_years:
        raise ValueError(
            f"Too few distinct years for an honest bootstrap: found {n_distinct}, "
            f"need >= {min_years}. A bootstrap on fewer resampling blocks is noise "
            "dressed up as statistics."
        )


def bootstrap_week_ci(panel: pd.DataFrame, iters: int, seed: int) -> pd.DataFrame:
    """Year-block percentile bootstrap 95% CI per week for delta-vs-baseline (SEAS-08/09).

    Resamples whole ISO years with replacement (D-02): each iteration draws
    `n_years` year-indices and moves every drawn year's full ticker-day
    cross-section together as one block. The baseline is recomputed from the
    SAME resampled draw each iteration (RESEARCH.md Pitfall 4) — never held
    fixed at the observed value. Significance is a pure CI-excludes-zero rule
    (SEAS-09), no p-value/test statistic. Uses `numpy.random.default_rng`
    (never the legacy global `np.random.seed`) for reproducibility (D-04).
    Raises ValueError before any array is allocated if `iters` is
    non-positive or exceeds `_MAX_BOOTSTRAP_ITERS` (WR-02), or if `seed` is
    negative (WR-01) -- the latter would otherwise only be caught
    incidentally by `numpy.random.default_rng`'s own check, with a raw numpy
    message instead of this module's descriptive-ValueError convention.

    Returns one row per week actually present in the panel, with columns
    [week, ci_low_bps, ci_high_bps, significant, insufficient_years], sorted
    ascending by week. A week absent from at least one distinct year (CR-01
    -- realistic for partial-history tickers, staggered admissions, or a
    small sector) can be selected into a resampled year-block with zero
    observations for that week; `np.nanpercentile` (not `np.percentile`) is
    used so a partial miss across draws no longer poisons the whole column
    into a NaN CI. `insufficient_years` is True only in the (rarer) case
    where EVERY draw missed the week -- the CI is genuinely uncomputable --
    and `significant` is then forced False rather than left to a NaN
    comparison silently reading as "not significant" with no indication
    anything was wrong. Downstream consumers (Phase 7) can therefore
    distinguish "not significant" from "cannot compute a CI."
    """
    if iters <= 0 or iters > _MAX_BOOTSTRAP_ITERS:
        raise ValueError(
            f"bootstrap-iters must be between 1 and {_MAX_BOOTSTRAP_ITERS}, got {iters}"
        )
    if seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed}")

    years = np.sort(panel["iso_year"].unique())
    n_years = len(years)
    year_to_idx = {year: idx for idx, year in enumerate(years)}
    year_idx = panel["iso_year"].map(year_to_idx)

    weeks_present = np.sort(panel["iso_week"].unique())

    sum_mat = np.zeros((n_years, 52))
    cnt_mat = np.zeros((n_years, 52))
    grouped = (
        panel.assign(_year_idx=year_idx)
        .groupby(["_year_idx", "iso_week"])["log_ret_bps"]
        .agg(["sum", "count"])
    )
    for (yi, wk), row in grouped.iterrows():
        sum_mat[yi, wk - 1] = row["sum"]
        cnt_mat[yi, wk - 1] = row["count"]

    rng = np.random.default_rng(seed)
    draw = rng.integers(0, n_years, size=(iters, n_years))

    resampled_sum = sum_mat[draw].sum(axis=1)
    resampled_cnt = cnt_mat[draw].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        resampled_week_mean = np.where(
            resampled_cnt > 0,
            resampled_sum / np.where(resampled_cnt > 0, resampled_cnt, 1),
            np.nan,
        )

    baseline_mean = resampled_sum.sum(axis=1) / resampled_cnt.sum(axis=1)
    delta = resampled_week_mean - baseline_mean[:, None]

    # CR-01: a week absent from at least one distinct year has zero
    # observations for any draw that doesn't happen to select a year
    # containing it, so `delta` can be NaN for some (not necessarily all)
    # draws in that week's column. `np.percentile` returns NaN for the
    # ENTIRE column the moment even a single draw is NaN, regardless of how
    # many valid draws remain -- `np.nanpercentile` is required to avoid
    # that poisoning. `insufficient_years` flags the (rare, but possible)
    # case where EVERY draw missed the week entirely, i.e. the CI is
    # genuinely uncomputable, not just noisier than usual; it is deliberately
    # NOT based on raw "does this week appear in every distinct panel year",
    # since a partial boundary ISO-year fragment (e.g. a handful of trailing
    # December days rolling into the next ISO year) legitimately lacks data
    # for most interior weeks without that being a real support problem.
    all_nan = np.all(np.isnan(delta), axis=0)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN (slice|axis) encountered")
        ci_low, ci_high = np.nanpercentile(delta, [2.5, 97.5], axis=0)
    insufficient_years = all_nan
    significant = ((ci_low > 0) | (ci_high < 0)) & ~insufficient_years

    result = pd.DataFrame(
        {
            "week": np.arange(1, 53),
            "ci_low_bps": ci_low,
            "ci_high_bps": ci_high,
            "significant": significant,
            "insufficient_years": insufficient_years,
        }
    )
    # Only weeks actually present in the panel are returned — a week with no
    # observations in any resampled draw should never yield a spurious CI.
    result = result[result["week"].isin(weeks_present)]
    return result.sort_values("week").reset_index(drop=True)


def compute_seasonality_stats(
    dataset: SectorDataset,
    bootstrap_iters: int | None = None,
    seed: int | None = None,
) -> SeasonalityResult:
    """Assemble the full per-week seasonality result (SEAS-08 orchestrator).

    Composes the four computation stages in sequence, mirroring
    `load_sector_dataset`'s small-functions + validate-first style:
    compute_log_returns -> check_thin_data (raises before any bootstrap work
    on a thin dataset, D-05) -> week_observed_stats -> bootstrap_week_ci. The
    observed and CI frames are merged on `week` into the full SEAS-10 column
    set plus `std_bps` (SEAS-06 needs std carried even though SEAS-10's table
    omits it -- kept here for Phase 7) and `insufficient_years` (CR-01 --
    True when every bootstrap draw missed the week entirely, meaning its CI
    is genuinely uncomputable rather than merely "not significant").
    `bootstrap_iters`/`seed` of None resolve to the D-03/D-04 module
    defaults. Pure function: no I/O, no wall-clock date.
    """
    iters = _DEFAULT_BOOTSTRAP_ITERS if bootstrap_iters is None else bootstrap_iters
    seed_val = _DEFAULT_SEED if seed is None else seed

    panel = compute_log_returns(dataset.frames)
    check_thin_data(panel)

    observed = week_observed_stats(panel)
    ci = bootstrap_week_ci(panel, iters, seed_val)

    weeks = observed.merge(ci, on="week", how="inner")
    weeks = weeks[
        [
            "week",
            "mean_daily_ret_bps",
            "delta_vs_baseline_bps",
            "ci_low_bps",
            "ci_high_bps",
            "median_bps",
            "n_obs",
            "n_years",
            "significant",
            "insufficient_years",
            "std_bps",
        ]
    ].sort_values("week").reset_index(drop=True)

    baseline_mean_bps = panel["log_ret_bps"].mean()
    n_years = panel["iso_year"].nunique()

    return SeasonalityResult(
        sector=dataset.sector,
        universe=dataset.universe,
        baseline_mean_bps=baseline_mean_bps,
        n_years=n_years,
        bootstrap_iters=iters,
        seed=seed_val,
        weeks=weeks,
    )
