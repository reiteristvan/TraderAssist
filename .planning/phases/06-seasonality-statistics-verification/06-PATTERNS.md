# Phase 6: Seasonality Statistics & Verification - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 3 (all existing files being extended — no brand-new files this phase)
**Analogs found:** 3 / 3 (self-referential — the phase extends its own established module)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `scanner/seasonality.py` (extend: `SeasonalityResult`, `compute_log_returns`, `check_thin_data`, `week_observed_stats`, `bootstrap_week_ci`, `compute_seasonality_stats`) | service/utility (statistical transform) | batch/transform (in-memory DataFrame → DataFrame, no I/O) | Same file's existing `SectorDataset` dataclass + `load_sector_dataset`/`validate_history`/`resolve_sector` | exact (same file, same module conventions) |
| `tests/test_seasonality.py` (add new test functions for SEAS-06/07/08/09/14/15) | test | transform/unit | Same file's existing `_synthetic_frame` helper + test structure | exact (same file, same test conventions) |
| `seasonality_by_week.py` (wire `--bootstrap-iters`/`--seed` into a live call to `compute_seasonality_stats`, print summary) | route/CLI entry | request-response (CLI args → stdout) | Same file's existing `main()` / `build_parser()` | exact (same file, same CLI conventions) |

No wholly new files are introduced by this phase — CONTEXT.md and RESEARCH.md are explicit that Phase 6 extends Phase 5's `scanner/seasonality.py` module and its paired test file, plus wires two already-declared-but-unused CLI args in `seasonality_by_week.py`. There is no controller/component/model/migration file in scope.

## Pattern Assignments

### `scanner/seasonality.py` (service/utility, batch/transform)

**Analog:** the same file's Phase 5 code (`SectorDataset`, `resolve_sector`, `universe_path`, `validate_history`, `load_sector_dataset`) — `D:\Projects\TraderAssist\scanner\seasonality.py`

