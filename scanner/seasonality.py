"""Phase 5 (SEAS-01..05) — Weekly Seasonality Analyzer data-loading pipeline.

Validates the requested sector name, resolves a universe file to a ticker
list, filters that list to the sector via the sector_store cache, validates
each ticker has enough cached daily OHLCV history, and hands back a clean
{ticker: DataFrame} set plus a skip report. Holds all Phase 5 logic; the
root seasonality_by_week.py CLI (Plan 03) stays thin. See
.planning/phases/05-sector-resolution-data-input/05-CONTEXT.md.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

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
