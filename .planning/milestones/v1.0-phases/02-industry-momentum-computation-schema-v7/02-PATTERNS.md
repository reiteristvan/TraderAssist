# Phase 2: Industry Momentum Computation + Schema v9 — Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 7
**Analogs found:** 7 / 7

> NOTE: The phase is labeled "schema-v7" in the roadmap/directory name but the actual DB is already at v8.
> All schema patterns below use v9 (the correct next version). See RESEARCH.md Pitfall 1.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scanner/core.py` (add `_industry_strength()` + post-loop rank) | utility/service | request-response, batch | `_sector_strength()` in same file | exact |
| `scanner/store_db.py` (schema v9 migration + INSERT updates) | data-store | CRUD | existing `if current < 8:` block + `insert_signal()` | exact |
| `scanner/simulate.py` (Signal dataclass extension) | model | transform | existing `Signal` dataclass + `Trade` optional fields | exact |
| `scanner/backtest.py` (per-day ETF rank + Signal construction) | service | batch | existing per-day `sliced_market` + `signals.append(Signal(...))` block | role-match |
| `scanner/journal.py` (write_live_signals sig dict extension) | service | request-response | existing `sigs.append({...})` block lines 52–68 | exact |
| `tests/test_core.py` (new industry_strength tests) | test | — | `test_quality_info_industry_roundtrip`, `test_historical_context_sliced` | role-match |
| `tests/test_store_db.py` (update ver assertions + NULL round-trip) | test | — | `test_migrate_idempotent`, `test_signal_round_trip` | exact |

---

## Pattern Assignments

### `scanner/core.py` — `_industry_strength()` function

**Analog:** `_sector_strength()` in `scanner/core.py` lines 275–293

**Direct template** (lines 275–293):
```python
def _sector_strength(sector: Optional[str], market_data: dict) -> dict:
    out = {"sector_etf": None, "sector_above_50ma": False, "sector_outperforming": False}
    if not sector:
        return out
    etf = SECTOR_ETF_MAP.get(sector)
    if not etf:
        return out
    out["sector_etf"] = etf
    etf_df = market_data.get(etf)
    spy_df = market_data.get("SPY")
    if etf_df is None or len(etf_df) < 50:
        return out
    sma50 = etf_df["Close"].rolling(50).mean().iloc[-1]
    out["sector_above_50ma"] = bool(etf_df["Close"].iloc[-1] > sma50)
    if spy_df is not None and len(spy_df) >= RS_LOOKBACK:
        etf_ret = etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-RS_LOOKBACK]
        spy_ret = spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-RS_LOOKBACK]
        out["sector_outperforming"] = bool(etf_ret > spy_ret)
    return out
```

**Key differences for `_industry_strength()`:**
- Accepts `industry_key: Optional[str]` + `sector: Optional[str]` (two-tier lookup)
- Uses `resolve_industry_etf(industry_key, sector)` instead of `SECTOR_ETF_MAP.get(sector)`
- Checks `len(etf_df) < 21` (not 50) before the 20-day ROC — 50 required only for 50MA boolean
- Computes 20-day ROC: `float(etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-21] - 1) * 100`
- Returns `None` (not `False`) for missing values — avoids NaN-to-0.0 coercion bug in SQLite
- Returns dict keys: `industry_etf`, `industry_mom_20d`, `industry_above_50ma`, `industry_rs_spy`

**resolve_industry_etf() — already shipped in Phase 1** (lines 113–120):
```python
def resolve_industry_etf(industry_key: Optional[str], sector: Optional[str]) -> Optional[str]:
    # None industry_key returns None immediately — no sector fallback (D-06).
    if industry_key is None:
        return None
    etf = INDUSTRY_ETF_MAP.get(industry_key)
    if etf is not None:
        return etf
    return SECTOR_ETF_MAP.get(sector)
```

**Post-loop rank percentile pattern** — add after the ticker loop in `run_scan()`:
```python
# pandas.Series.rank(pct=True) — ascending; higher momentum = higher percentile
# Must be post-loop: rank requires all ETFs seen in the run to be present.
etf_scores: dict[str, float] = {}
for row in rows:
    etf = row.get("industry_etf")
    mom = row.get("industry_momentum")
    if etf is not None and mom is not None and etf not in etf_scores:
        etf_scores[etf] = mom
