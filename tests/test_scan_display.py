"""Tests for _print_scan_results industry column display — Phase 03 Plan 01.

Covers: Industry / Mom / Trend / Rank% columns added between confidence and close.
All tests are fully offline — no yfinance, no DB, no filesystem reads.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from scan import _print_scan_results


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_row(
    ticker: str,
    strategy: str = "pullback",
    score: float = 75.0,
    confidence: str = "HIGH",
    industry_group=None,
    industry_momentum=None,
    industry_above_50ma=None,
    industry_rank_pct=None,
    close: float = 150.0,
    suggested_stop: float = 145.0,
    suggested_target: float = 160.0,
    risk_reward: float = 2.0,
    qualified: bool = True,
) -> dict:
    return dict(
        ticker=ticker,
        strategy=strategy,
        score=score,
        confidence=confidence,
        industry_group=industry_group,
        industry_momentum=industry_momentum,
        industry_above_50ma=industry_above_50ma,
        industry_rank_pct=industry_rank_pct,
        close=close,
        suggested_stop=suggested_stop,
        suggested_target=suggested_target,
        risk_reward=risk_reward,
        qualified=qualified,
    )


# ── tests ──────────────────────────────────────────────────────────────────────

def test_print_scan_results_industry_columns(capsys):
    """Industry / Mom / Trend / Rank% appear in CLI output with correct formatting.

    Three rows:
      1. Positive-momentum row  — industry_momentum=5.2, industry_above_50ma=1, rank=18
      2. Negative-momentum row  — industry_momentum=-3.1, industry_above_50ma=0, rank=62
      3. All-NULL industry row  — all four fields None / NaN
    """
    rows = [
        _make_row(
            ticker="AAPL",
            industry_group="Semiconductors & Semiconductor Equipment Industry",
            industry_momentum=5.2,
            industry_above_50ma=1,
            industry_rank_pct=18.0,
        ),
        _make_row(
            ticker="BAC",
            industry_group="Banks Regional",
            industry_momentum=-3.1,
            industry_above_50ma=0,
            industry_rank_pct=62.0,
        ),
        _make_row(
            ticker="XYZ",
            industry_group=None,
            industry_momentum=float("nan"),
            industry_above_50ma=None,
            industry_rank_pct=None,
        ),
    ]
    df = pd.DataFrame(rows)

    _print_scan_results(df)
    out = capsys.readouterr().out

    # Header tokens must be present
    assert "Industry" in out, "Column header 'Industry' not found in CLI output"
    assert "Mom" in out, "Column header 'Mom' not found in CLI output"
    assert "Trend" in out, "Column header 'Trend' not found in CLI output"
    assert "Rank%" in out, "Column header 'Rank%' not found in CLI output"

    # Positive momentum formatting (D-02)
    assert "+5.2%" in out, "Positive momentum '+5.2%' not found in CLI output"

    # Negative momentum formatting (D-02)
    assert "-3.1%" in out, "Negative momentum '-3.1%' not found in CLI output"

    # Trend arrows (D-03)
    assert "↑" in out, "Up-arrow '↑' (U+2191) not found in CLI output"
    assert "↓" in out, "Down-arrow '↓' (U+2193) not found in CLI output"

    # Rank percent formatting (D-04)
    assert "Top 18%" in out, "'Top 18%' rank display not found in CLI output"

    # NULL row must render em dash (U+2014), not raw Python/float values (D-10)
    em_dash = "—"
    assert em_dash in out, "Em dash '—' (U+2014) not found in CLI output for NULL row"

    # Raw stored values must NOT leak for the NULL row
    assert "None" not in out, "Raw 'None' text leaked for NULL industry field"
    # 0.0 is the raw float representation — it must NOT appear as a literal in output
    # (Note: 0 as integer is a valid industry_above_50ma value, but NaN/None → '—')
    # We check that '0.0' does not appear (NaN formatted as float would look like nan/0.0)
    assert "nan" not in out.lower(), "Raw 'nan' text leaked for NULL industry field"
