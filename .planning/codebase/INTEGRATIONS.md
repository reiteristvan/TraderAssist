# External Integrations

**Analysis Date:** 2026-07-02

## APIs & External Services

**Market Data:**
- Yahoo Finance (via yfinance 1.2.1) — sole price/fundamental data source
  - SDK/Client: `yfinance` (`import yfinance as yf`)
  - Auth: none required (public API)
  - Usage: OHLCV price history, ticker `info` dict (sector, industry, market cap)
  - Entry points: `scanner/data_store.py` (`get_market_data()`, `refresh_ticker()`), `scanner/earnings_store.py`
  - Constraint: **No `yf.` imports permitted outside these two modules**

**Industry/Sector ETF Proxies:**
- Standard SPDR / VanEck ETFs (XSD, XSW, XBI, KRE, XRT, XOP, XME, GDX, etc.)
  - Fetched via yfinance; no separate API key needed
  - Mapping defined in `scanner/core.py` (`SECTOR_ETF_MAP`, intended `INDUSTRY_ETF_MAP`)

## Data Storage

**Databases:**
- SQLite via `data/scanner.db`
  - Schema version: 6
  - Tables: `signals`, `runs`, `backtest_reports`, `jobs`, `bars`, `schema_version`
  - All SQL isolated in `scanner/store_db.py` (designed to be swappable to Postgres)
  - Read by Express API via `better-sqlite3`; written exclusively by Python engine
  - Connection (API): `DB_PATH` env var (default inferred from relative path)

**File Storage:**
- Local filesystem Parquet cache
  - OHLCV: `data/ohlcv/{TICKER}.parquet` — managed by `scanner/data_store.py`
  - Earnings dates: `data/earnings/{TICKER}_earnings.parquet` — managed by `scanner/earnings_store.py`
  - Never read directly by the web layer
- Universe text files: `universes/sp400.txt`, `sp500.txt`, `sp600.txt`, `sample.txt`
- Backtest output directories: `runs/{run_id}/`

**Caching:**
- Parquet file cache for OHLCV and earnings data (local disk)
- No in-memory caching layer (Redis/Memcached)

## Authentication & Identity

**Auth Provider:**
- None — personal-use tool; no user authentication

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or similar integration

**Logs:**
- Python: `print()` / `logging` to stdout (no structured logging framework)
- Express: console output only

## CI/CD & Deployment

**Hosting:**
- Local development only — no cloud deployment config detected

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CircleCI, no GitLab CI)

## Environment Configuration

**Required env vars (Express API):**
- `PORT` — HTTP port (default: `3000`)
- `DB_PATH` — absolute or relative path to `data/scanner.db`

**Secrets location:**
- `web/api/.env` (gitignored; `.env.example` committed as reference)
- No secrets required for Python engine (yfinance is unauthenticated)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Internal API Surface (web/api routes)

The Express API exposes read-only endpoints consumed by the Angular UI:

| Route prefix | Router file | Purpose |
|---|---|---|
| `/api/health` | `routes/health.js` | Liveness check |
| `/api/signals` | `routes/signals.js` | Signal listing and filtering |
| `/api/runs` | `routes/runs.js` | Backtest run metadata |
| `/api/journal` | `routes/journal.js` | Live signal journal |
| `/api/stats` | `routes/stats.js` | Aggregate stats |
| `/api/jobs` | `routes/jobs.js` | On-demand diagnose job queue |
| `/api/ohlcv` | `routes/ohlcv.js` | OHLCV bars for chart (from `bars` table) |

CORS: restricted to `http://localhost:4200` only.

---

*Integration audit: 2026-07-02*