if len(etf_scores) >= 2:
    pct_ranks = pd.Series(etf_scores).rank(pct=True)
    for row in rows:
        etf = row.get("industry_etf")
        if etf is not None:
            val = pct_ranks.get(etf)
            row["industry_rank_pct"] = float(val) if val is not None and not pd.isna(val) else None
```

---

### `scanner/store_db.py` — schema v9 migration

**Analog:** existing `if current < 8:` block (lines 148–153) + `insert_signal()` (lines 196–208)

**Migration pattern to copy** (lines 148–153):
```python
if current < 8:
    conn.execute("ALTER TABLE signals ADD COLUMN mae_r REAL")
    conn.execute("ALTER TABLE signals ADD COLUMN mfe_r REAL")
    conn.execute("ALTER TABLE signals ADD COLUMN post_stop_reached_target INTEGER")
    conn.execute("ALTER TABLE signals ADD COLUMN post_stop_mfe_r REAL")
    conn.execute("UPDATE schema_version SET version = 8")
```

**New v9 block — append after the v8 block, change constant to 9:**
```python
# _SCHEMA_VERSION = 9  (bump from 8)

if current < 9:
    conn.execute("ALTER TABLE signals ADD COLUMN industry_group TEXT")
    conn.execute("ALTER TABLE signals ADD COLUMN industry_momentum REAL")
    conn.execute("ALTER TABLE signals ADD COLUMN industry_above_50ma INTEGER")  # SQLite bool
    conn.execute("ALTER TABLE signals ADD COLUMN industry_rank_pct REAL")
    conn.execute("UPDATE schema_version SET version = 9")
    current = 9
