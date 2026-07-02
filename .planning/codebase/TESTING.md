# Testing Patterns

**Analysis Date:** 2026-07-02

## Test Frameworks

### Python (Engine)

**Runner:** pytest 9.1.0
**Config:** `pyproject.toml` — `[tool.pytest.ini_options]` with `pythonpath = ["."]`

**Run Commands:**
```bash
pytest -q                  # Run all tests (required green after every Python change)
pytest tests/test_core.py  # Single file
pytest -k "test_gate"      # Filter by name
```

### Node.js (API)

**Runner:** Jest 29.7.0
**Config:** `web/api/package.json` — `"testEnvironment": "node"`, `"testMatch": ["**/tests/**/*.test.js"]`

**Run Commands:**
```bash
cd web/api && npm test     # Jest --runInBand --forceExit
```

### Angular (UI)

**Runner:** Karma (via `@angular-devkit/build-angular`)
**Config:** `web/ui/angular.json`, `web/ui/tsconfig.spec.json`

**Run Commands:**
```bash
cd web/ui && ng test       # Must stay green after web changes
```

## Test File Organization

### Python

**Location:** All tests in `tests/` directory at project root — NOT co-located with source

**Naming:** `test_<module_name>.py` mirrors source module names exactly:
```
tests/
├── conftest.py               # Shared fixtures and factory functions
├── golden/                   # JSON golden master snapshots
│   ├── pullback_qualifying.json
│   ├── pullback_near_miss.json
│   ├── breakout_qualifying.json
│   └── breakout_near_miss.json
├── test_backtest.py          # scanner/backtest.py
├── test_core.py              # scanner/core.py
├── test_data_store.py        # scanner/data_store.py
├── test_earnings_store.py    # scanner/earnings_store.py
├── test_fixtures.py          # conftest factory validation
├── test_golden_master.py     # Golden master snapshots
├── test_journal.py           # scanner/journal.py
├── test_postmortem.py        # scanner/postmortem.py
├── test_regime.py            # scanner/regime.py
├── test_report.py            # scanner/report.py
├── test_scan_display.py      # scan.py display logic
├── test_simulate.py          # scanner/simulate.py
├── test_store_db.py          # scanner/store_db.py
├── test_strategies.py        # scanner/strategies/{pullback,breakout}.py
├── test_targets.py           # scanner/targets.py
└── test_universe.py          # scanner/universe.py
```

### Node.js API

**Location:** `web/api/tests/` directory

```
web/api/tests/
├── helpers.js          # Shared DB factory (makeTmpDb)
├── health.test.js
├── jobs.test.js
├── ohlcv.test.js
├── runs.test.js
├── signals.test.js
├── stats.test.js
└── ...
```

### Angular UI

**Location:** Co-located `.spec.ts` files alongside component/service source:
```
web/ui/src/app/
├── app.component.spec.ts
├── pages/
│   ├── backtests/backtests.component.spec.ts
│   ├── candidates/candidates.component.spec.ts
│   ├── dashboard/dashboard.component.spec.ts
│   └── ...
└── services/
    └── api.service.spec.ts
```

## Python Test Structure

### conftest.py Factories

Test data is provided through **plain callable factory functions** in `tests/conftest.py` — NOT pytest fixtures injected by name. Call them directly with parentheses:

```python
from tests.conftest import make_pullback_setup, make_breakout_setup, make_market_data, make_quality

df = make_pullback_setup()           # 280-bar synthetic OHLCV
df = make_breakout_setup()           # 270-bar synthetic OHLCV
market_data = make_market_data()     # dict of ETF DataFrames
quality = make_quality()             # dict with profitable, market_cap, debt_equity, sector
quality = make_quality(sector=None)  # override any field via kwargs
```

### Autouse Network Block

`conftest.py` registers an **autouse fixture** that blocks all yfinance network calls in every test:

```python
@pytest.fixture(autouse=True)
def _block_yfinance_network(monkeypatch):
    """RuntimeError raised if any test accidentally hits yfinance."""
    import yfinance as yf
    def _blocked(*args, **kwargs):
        raise RuntimeError("yfinance network call blocked in tests ...")
    monkeypatch.setattr(yf, "Ticker", _blocked)
    monkeypatch.setattr(yf, "download", _blocked)
```

