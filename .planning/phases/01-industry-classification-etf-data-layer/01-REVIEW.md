---
phase: "01"
status: findings
effort: high
reviewed_at: "2026-07-01"
finding_count: 4
---

# Code Review — Phase 01: Industry Classification + ETF Data Layer

## Findings

### 1. Test fixtures missing all 17 new industry ETFs — `tests/conftest.py:160`

**Severity:** Medium

`make_market_data()` in `conftest.py` and `_make_market()` in `test_backtest.py` both build the market data dict by iterating `SECTOR_ETF_MAP.values()` only. The 17 new industry ETFs added to `_MARKET_SYMBOLS` (XSD, XSW, XBI, XPH, XHE, XHS, KRE, KBE, KIE, KCE, XHB, XRT, XAR, XOP, XES, GDX, XME) are **absent** from every test's mock market dict.

**Failure scenario:** Phase 2 momentum code calls `market_data.get('XSD')` etc. With the current fixtures those keys are missing and return `None` silently — tests pass but the industry ETF path is never exercised, masking real bugs until production.

**Fix:** Update both fixture builders to also iterate `INDUSTRY_ETF_MAP.values()` (or add the known ETF list explicitly), seeding each new key with the same synthetic spy/xlk frame as the sector ETFs.

```python
# conftest.py — in make_market_data()
from scanner.core import SECTOR_ETF_MAP, INDUSTRY_ETF_MAP
...
for etf in set(SECTOR_ETF_MAP.values()) | set(INDUSTRY_ETF_MAP.values()):
    data[etf] = xlk_df if etf == "XLK" else spy_df

# test_backtest.py — in _make_market()
from scanner.core import SECTOR_ETF_MAP, INDUSTRY_ETF_MAP
return {"SPY": spy_bars,
        **{etf: spy_bars for etf in set(SECTOR_ETF_MAP.values()) | set(INDUSTRY_ETF_MAP.values())}}
```

---

### 2. `_MARKET_SYMBOLS` is an unguarded manual copy of `INDUSTRY_ETF_MAP` values — `scanner/data_store.py:30`

**Severity:** Low (maintenance risk)

`_MARKET_SYMBOLS` in `data_store.py` is a static literal list that must stay in sync with `INDUSTRY_ETF_MAP` in `core.py`. The circular-import constraint (documented in the plan) prevents importing the map directly. There is no runtime or test-time enforcement of the sync contract.

**Failure scenario:** A future developer adds `"auto-manufacturers" -> "CARZ"` to `INDUSTRY_ETF_MAP` but forgets to update `_MARKET_SYMBOLS`. `CARZ` never gets a Parquet file; Phase 2 momentum lookup silently receives `NaN` for every ticker in that industry.

**Fix:** Add a test in `tests/test_data_store.py` that imports both and asserts `set(INDUSTRY_ETF_MAP.values()).issubset(set(_MARKET_SYMBOLS))`. This makes the divergence fail loudly rather than silently.

---

### 3. Multi-line docstring on `resolve_industry_etf` violates CLAUDE.md — `scanner/core.py:113`

**Severity:** Low (conventions)

CLAUDE.md (root): *"Never write multi-paragraph docstrings or multi-line comment blocks — one short line max."*

The docstring added at line 114 spans 7 lines and re-explains the function name and the lookup chain already visible from the code.

**Fix:** Reduce to one line or remove entirely:
```python
def resolve_industry_etf(industry_key: Optional[str], sector: Optional[str]) -> Optional[str]:
    # Returns None immediately when industry_key is None (D-06); no sector fallback.
    if industry_key is None:
```

---

### 4. Same fixture gap in `test_backtest.py` — `tests/test_backtest.py:59`

**Severity:** Medium (same root cause as finding #1)

`_make_market()` at line 59 builds from `SECTOR_ETF_MAP` only. Same consequence: backtest tests that exercise industry ETF lookup will silently receive `None`. Covered by the same fix as finding #1.

---

## Summary

| # | File | Line | Severity | Category |
|---|------|------|----------|----------|
| 1 | tests/conftest.py | 160 | Medium | Correctness (test gap) |
| 2 | scanner/data_store.py | 30 | Low | Maintainability |
| 3 | scanner/core.py | 113 | Low | Conventions |
| 4 | tests/test_backtest.py | 59 | Medium | Correctness (test gap) |

Findings #1 and #4 are the same root defect in two files; fix together. No bugs in production code paths — all findings are in test infrastructure or style.