```

**insert_signal() pattern to extend** (lines 196–208):
```python
def insert_signal(conn: sqlite3.Connection, sig: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO signals
           (date, ticker, strategy, source, run_id, score, confidence,
            stop, target, atr, qualified, failed_gates, close,
            gate_detail_json, ath_zone)
           VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
                   :stop, :target, :atr, :qualified, :failed_gates, :close,
                   :gate_detail_json, :ath_zone)""",
        {**sig, "gate_detail_json": sig.get("gate_detail_json"),
                "ath_zone": sig.get("ath_zone")},
    )
    conn.commit()
```

Add 4 columns to both the column list, VALUES list, and the dict unpacking — follow the `ath_zone` pattern exactly: add to both INSERT string and the `.get()` dict.

---

### `scanner/simulate.py` — Signal dataclass extension

**Analog:** existing optional fields at bottom of `Signal` (lines 50–55) and `Trade` (same file)

**Current Signal fields** (lines 15–28):
```python
@dataclass
class Signal:
    date: date
    ticker: str
    strategy: str       # "pullback" | "breakout"
    score: float
    confidence: Optional[str]
    stop: float
    target: float
    atr: float
    qualified: bool
    failed_gates: list[str] = field(default_factory=list)
    close: float = 0.0  # signal-bar close price
```

**Pattern for appending Optional fields with defaults** (from `Trade`, lines 50–55):
```python
    target_r: Optional[float] = None
    target_atr: Optional[float] = None
    mae_r: Optional[float] = None
    mfe_r: Optional[float] = None
    post_stop_reached_target: Optional[bool] = None
    post_stop_mfe_r: Optional[float] = None
```

Append these 4 fields to `Signal` after `close: float = 0.0`, using the same `Optional[X] = None` pattern:
```python
    # Phase 2 — industry momentum
    industry_group: Optional[str] = None
    industry_momentum: Optional[float] = None
    industry_above_50ma: Optional[bool] = None
    industry_rank_pct: Optional[float] = None
```

Fields with defaults must come after all fields without defaults — `close: float = 0.0` already has a default, so appending here is valid.

---

### `scanner/backtest.py` — per-day ETF rank + Signal construction

**Analog:** per-day `sliced_market` block + `signals.append(Signal(...))` at lines 309–417

**Per-day slicing pattern** (lines 311–315):
```python
as_of_ts = pd.Timestamp(d)

# Slice market once per day
sliced_market = {
    sym: df[df.index <= as_of_ts] for sym, df in full_market.items()
}
```

**Signal construction pattern** (lines 405–417):
```python
signals.append(Signal(
    date=d,
    ticker=ticker,
    strategy=strategy,
    score=result.score,
    confidence=result.confidence,
    stop=result.suggested_stop,
    target=result.suggested_target,
    atr=result.atr or 0.0,
    qualified=result.qualified,
    failed_gates=list(result.failed_gates),
    close=result.close,
))
```

**Integration approach:** Before the inner per-ticker loop, compute a per-day ETF momentum dict using `sliced_market`. Then look up each ticker's industry ETF in that dict when constructing `Signal`. Add `industry_group`, `industry_momentum`, `industry_above_50ma`, `industry_rank_pct` as keyword args to `Signal(...)`.

The `quality_by_ticker` dict already exists in `generate_signals()` — use `quality_by_ticker.get(ticker).industry_key` and `.sector` to call `_industry_strength()`.

---

### `scanner/journal.py` — write_live_signals sig dict extension

**Analog:** `sigs.append({...})` block (lines 51–68)

**Current hard-coded sig dict** (lines 52–68):
```python
sigs.append({
    "date": str(row.get("as_of") or row.get("date", date.today())),
    "ticker": row["ticker"],
    "strategy": strategy,
    "source": "live",
    "run_id": run_id,
    "score": row.get("score"),
    "confidence": row.get("confidence"),
    "stop": row.get("suggested_stop"),
    "target": row.get("suggested_target"),
    "atr": row.get("atr"),
    "qualified": 1 if row.get("qualified") else 0,
    "failed_gates": ";".join(row.get("failed_gates") or []),
    "close": row.get("close"),
    "gate_detail_json": json.dumps(row.get("gate_detail") or []),
    "ath_zone": row.get("ath_zone"),
})
```

**Pattern:** Add 4 new keys using `.get()` with implicit None default, same as `ath_zone`:
```python
    "industry_group": row.get("industry_group"),
    "industry_momentum": row.get("industry_momentum"),
    "industry_above_50ma": row.get("industry_above_50ma"),
    "industry_rank_pct": row.get("industry_rank_pct"),
```

---

### `tests/test_core.py` — new industry_strength tests

**Analog:** `test_quality_info_industry_roundtrip` (lines 193–205) and `test_historical_context_sliced` (lines 218–247)

**Test structure pattern — unit test with monkeypatched market_data:**
```python
def test_quality_info_industry_roundtrip():
    qi = QualityInfo(
        profitable=True,
        market_cap=2.5e9,
        debt_equity=50.0,
        sector="Technology",
        float_shares=50e6,
        industry="Semiconductors",
        industry_key="semiconductors",
    )
    assert qi.industry == "Semiconductors"
    assert qi.industry_key == "semiconductors"
```

**Test structure pattern — context slicing with synthetic DataFrames:**
```python
def test_historical_context_sliced(tmp_path, monkeypatch):
    import scanner.data_store as ds
    import scanner.core as core

    monkeypatch.setattr(ds, "_CACHE_DIR", tmp_path)

    idx = pd.bdate_range(end=pd.Timestamp("2026-06-15"), periods=400)
    closes = np.linspace(10.0, 30.0, 400)
    full_df = pd.DataFrame({
        "Open": closes - 0.1, "High": closes + 0.2, "Low": closes - 0.2,
        "Close": closes, "Volume": np.full(400, 1_000_000.0),
    }, index=idx)

    for sym in ["SYN"] + ds._MARKET_SYMBOLS:
        ds._write_cache(sym, full_df)
    # ...
```

**New tests to add** (use the same synthetic DataFrame idiom for market_data):

| Test function | What to assert |
|---|---|
| `test_industry_strength_basic` | Returns correct `industry_mom_20d` when ETF has ≥ 21 bars |
| `test_industry_strength_no_etf_returns_none` | `industry_key=None` → all fields `None` |
| `test_industry_strength_insufficient_bars_returns_none` | ETF with 10 bars → `industry_mom_20d` is `None` |
| `test_industry_above_50ma_flag` | ETF close > SMA50 → `True`; close < SMA50 → `False` |
| `test_industry_rs_spy_ratio` | Known ETF and SPY closes → ratio matches manual calculation |
| `test_industry_rank_pct_multi_etf` | 3 rows with 3 different ETFs → middle ETF gets rank 0.5 |
| `test_industry_rank_pct_single_etf_returns_none` | All rows same ETF → `industry_rank_pct` stays `None` |

Build the synthetic `market_data` dict directly (no monkeypatching needed for unit tests of `_industry_strength()`):
```python
market_data = {
    "XSD": pd.DataFrame({"Close": list(range(1, 60))}, ...),
    "SPY": pd.DataFrame({"Close": list(range(1, 60))}, ...),
}
```

---

### `tests/test_store_db.py` — schema version update + NULL round-trip

**Analog:** `test_migrate_idempotent` (lines 70–78) and `test_signal_round_trip` (lines 87–97)

**Current assertions to update** (lines 78, 82):
```python
assert ver == 8   # line 78 in test_migrate_idempotent
assert store_db.get_schema_version(db) == 8  # line 82 in test_migrate_schema_version_present
```
Change both to `== 9`.

**Round-trip pattern to copy for NULL test** (lines 87–97):
```python
def test_signal_round_trip(db):
    sig = _sample_signal()
    store_db.insert_signal(db, sig)
    row = db.execute(
        "SELECT * FROM signals WHERE ticker = 'AAPL' AND date = '2026-01-05'"
    ).fetchone()
    assert row is not None
    assert row["ticker"] == "AAPL"
    assert float(row["score"]) == pytest.approx(65.0)
```

**New test — NULL round-trip** (add after existing round-trip tests):
```python
def test_industry_momentum_null_round_trip(db):
    """industry_momentum=None must be stored as SQL NULL, not 0.0 (anti-NaN pitfall)."""
    sig = {**_sample_signal(), "industry_group": None, "industry_momentum": None,
           "industry_above_50ma": None, "industry_rank_pct": None}
    store_db.insert_signal(db, sig)
    row = db.execute("SELECT * FROM signals WHERE ticker = 'AAPL'").fetchone()
    assert row["industry_momentum"] is None
    assert row["industry_group"] is None
    assert row["industry_rank_pct"] is None
```

---

## Shared Patterns

### Python None for missing values (not NaN)

**Source:** RESEARCH.md anti-patterns + `_sector_strength()` in `scanner/core.py` (lines 275–293)
**Apply to:** `_industry_strength()`, `insert_signal()` dict building, `write_live_signals()` sig dict

All missing numeric industry fields must be Python `None`, never `float('nan')` or `numpy.nan`. SQLite stores `None` as NULL; NaN may coerce to 0.0.

### No yfinance imports outside data_store.py

**Source:** `CLAUDE.md` global constraint
**Apply to:** `scanner/core.py` — `_industry_strength()` must use `market_data.get(etf)` only

`market_data` dict is already populated by `get_market_data()` in `data_store.py` before the function is called. Never import `yf` or call `yf.download()` in `core.py`.

### No datetime.now() inside evaluation logic

**Source:** `CLAUDE.md` global constraint
**Apply to:** `_industry_strength()`, `_attach_industry_rank_pct()`

Both functions receive pre-sliced `market_data` (already anchored to `as_of`). No date arithmetic needed inside either function.

### INSERT OR IGNORE with dict unpacking

**Source:** `insert_signal()` and `insert_signals_batch()` in `scanner/store_db.py` lines 196–228

Always pass `{**sig, "new_field": sig.get("new_field")}` — the dict-spread ensures all existing keys are included, and explicit `.get()` calls for new optional columns ensure NULL defaults without KeyError.

---

## No Analog Found

All 7 files have close analogs. No file in this phase requires building a net-new pattern.

---

## Metadata

**Analog search scope:** `scanner/`, `tests/`
**Files scanned:** `scanner/core.py`, `scanner/store_db.py`, `scanner/simulate.py`, `scanner/backtest.py`, `scanner/journal.py`, `tests/test_core.py`, `tests/test_store_db.py`
**Pattern extraction date:** 2026-07-01
