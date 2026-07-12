"""Standalone subprocess helper for the cp1252 stream-encoding regression test.

Not collected by pytest (leading underscore keeps it outside the ``test_*.py``
discovery pattern). Invoked directly as a subprocess by
``tests/test_seasonality_cli.py::test_main_output_survives_cp1252_stream_encoding``
so the confirmation print in ``seasonality_by_week.py`` runs through a real,
non-capsys stream bound to cp1252 (see 07-VERIFICATION.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Insert the repository root (parent of tests/) at the front of sys.path so
# `scanner` and `seasonality_by_week` import correctly when this file is run
# directly, outside pytest's `pythonpath` config.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import seasonality_by_week as cli
from scanner import seasonality
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


def main() -> int:
    out_path = sys.argv[1]

    fake_ds = SectorDataset(
        sector="Technology",
        universe="sp500",
        frames={"AAPL": _tiny_frame()},
        skipped=[],
    )

    def _fake_load(sector, universe, years=None, as_of=None):
        return fake_ds

    def _fake_compute(dataset, bootstrap_iters=None, seed=None):
        return _fake_result()

    seasonality.load_sector_dataset = _fake_load
    seasonality.compute_seasonality_stats = _fake_compute

    return cli.main(
        ["--sector", "Technology", "--universe", "sp500", "--output", out_path]
    )


if __name__ == "__main__":
    sys.exit(main())