Tests in `test_data_store.py` and `test_earnings_store.py` override this with their own mocks using `monkeypatch.setattr(ds, "_fetch_raw", fake_fetch_raw)`.

### Test Naming Pattern

```python
# Pattern: test_<subject>_<condition>_<outcome>
def test_pullback_earnings_unknown_skips(): ...
def test_pullback_earnings_known_within_buffer_fails(): ...
def test_pullback_earnings_known_beyond_buffer_passes(): ...
def test_gate_counts(): ...
def test_skip_excluded_from_total(): ...
```

### Within-file Section Headers

Tests grouped within files using the same `# ── Label ──` separator as production code:

```python
# ── E2.2a: earnings skip (pullback) ──────────────────────────────────────────

def test_pullback_earnings_unknown_skips(): ...

# ── E2.2b: sector skip (pullback) ────────────────────────────────────────────

def test_pullback_sector_unknown_skips(): ...
```

### Strategy Test Pattern

Strategy tests build a context using local helper builders, then assert on the result dataclass:

```python
def _pb_ctx(df, quality=None, weekly=_AUTO, days_to_earnings=30, market_data=None):
    """Build EvalContext for pullback evaluation."""
    ...
    return EvalContext(
        as_of=df.index[-1].date(),
        market_data=market_data,
        weekly=weekly,
        quality=quality,
        days_to_earnings=days_to_earnings,
    )

def test_pullback_earnings_unknown_skips():
    df = make_pullback_setup()
    ctx = _pb_ctx(df, days_to_earnings=None)
    res = pb_eval("SYN", df, ctx)
    assert "Earnings clear" in res.skipped_gates
    assert "Earnings clear" not in res.failed_gates
```

### DB Tests Pattern

DB tests use a `db` pytest fixture that creates a temp SQLite file and migrates it:

```python
@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    store_db.migrate(db_path=path)
    conn = store_db.get_connection(path)
    yield conn
    conn.close()
```

## Mocking

### Python

**Framework:** `pytest` built-in `monkeypatch`

**What to mock:**
- `_fetch_raw` in `data_store.py` to avoid network calls
- `make_contexts` in `core.py` to inject pre-built `EvalContext`
- `_CACHE_DIR` in `data_store.py` to redirect to `tmp_path`
- `core.make_contexts` lambda to return deterministic contexts

**Pattern:**
```python
def test_run_scan_sorted_and_complete(monkeypatch):
    import scanner.core as core
    monkeypatch.setattr(core, "make_contexts", lambda t, as_of=None: {tk: ctx for tk in t})
    result = run_scan(tickers, br_fn, as_of=as_of,
                      history_provider=lambda t, end=None: df)
```

**What NOT to mock:**
- Strategy evaluation logic (`pullback.evaluate`, `breakout.evaluate`) — tested end-to-end with synthetic data
- `GateLog` — tested directly, not mocked in strategy tests
- `store_db.migrate` — idempotency tested against real temp SQLite file

### Node.js API

**Framework:** `supertest` + `jest.resetModules()` for fresh app instances per test

**Pattern:** `makeTmpDb()` in `tests/helpers.js` seeds a real SQLite DB in a temp file, then `loadApp(tmpDb)` loads a fresh Express instance pointing at it:

```javascript
function loadApp(dbPath) {
  jest.resetModules();
  const freshDb = require('../db');
  freshDb._reset();
  process.env.DB_PATH = dbPath;
  return require('../app');
}

describe('GET /api/signals/latest', () => {
  let app, tmpDb;
  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });
  it('returns 200 with count and signals array', async () => {
    const res = await request(app).get('/api/signals/latest');
    expect(res.status).toBe(200);
  });
});
```

**`makeTmpDb` options:** `withScanRun`, `withBacktest`, `withSignals`, `withResolved`, `withBars` — compose realistic DB states without real scanner runs.

### Angular UI

**Framework:** `TestBed` with `HttpClientTestingModule`

**Pattern:**
```typescript
describe('ApiService', () => {
  let service: ApiService;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(ApiService);
  });
  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
```

UI tests are currently shallow (existence checks, basic rendering). HTTP calls are not deeply exercised in Angular tests — coverage focus is on the Python engine and Node API.

