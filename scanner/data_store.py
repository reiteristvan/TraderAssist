"""E1 — Parquet-cached OHLCV. The ONLY module that imports yfinance for prices.

Replaces pullback_filter._fetch_history/prefetch_market_data, breakout_filter._history,
and swing_scanner.fetch_data/fetch_ath. See CLAUDE.md EPIC E1.
"""
