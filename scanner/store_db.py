"""E9 — Owns ALL SQL; data/scanner.db (SQLite, Postgres-swappable).

Single module owning the DB connection and every SQL statement: signals,
runs, and backtest_reports tables, plus migrate(). See CLAUDE.md EPIC E9.1.
"""
