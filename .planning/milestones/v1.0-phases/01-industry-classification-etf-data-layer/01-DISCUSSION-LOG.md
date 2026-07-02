# Phase 1: Industry Classification + ETF Data Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 1-Industry Classification + ETF Data Layer
**Areas discussed:** ETF map scope, QualityInfo fields, Fallback ETF resolution

---

## ETF map scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full research map | All entries from CLAUDE.md — every sector covered, ~17 unique ETFs cached on refresh. Phase 2 momentum computation works for any ticker in the universe without gaps. | ✓ |
| Starter set (~10 ETFs) | Cover the most common SP400/500/600 industries. Smaller download footprint. Risk: uncommon industries return NULL momentum in Phase 2 until map is extended. | |

**User's choice:** Full research map

---

| Option | Description | Selected |
|--------|-------------|----------|
| Deduplicate | Build the combined unique set: current sector symbols UNION all new industry ETF symbols. _MARKET_SYMBOLS stays clean. | ✓ |
| Add naively, allow dupes | Simpler code change. get_market_data() dict overwrites dupes anyway. Slightly wasteful. | |

**User's choice:** Deduplicate

---

| Option | Description | Selected |
|--------|-------------|----------|
| In the map itself | Explicit entries like 'oil-gas-integrated': 'XLE'. Map is single source of truth. | ✓ |
| Runtime fallback only | INDUSTRY_ETF_MAP covers only industries with dedicated ETFs; lookup falls back to SECTOR_ETF_MAP when key is missing. Cleaner map, more logic. | |

**User's choice:** In the map itself

---

## QualityInfo fields

| Option | Description | Selected |
|--------|-------------|----------|
| Two fields: industry_name + industry_key | Store both info['industry'] (human display) and info['industryKey'] (slug). ETF lookup uses industry_key; CLI/UI display uses industry_name. Matches CLAUDE.md research checklist. | ✓ |
| One field: industry_key only | Store only the slug. Formatting for display handled by planner. Risk: ugly slugs like 'drug-manufacturers-general'. | |
| One field named 'industry' (store the slug) | Name it 'industry' but store the slug. | |

**User's choice:** Two fields: industry + industry_key

---

| Option | Description | Selected |
|--------|-------------|----------|
| industry + industry_key (consistent with sector) | 'industry' for display name, 'industry_key' for slug. Mirrors the existing 'sector' field. | ✓ |
| industry_name + industry_key (explicit) | More verbose but self-documenting. | |

**User's choice:** industry + industry_key (bare convention, consistent with sector)

---

## Fallback ETF resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Skip entirely — return None | No industry_key = no industry ETF. Sector ETF is _sector_strength()'s job. Keeps industry and sector computations separate. | ✓ |
| Fall back to sector ETF | If industry_key is None but sector is known, use the sector ETF as the industry proxy. More coverage but conflates 'no data' with 'sector-level data'. | |

**User's choice:** Skip entirely — return None when industry_key is None

---

## Claude's Discretion

- Exact function name and signature for the ETF resolution helper (e.g., `resolve_industry_etf(industry_key, sector)`)
- Whether to use `field(default=None)` or `= None` syntax in the frozen dataclass for new fields

## Deferred Ideas

None — discussion stayed within phase scope.
