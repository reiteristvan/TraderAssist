# Coding Conventions

**Analysis Date:** 2026-07-02

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `data_store.py`, `store_db.py`, `earnings_store.py`)
- Test files: `test_<module_name>.py` (mirrors module in `tests/`)
- JavaScript/TypeScript files: `camelCase.js` for Node API, `kebab-case.component.ts` for Angular components

**Functions:**
- Public Python functions: `snake_case` (e.g., `run_scan`, `make_contexts`, `get_history`)
- Private/internal Python functions: `_snake_case` with underscore prefix (e.g., `_fetch_raw`, `_make_quality_info`, `_sector_strength`, `_bullish_reversal_candle`)
- JavaScript API handlers: `camelCase` inline arrow functions in route handlers

**Variables:**
- Python: `snake_case` throughout
- Constants (module-level thresholds): `UPPER_SNAKE_CASE` (e.g., `TREND_LOOKBACK_HIGH`, `RSI_PULLBACK_RANGE`, `EARNINGS_BUFFER_DAYS`)
- Private module-level vars: `_UPPER_SNAKE_CASE` with leading underscore (e.g., `_DEFAULT_DB`, `_CACHE_DIR`, `_SCHEMA_VERSION`)
- Logger: `_log = logging.getLogger("scanner.<module>")` — always module-scoped private

**Types:**
- Dataclasses preferred over plain dicts for structured data (e.g., `GateLog`, `QualityInfo`, `EvalContext`, `PullbackResult`, `BreakoutResult`, `RefreshReport`, `SizeInfo`, `Signal`, `Trade`)
- `Optional[T]` used for fields that may be `None` (not `T | None` union syntax, despite `from __future__ import annotations`)
- Return type annotations on public functions; private helpers may omit

**Classes:**
- PascalCase throughout (e.g., `GateLog`, `QualityInfo`, `EvalContext`)
- `@dataclass` or `@dataclass(frozen=True)` for data containers; plain class for stateful accumulators (`GateLog`)

## Code Style

**Formatting:**
- No formatter config detected (no `.prettierrc`, no `black` config, no `ruff` config)
- Consistent 4-space indentation in Python
- Blank lines used liberally to separate logical sections within functions

**Section Comments:**
- Sections within a module delimited with `# ── Section Name ──` using em-dash box-drawing characters
- Section comments align at column positions visually (see `scanner/core.py`, `scanner/store_db.py`)
- Test files use the same `# ── Test group label ──` pattern to separate test suites within a file

**Module Docstrings:**
- Every Python module has a top-level docstring explaining Epic number, purpose, and key design decisions
- Example: `"""E1 — Parquet-cached OHLCV. The ONLY module that imports yfinance for prices."""`

**Line Length:**
- No enforced limit; lines commonly run 90–110 chars in module bodies

## Import Organization

**Python order:**
1. `from __future__ import annotations` — always first when present
2. Standard library (alphabetical within group)
3. Third-party (numpy, pandas, yfinance, ta, etc.)
4. Internal (`scanner.*` imports)

**Path Aliases:**
- No path aliases; all internal imports use `scanner.<module>` absolute form (e.g., `from scanner.core import GateLog`)
- Strategies import public symbols from `scanner.core` via explicit named imports (not wildcard)

**JavaScript/Angular:**
- Angular components import from `@angular/core`, `@angular/common/http`, etc.
- API imports use relative `require('../db')`, `require('../app')` patterns

## Error Handling

**Patterns:**
- yfinance calls wrapped in `fetch_with_retry` with exponential back-off (`scanner/data_store.py`)
- Unknown/missing data represented as `None` — callers check `is None` and skip gates rather than failing
- Gate evaluation uses explicit `log.skip(name, reason)` rather than exceptions for data-absent conditions
- Database operations use `sqlite3` without ORM; errors propagate as native exceptions (no custom wrapping)
- `warnings.filterwarnings("ignore", ...)` suppressed at module level for FutureWarning/UserWarning from pandas/yfinance

## Logging

**Framework:** Python `logging` module

**Pattern:**
- Module-level logger: `_log = logging.getLogger("scanner.<module>")`
- Used in `data_store.py` for cache hits/misses and retry events
- Evaluation/strategy code does NOT log — it uses `GateLog.verbose` print mode for diagnostic output
- Web API layer: no structured logging, uses `console.error` only in error paths

## Comments

**When to Comment:**
- Constants: inline comments explaining threshold source or rationale (e.g., `# single definition — imported by both strategies`)
- Design decisions: `# D-01`, `# D-03` tags referencing decisions from planning docs
- Non-obvious math: formulas annotated with plain-language description
- Epic references: `# E2.1`, `# E3.3` tags tying code to feature epics
- `noqa` used sparingly with explicit rule codes (`# noqa: E731`, `# noqa: F841`)

**Docstrings:**
- Public functions: docstrings describing purpose and key behavior
- Private helpers: docstrings when logic is non-trivial
- Dataclass fields: no per-field docstrings; intent conveyed by field names

## Function Design

**Size:** Functions typically 15–60 lines; longer functions (evaluate() in strategies) use `# ── Section ──` comments to divide logical phases

**Parameters:** Keyword arguments with defaults preferred for optional params; no `**kwargs` in core logic

**Return Values:**
- Strategy `evaluate()` always returns a result dataclass (never None)
- Optional results use `Optional[Type]` and callers handle None
- Factory/context functions return `Optional[EvalContext]` when data unavailable

## Module Design

**Exports:**
- No `__all__` declarations; public API is determined by naming (no underscore = public)
- `scanner/__init__.py` and `scanner/strategies/__init__.py` are empty (no re-exports)

**Singleton Pattern:**
- `store_db.py` uses `_DEFAULT_DB = Path("data/scanner.db")` and a module-level connection cache
- `data_store.py` uses module-level `_CACHE_DIR` and `_MARKET_SYMBOLS` constants

**Constants Organization:**
- Thresholds centralized in `scanner/core.py` under `# ── Thresholds (E2.3) ──` section
- Strategy files import specific constants by name from `scanner.core` — never redefine

## Key Invariants to Preserve

- **No `yf.` imports** outside `scanner/data_store.py` and `scanner/earnings_store.py`
- **No `datetime.now()` / `pd.Timestamp.now()`** inside evaluation logic — use `ctx.as_of`
- **No gate threshold changes** without an explicit task backed by data
- **Single source of truth**: `EARNINGS_BUFFER_DAYS` defined once in `scanner/core.py`, imported by both strategies (never duplicated)
- **All SQL in `store_db.py`** — no SQL strings in any other module
- **Schema version bump required** for any new DB column (`_SCHEMA_VERSION` in `store_db.py`)

---

*Convention analysis: 2026-07-02*
