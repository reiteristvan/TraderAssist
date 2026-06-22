"""E10 — Universe builder + audit.

Builds ticker universes from index constituent tables (Wikipedia) or a
holdings CSV, and audits a universe file for unfetchable tickers.
See CLAUDE.md EPIC E10.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

_log = logging.getLogger("scanner.universe")

_WIKIPEDIA_URLS = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}

_TICKER_COLS = ("Symbol", "Ticker", "Ticker symbol")  # column names to try


def _normalize(ticker: str) -> str:
    """Normalize ticker: strip whitespace, uppercase, replace dots with dashes."""
    return ticker.strip().upper().replace(".", "-")


def build_universe(index: str, out_path: Optional[Path] = None) -> list[str]:
    """Scrape Wikipedia for S&P index constituents and return normalized tickers.

    Writes results to out_path if given (one ticker per line, with a
    generated-on comment header). Returns the sorted list of tickers.
    """
    import pandas as pd

    url = _WIKIPEDIA_URLS.get(index.lower())
    if url is None:
        raise ValueError(f"Unknown index: {index!r}. Choose from {list(_WIKIPEDIA_URLS)}")

    _log.info("Fetching %s constituents from Wikipedia...", index)
    tables = pd.read_html(url)

    tickers: list[str] = []
    for table in tables:
        # Find first table that has a recognized ticker column
        for col in _TICKER_COLS:
            if col in table.columns:
                raw = table[col].dropna().astype(str).tolist()
                tickers = sorted({_normalize(t) for t in raw if t and t.upper() != col.upper()})
                break
        if tickers:
            break

    if not tickers:
        raise RuntimeError(f"Could not find a ticker column in any table at {url}")

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import datetime
        lines = [
            f"# Generated {datetime.date.today()} — {index.upper()} constituents (Wikipedia)",
            *tickers,
        ]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _log.info("Wrote %d tickers to %s", len(tickers), out_path)

    return tickers


def audit_universe(file_path: Path) -> dict:
    """Check each ticker in a universe file for fetchable history.

    Returns dict with keys 'ok', 'failed' (list of (ticker, error) tuples).
    Failed tickers are non-fatal — the rest of the universe is unaffected.
    """
    from scanner.data_store import refresh_universe

    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    tickers = [
        l.strip().upper()
        for l in lines
        if l.strip() and not l.startswith("#")
    ]

    _log.info("Auditing %d tickers from %s...", len(tickers), file_path)
    report = refresh_universe(tickers, pause=0.1)

    return {
        "ok": report.succeeded + report.invalidated,
        "failed": report.failed,
    }


def load_universe_file(path: Path) -> list[str]:
    """Read a universe text file (# comment lines ignored)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [
        l.strip().upper()
        for l in lines
        if l.strip() and not l.startswith("#")
    ]
