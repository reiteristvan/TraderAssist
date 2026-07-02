# Technology Stack

**Analysis Date:** 2026-07-02

## Languages

**Primary:**
- Python 3.13.7 — scanner engine, CLI, backtesting, signal pipeline (`scan.py`, `scanner/`)
- JavaScript (Node.js) — REST API server (`web/api/`)
- TypeScript 4.8.2 — Angular SPA frontend (`web/ui/`)

**Secondary:**
- SQL — all database queries isolated in `scanner/store_db.py`

## Runtime

**Environment:**
- Python 3.13.7 — engine and CLI
- Node.js 22.18.0 — Express API

**Package Manager:**
- pip — Python dependencies; lockfile: not present (requirements.txt only)
- npm 11.5.2 — Node/Angular; lockfile: `web/api/package-lock.json`, `web/ui/package-lock.json`

## Frameworks

**Core (Python):**
- pandas 3.0.2 — OHLCV data manipulation, signal calculations
- numpy 2.4.4 — numerical operations
- ta 0.11.0 — technical analysis indicators (MACD, RSI, ATR, etc.)
- pyarrow 24.0.0 — Parquet file read/write for OHLCV and earnings cache

**API:**
- Express 4.21.2 — HTTP server (`web/api/server.js`, `web/api/app.js`)
- better-sqlite3 11.10.0 — synchronous SQLite client for Express

**Frontend:**
- Angular 15.0.x — SPA framework (`web/ui/`)
- lightweight-charts 4.2.3 — TradingView-style candlestick/OHLCV charts
- RxJS 7.5.x — reactive streams in Angular

**Testing:**
- pytest 9.1.0 + pytest-cov 7.1.0 — Python unit/integration tests (`tests/`)
- Jest 29.7.0 + supertest 7.1.0 — Express API tests (`web/api/tests/`)
- Karma 6.4.x + Jasmine 4.5.x — Angular component tests (`web/ui/`)

**Build/Dev:**
- Angular CLI 15.0.1 — UI build and dev server (`ng serve`, `ng build`)
- dotenv 16.4.7 — environment variable loading for Express

## Key Dependencies

**Critical:**
- `yfinance` 1.2.1 — sole price data source; imported ONLY in `scanner/data_store.py` and `scanner/earnings_store.py`
- `pandas_market_calendars` 5.4.0 — market trading day calendar logic
- `better-sqlite3` ^11.10.0 — synchronous SQLite; all API DB access via this client
- `pyarrow` 24.0.0 — Parquet cache layer for OHLCV and earnings data

**Infrastructure:**
- `lxml` 6.1.1 — HTML/XML parsing (used by yfinance internally)
- `cors` ^2.8.5 — CORS middleware; API allows only `http://localhost:4200`
- `tslib` ^2.3.0 — TypeScript runtime helpers
- `zone.js` ~0.12.0 — Angular change detection

## Configuration

**Environment:**
- Express reads env vars via `dotenv` from `web/api/.env` (`.env.example` present)
- Key config: `PORT` (default 3000), `DB_PATH` (path to `data/scanner.db`)
- Angular: no runtime environment files detected; API base URL appears hardcoded to `http://localhost:3000`

**Build:**
- Python: `pyproject.toml` sets `pythonpath = ["."]` for pytest
- Angular: `web/ui/angular.json` — output to `dist/ui`, target ES2022, strict TypeScript
- TypeScript: `web/ui/tsconfig.json` — strict mode, ES2022 module/target, `experimentalDecorators: true`

## Platform Requirements

**Development:**
- Python 3.13+ on Windows (Windows reserved names filtered at universe load time)
- Node.js 22.x + npm 11.x
- Chrome — required for Karma/Angular test runner (`karma-chrome-launcher`)
- SQLite — embedded, no separate DB server needed

**Production:**
- No deployment config detected; designed for local / personal use
- Engine: `python scan.py worker --once` for background job processing
- API: `node web/api/server.js` on port 3000
- UI: `ng serve` (dev) or `ng build` + static hosting on port 4200

---

*Stack analysis: 2026-07-02*