**Imports pattern** (lines 1-23, `scanner/seasonality.py`):
```python
"""Phase 5 (SEAS-01..05) — Weekly Seasonality Analyzer data-loading pipeline.
...
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
```
Phase 6 additions should extend this same import block (add `numpy as np`), keep the `_log` logger, and add new module docstring content describing the Phase 6 additions (mirrors the file's existing "Phase 5 (SEAS-01..05)" docstring convention — Phase 6 should append a "Phase 6 (SEAS-06..09, 14..15)" section rather than replacing the docstring).

**Dataclass pattern** (lines 32-40):
```python
_MIN_HISTORY_DAYS = 730


@dataclass
class SectorDataset:
    sector: str
    universe: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)
```
Copy this exact shape for the new `SeasonalityResult` dataclass: module-level constant(s) declared just above (`_MIN_BOOTSTRAP_YEARS = 5`, `_DEFAULT_BOOTSTRAP_ITERS = 1000`, `_DEFAULT_SEED = 42`, mirroring `_MIN_HISTORY_DAYS`'s placement/naming style), then a plain `@dataclass` with typed fields, `field(default_factory=...)` for mutable containers, no methods — matches RESEARCH.md's recommended `SeasonalityResult(sector, universe, baseline_mean_bps, n_years, bootstrap_iters, seed, weeks=<DataFrame>)`.

**ValueError-with-message abort pattern** (lines 48-60, `resolve_sector`):
```python
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
```
This is the exact pattern to mirror for `check_thin_data()` (D-05 guard): compute the check up front, raise a plain `ValueError` with a descriptive f-string message (state what was found and what was required) when the condition fails, otherwise return normally (no dedicated return value needed — `check_thin_data` returns `None` per RESEARCH.md's signature). Do NOT log-and-continue here; this is the "abort the whole run" tier, distinct from the skip-not-fail tier below.

**Skip-not-fail / try-except-continue pattern** (lines 106-146, `validate_history`) — NOT used by Phase 6's new thin-data guard (different tier per CONTEXT.md), but useful reference if any per-ticker log-return computation needs to tolerate a bad frame:
```python
for ticker in tickers:
    try:
        df = get_history(ticker, end=as_of)
        if df is None:
            skipped.append((ticker, "no-data"))
            continue
        ...
        frames[ticker] = df
    except Exception as exc:
        _log.warning("validate_history: %s failed: %s", ticker, exc)
        skipped.append((ticker, "error"))

_log.info("validate_history: %d admitted, %d skipped", len(frames), len(skipped))
return frames, skipped
```
Per CONTEXT.md, this "skip, don't fail" philosophy applies to per-ticker gaps, NOT to the new dataset-wide thin-data guard — do not reuse this try/except/append-skip shape for `check_thin_data`; use the `resolve_sector`-style `ValueError` instead.

**Orchestrator/composition pattern** (lines 149-171, `load_sector_dataset`):
```python
def load_sector_dataset(
    sector: str,
    universe: str,
    years: int | None = None,
    as_of: date | None = None,
) -> SectorDataset:
    """Resolve sector + universe, filter to sector, validate history.

    Validates the sector FIRST so an invalid sector raises before any
    universe/history work is done (SEAS-02 "without running any analysis").
    """
    canonical = resolve_sector(sector)
    path = universe_path(universe)
    tickers = load_universe_file(path)
    matched, skipped_sector = resolve_sector_universe(canonical, tickers)
    frames, skipped_hist = validate_history(matched, years=years, as_of=as_of)
    return SectorDataset(
        sector=canonical,
        universe=universe.lower(),
        frames=frames,
        skipped=skipped_sector + skipped_hist,
    )
```
Copy this composition shape for `compute_seasonality_stats(dataset, bootstrap_iters=..., seed=...)`: call small single-purpose functions in sequence (`compute_log_returns` → `check_thin_data` (raises before any bootstrap work, same "validate first" comment convention) → `week_observed_stats` → `bootstrap_week_ci`), then assemble the final dataclass from their outputs. Apply defaults via module constants (`_DEFAULT_BOOTSTRAP_ITERS`, `_DEFAULT_SEED`) the same way `load_sector_dataset` takes `years: int | None = None` and only applies special handling when not None.

**Function decomposition to add** (per RESEARCH.md's Architecture Patterns, directly reusable as the file's new public surface, following the existing one-function-one-responsibility style seen in `resolve_sector`/`universe_path`/`resolve_sector_universe`/`validate_history`):
```python
def compute_log_returns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame: ...
def check_thin_data(panel: pd.DataFrame, min_years: int = _MIN_BOOTSTRAP_YEARS) -> None: ...
def week_observed_stats(panel: pd.DataFrame) -> pd.DataFrame: ...
def bootstrap_week_ci(panel: pd.DataFrame, iters: int, seed: int) -> pd.DataFrame: ...
def compute_seasonality_stats(
    dataset: SectorDataset,
    bootstrap_iters: int = _DEFAULT_BOOTSTRAP_ITERS,
    seed: int = _DEFAULT_SEED,
) -> SeasonalityResult: ...
```

**No datetime.now() convention** — confirmed nowhere in `scanner/seasonality.py` currently; the file already threads `as_of: date | None` explicitly through `validate_history`/`load_sector_dataset` rather than reading wall-clock time. Phase 6 must follow the same explicit-data-driven-date approach (ISO year/week from `.isocalendar()` on the DataFrame index, never `date.today()`).

---

### `tests/test_seasonality.py` (test, unit/transform)

**Analog:** the same file's existing helper and test style — `D:\Projects\TraderAssist\tests\test_seasonality.py`

**Imports pattern** (lines 1-15):
```python
"""Tests for scanner.seasonality — Phase 5 (SEAS-01..05)."""
from __future__ import annotations

import pandas as pd
import pytest

from scanner.core import SECTOR_ETF_MAP
from scanner.seasonality import (
    resolve_sector,
    resolve_sector_universe,
    universe_path,
    valid_sectors,
    validate_history,
    load_sector_dataset,
)
```
Extend this same import list (append `compute_log_returns`, `check_thin_data`, `week_observed_stats`, `bootstrap_week_ci`, `compute_seasonality_stats`, `SeasonalityResult` to the `from scanner.seasonality import (...)` block) rather than adding a second import block. Add `import numpy as np` for RNG-based synthetic panel construction. Update the module docstring to mention Phase 6 (matches the `scanner/seasonality.py` docstring-versioning convention).

**Synthetic-fixture helper pattern** (lines 18-30, `_synthetic_frame`):
```python
def _synthetic_frame(start: str, periods: int) -> pd.DataFrame:
    """Build a synthetic OHLCV frame spanning `periods` business days from `start`."""
    idx = pd.date_range(start=start, periods=periods, freq="B")
    return pd.DataFrame(
        {
            "Open": 1.0,
            "High": 1.0,
            "Low": 1.0,
            "Close": 1.0,
            "Volume": 1000,
        },
        index=idx,
    )
```
This is the direct analog to extend with a new helper (e.g. `_synthetic_panel(n_years, n_tickers, daily_vol_bps, seed, inject_week=None, inject_bps=0.0)`) that builds the RESEARCH.md-verified 20-year/15-ticker/150bps/seed-10 synthetic panel used for SEAS-14/15. Keep it a small, private (`_`-prefixed), single-purpose function local to the test file, same as `_synthetic_frame`, rather than a shared fixture/conftest (RESEARCH.md's Wave 0 Gaps explicitly says "No new fixtures/conftest needed").

**Section-comment-banner test organization** (lines 33, 53, 69, 87, 158):
```python
# ── resolve_sector / valid_sectors ──────────────────────────────────────────
...
# ── universe_path ────────────────────────────────────────────────────────────
...
# ── resolve_sector_universe ──────────────────────────────────────────────────
...
# ── validate_history ──────────────────────────────────────────────────────────
...
# ── load_sector_dataset ───────────────────────────────────────────────────────
```
Append new banner sections in the same style for each new function group: `# ── compute_log_returns ──`, `# ── check_thin_data ──`, `# ── week_observed_stats ──`, `# ── bootstrap_week_ci ──`, `# ── compute_seasonality_stats / synthetic verification ──`.

**Monkeypatch-driven isolation pattern** (lines 71-84, 89-99):
```python
def test_resolve_sector_universe_matched_dropped_skipped(monkeypatch):
    sectors = {"AAPL": "Technology", "JPM": "Financial Services"}

    def fake_get_sector(ticker):
        return sectors.get(ticker)  # XYZ → None

    monkeypatch.setattr("scanner.seasonality.sector_store.get_sector", fake_get_sector)

    matched, skipped = resolve_sector_universe("Technology", ["AAPL", "JPM", "XYZ"])
    ...
```
Phase 6's new tests are pure in-memory DataFrame transforms (no external I/O to mock — `compute_log_returns`/`week_observed_stats`/`bootstrap_week_ci` take `frames`/`panel` directly), so `monkeypatch` is likely NOT needed for most new tests; construct inputs directly via the new synthetic helper instead, matching the plain-assertion style of `test_validate_history_admits_long_history` (lines 89-99) rather than the monkeypatch style, except where `compute_seasonality_stats` is tested via a full `SectorDataset` (still no I/O — a `SectorDataset` can be constructed directly with in-memory frames, no `get_history` mock needed).

**Plain-assertion structural test pattern** (lines 141-155, `test_validate_history_years_trim`):
```python
def test_validate_history_years_trim(monkeypatch):
    long_frame = _synthetic_frame("2020-01-01", 780)  # ~3 years
    ...
    frames, skipped = validate_history(["AAPL"], years=1)
    assert "AAPL" in frames
    trimmed = frames["AAPL"]
    span_days = (trimmed.index.max() - trimmed.index.min()).days
    assert span_days <= 370
    assert skipped == []
```
Use this shape (build input → call function → assert on returned DataFrame's shape/columns/values) for SEAS-06/07 tests (`week_observed_stats` mean/median/std/n_obs/n_years correctness against a hand-computable synthetic panel) and SEAS-08/09 (bootstrap CI reproducibility across two calls with same seed, difference with a different seed, and `ValueError` from `check_thin_data` below 5 distinct years — mirror `test_load_sector_dataset_invalid_sector_raises_before_get_history`'s `pytest.raises(ValueError)` style below).

**pytest.raises pattern** (lines 160-167, `test_load_sector_dataset_invalid_sector_raises_before_get_history`):
```python
def test_load_sector_dataset_invalid_sector_raises_before_get_history(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("get_history called unexpectedly")

    monkeypatch.setattr("scanner.data_store.get_history", _fail)

    with pytest.raises(ValueError):
        load_sector_dataset("Widgets", "sp500")
```
Direct analog for the D-05 thin-data-guard test: construct a panel/dataset with fewer than 5 distinct years, then `with pytest.raises(ValueError): check_thin_data(panel)` (or `compute_seasonality_stats(dataset)` if testing the guard is wired through the full entry point).

**Synthetic verification tests (SEAS-14/15)** — use RESEARCH.md's verified fixed parameters directly (empirically searched and confirmed stable in this environment, safe to hardcode as test constants at module level near the top of the file, alongside `_synthetic_frame`):
```python
N_YEARS = 20
N_TICKERS = 15
DAILY_VOL_BPS = 150
DATA_SEED = 10
BOOTSTRAP_SEED = 42
BOOTSTRAP_ITERS = 1000
```
Pure-noise test asserts `1 <= flagged_count <= 3` (RESEARCH.md found stable 1-2/52, D-06/SEAS-15 allows 0-3); injected-effect test asserts week 28's `significant` flag is `True` with CI entirely below zero.

---

### `seasonality_by_week.py` (route/CLI entry, request-response)

**Analog:** the same file's existing `main()`/`build_parser()` — `D:\Projects\TraderAssist\seasonality_by_week.py`

**Argparse-declared-but-unused-args pattern** (lines 42-53):
```python
parser.add_argument(
    "--output", default=None,
    help="Output path for results (consumed in a later phase; not used yet)",
)
parser.add_argument(
    "--bootstrap-iters", type=int, default=None,
    help="Number of bootstrap iterations (consumed in a later phase; not used yet)",
)
parser.add_argument(
    "--seed", type=int, default=None,
    help="Random seed for bootstrap reproducibility (consumed in a later phase; not used yet)",
)
```
Phase 6 makes `--bootstrap-iters`/`--seed` live: update their `help=` strings to drop "not used yet" (they're now consumed), and default handling should defer to `scanner.seasonality`'s module constants — pass `args.bootstrap_iters` and `args.seed` straight through to `compute_seasonality_stats`, letting that function apply `_DEFAULT_BOOTSTRAP_ITERS`/`_DEFAULT_SEED` when `None` (keeps the "CLI is thin, defaults live in the engine module" boundary already established for `years`). `--output` stays a Phase 7 concern (CSV export) — leave its help text and behavior unchanged.

**Try/except ValueError → exit 2 pattern** (lines 62-66):
```python
try:
    ds = seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)
except ValueError as exc:
    print(str(exc), file=sys.stderr)
    return 2
```
Reuse this exact shape for the new `compute_seasonality_stats` call — wrap it in the same try/except block (either the same `try` extended to cover both calls, or a second matching `try/except ValueError: print to stderr; return 2` block immediately after) so the D-05 thin-data guard's `ValueError` surfaces identically to the existing sector/universe validation errors.

**Stdout summary print pattern** (lines 68-75):
```python
print(f"Sector: {ds.sector}  Universe: {ds.universe}")
print(f"Admitted: {len(ds.frames)}  Skipped: {len(ds.skipped)}")
if ds.skipped:
    preview = ds.skipped[:10]
    print(f"Skipped tickers (showing {len(preview)} of {len(ds.skipped)}):")
    for ticker, reason in preview:
        print(f"  {ticker}: {reason}")

return 0
```
Follow this same plain-print style (no table library, no formatting framework) for Phase 6's own manual-verification output — e.g. print `baseline_mean_bps`, `n_years`, `bootstrap_iters`, `seed`, and a compact per-week summary (RESEARCH.md notes Phase 6 needs "SOME way to surface results ... likely a plain dict/DataFrame print, not the polished Phase 7 table" — a `print(result.weeks)` DataFrame dump, or a loop over flagged weeks only, both fit this file's existing print-loop convention).

---

## Shared Patterns

### ValueError-with-message abort (dataset-wide validity failures)
**Source:** `scanner/seasonality.py::resolve_sector` (lines 48-60) and `::universe_path` (lines 63-74)
**Apply to:** `check_thin_data()` (D-05 guard) in `scanner/seasonality.py`, caught in `seasonality_by_week.py::main()` per the existing try/except/exit-2 block (lines 62-66).
```python
if condition_fails:
    raise ValueError(f"... descriptive message with the actual vs required values ...")
```

### Skip-not-fail (per-ticker, NOT for the thin-data guard)
**Source:** `scanner/seasonality.py::validate_history` (lines 106-146)
**Apply to:** Any future per-ticker gap-handling in log-return computation, should it be added — explicitly NOT the new dataset-wide thin-data guard, which uses the ValueError-abort pattern above instead (see CONTEXT.md: "different tiers ... don't conflate the two philosophies").

### Dataclass-as-result-container
**Source:** `scanner/seasonality.py::SectorDataset` (lines 35-40)
**Apply to:** New `SeasonalityResult` dataclass — plain `@dataclass`, typed fields, `field(default_factory=...)` for any mutable container, no business logic in the class itself (logic lives in module-level functions that construct and return instances).

### Thin CLI delegates to scanner/ module
**Source:** `seasonality_by_week.py::main()` (lines 57-77) delegating to `scanner/seasonality.py::load_sector_dataset`
**Apply to:** The same `main()` extended to also call `compute_seasonality_stats` — CLI owns argument parsing, error-to-exit-code translation, and print formatting only; all statistical logic stays in `scanner/seasonality.py`.

### No `datetime.now()` in evaluation logic
**Source:** CLAUDE.md global convention, already honored throughout `scanner/seasonality.py` (`as_of: date | None` threaded explicitly rather than read from wall clock)
**Apply to:** All new ISO week/year extraction — derive exclusively from `df.index.isocalendar()` / `panel["date"]`, never `date.today()` or `pd.Timestamp.now()`.

## No Analog Found

None. This phase extends only files that already exist with well-established internal conventions; every new function/test has a directly applicable analog within the same file.

## Metadata

**Analog search scope:** `scanner/seasonality.py`, `tests/test_seasonality.py`, `seasonality_by_week.py` (all read in full — each under 200 lines, single-pass reads, no re-reads needed)
**Files scanned:** 3
**Pattern extraction date:** 2026-07-10
