"""Tests for scanner.universe — E10.

Tests use synthetic data; no network calls.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scanner.universe import _normalize, load_universe_file


def test_normalize_dots_to_dashes():
    assert _normalize("BRK.B") == "BRK-B"


def test_normalize_uppercase():
    assert _normalize("aapl") == "AAPL"


def test_normalize_strips_whitespace():
    assert _normalize("  MSFT  ") == "MSFT"


def test_normalize_brk_b():
    assert _normalize("BRK.B") == "BRK-B"


def test_load_universe_file(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("# comment\nAAPL\nMSFT\n\nGOOGL\n", encoding="utf-8")
    tickers = load_universe_file(f)
    assert tickers == ["AAPL", "MSFT", "GOOGL"]


def test_load_universe_file_ignores_comments(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("# Generated 2026-06-22 — SP500\nAAPL\nMSFT\n", encoding="utf-8")
    tickers = load_universe_file(f)
    assert "AAPL" in tickers
    assert not any(t.startswith("#") for t in tickers)


def test_build_universe_scrapes_and_normalizes(tmp_path, monkeypatch):
    """Mock pandas.read_html to return a synthetic table; verify normalization."""
    import scanner.universe as univ

    fake_table = pd.DataFrame({
        "Symbol": ["AAPL", "BRK.B", "msft", "  GOOGL "],
        "Name": ["Apple", "Berkshire", "Microsoft", "Alphabet"],
    })

    monkeypatch.setattr(pd, "read_html", lambda url: [fake_table])

    out_file = tmp_path / "sp500.txt"
    tickers = univ.build_universe("sp500", out_path=out_file)

    assert "AAPL" in tickers
    assert "BRK-B" in tickers  # dot → dash
    assert "MSFT" in tickers   # uppercased
    assert "GOOGL" in tickers  # stripped
    assert out_file.exists()
    content = out_file.read_text()
    assert "# Generated" in content
    assert "BRK-B" in content


def test_build_universe_unknown_index():
    from scanner.universe import build_universe
    with pytest.raises(ValueError, match="Unknown index"):
        build_universe("sp100")


def test_build_universe_no_ticker_column(monkeypatch):
    """Table without a recognized ticker column → RuntimeError."""
    import scanner.universe as univ

    fake = pd.DataFrame({"Company": ["Apple"], "Country": ["US"]})
    monkeypatch.setattr(pd, "read_html", lambda url: [fake])

    with pytest.raises(RuntimeError, match="Could not find a ticker column"):
        univ.build_universe("sp500")