## Fixtures and Factories

### Synthetic OHLCV Data

Factories in `tests/conftest.py` produce deterministic data using seeded `numpy.random.default_rng`:

```python
def make_pullback_setup(r1=0.0035, n_base=270, pullback_days=10, depth=0.05, seed=1, ...):
    """Synthetic pullback: clean advance + controlled pullback hitting support."""
    ...

def make_breakout_setup(r_base=0.0035, n_pre=230, n_consol=40, breakout_jump=0.006, ...):
    """Synthetic breakout: pre-trend + tightening consolidation + breakout day."""
    ...

def make_downtrend(n=280, r=-0.003, seed=5):
    """Steady downtrend: should fail both strategies."""
    ...

def make_choppy(n=280, amp=0.03, seed=6):
    """Directionless random walk: should fail both strategies."""
    ...
```

**Tuning fixture behavior:** Pass keyword overrides to push setups toward near-miss conditions:
```python
df = make_pullback_setup(depth=0.035)      # too shallow — fails pullback depth gate
df = make_breakout_setup(breakout_jump=0.012)  # weak jump — near miss
```

### Golden Master Snapshots

Located in `tests/golden/*.json`. Snapshot fields are compared field-by-field with float tolerance of ±0.1:

```python
def _assert_field_matches(actual, expected, field):
    if isinstance(expected, float):
        assert abs(actual - expected) <= 0.1, f"{field}: {actual} vs expected {expected}"
    elif isinstance(expected, list):
        assert actual == expected, ...
    else:
        assert actual == expected, ...
```

Golden files are the refactor contract — update them only when intentional behavior changes.

## Coverage

**Requirements:** No enforced coverage threshold; convention is "pytest -q must stay green"

**View Coverage:**
```bash
pytest --cov=scanner --cov-report=term-missing
```

**Known gaps:** Angular UI specs are shallow (component creation only); API tests cover all routes but not every error path.

## Test Types

**Unit Tests:**
- Scope: individual gate logic, GateLog accumulator, single-function utilities
- Files: `test_core.py`, `test_targets.py`, `test_regime.py`, `test_simulate.py`
- No network, no filesystem, no DB

**Integration Tests:**
- Scope: full strategy evaluation pipeline (OHLCV → EvalContext → evaluate() → result dataclass)
- Files: `test_strategies.py`, `test_golden_master.py`
- Uses synthetic data from conftest factories; no network

**Store/DB Tests:**
- Scope: migrate idempotency, round-trip signal write/read, schema version
- Files: `test_store_db.py`
- Uses real SQLite in `tmp_path`

**Cache Tests:**
- Scope: Parquet cache hit/miss, split invalidation, staleness detection
- Files: `test_data_store.py`, `test_earnings_store.py`
- Monkeypatches `_fetch_raw` / `_CACHE_DIR`; no real yfinance calls

**API Integration Tests:**
- Scope: full HTTP request → SQLite query → JSON response
- Files: `web/api/tests/*.test.js`
- Uses `makeTmpDb()` seeded SQLite; supertest drives Express

## Common Patterns

**Testing gate skip vs fail distinction:**
```python
res = pb_eval("SYN", df, ctx)
assert "Earnings clear" in res.skipped_gates      # skipped, not failed
assert "Earnings clear" not in res.failed_gates
```

**Testing gates_total invariant:**
```python
# gates_total == gates_passed + len(failed_gates) — skipped not counted
assert res.gates_total == res.gates_passed + len(res.failed_gates)
```

**Testing single-source-of-truth constants:**
```python
def test_earnings_buffer_days_single_definition():
    from scanner.core import EARNINGS_BUFFER_DAYS
    from scanner.strategies import breakout, pullback
    assert breakout.EARNINGS_BUFFER_DAYS is EARNINGS_BUFFER_DAYS
    assert pullback.EARNINGS_BUFFER_DAYS is EARNINGS_BUFFER_DAYS
```

**Async Testing (Node):** All Jest tests use `async/await` with `supertest`:
```javascript
it('returns 200 with count and signals array', async () => {
  const res = await request(app).get('/api/signals/latest');
  expect(res.status).toBe(200);
});
```

---

*Testing analysis: 2026-07-02*
