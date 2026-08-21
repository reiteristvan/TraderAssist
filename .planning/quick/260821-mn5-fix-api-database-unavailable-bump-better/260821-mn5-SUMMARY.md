---
phase: quick-260821-mn5
plan: 01
subsystem: api
tags: [better-sqlite3, node24, abi, sqlite, express, jest, diagnostics]

requires: []
provides:
  - "web/api better-sqlite3 dependency bumped ^11.10.0 -> ^12.6.2, resolving a prebuilt ABI-137 binary under Node 24.19.0 with no C++ compile step"
  - "getDb()/getWriteDb() log the caught open error via a shared _logDbOpenFailure helper before returning null, while the absent-file path stays silent"
  - "web/api/tests/db-open-failure.test.js proving both the loud (open failure) and quiet (absent file) paths, plus the unchanged 503 contract"
affects: [web-api, db-layer]

actuals:
  tokens: 1969
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Module-private _logDbOpenFailure(fnName, dbPath, err) helper called from inside catch blocks only, never above the fs.existsSync guard"

key-files:
  created:
    - web/api/tests/db-open-failure.test.js
  modified:
    - web/api/package.json
    - web/api/package-lock.json
    - web/api/db/index.js

key-decisions:
  - "Bumped better-sqlite3 to ^12.6.2 (installed 12.11.1) — Node 24 prebuilds only begin at 12.2.0; the previously pinned ^11.10.0 range could never resolve to a prebuilt ABI-137 binary and this machine has no VS C++ build tools for a source compile."
  - "getDb() and getWriteDb() now log every open failure unconditionally (no once-only/rate-limiting) — deliberate per D2/D-02 since the ABI fault ran silently for a day; the fs.existsSync guard above the try block is the only thing that keeps the legitimate absent-file path quiet."
  - "Test assertions on the caught error use err.message shape checks instead of toBeInstanceOf(Error) — better-sqlite3's native SqliteError is bound to whichever test file's Jest VM realm first dlopen'd the native addon (a process-wide native binding cache), making cross-realm instanceof unreliable across sibling test files under --runInBand."

requirements-completed: [D1, D2, D3]

coverage:
  - id: D1
    description: "better-sqlite3 bumped to ^12.6.2 (installed 12.11.1); loads a prebuilt ABI-137 binary under Node 24.19.0 with no compile step; getDb() opens the real data/scanner.db readonly with PRAGMA integrity_check = ok"
    requirement: "D1"
    verification:
      - kind: other
        ref: "node -e getDb()/getSchemaVersion() end-to-end check against data/scanner.db (see Verification section)"
        status: pass
      - kind: unit
        ref: "web/api/tests (npm test) — 76 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "getDb() and getWriteDb() log the caught open error via _logDbOpenFailure before returning null; absent-file path stays silent; 503 status/body unchanged"
    requirement: "D2"
    verification:
      - kind: unit
        ref: "web/api/tests/db-open-failure.test.js — Test 1-5 (loud read/write path, quiet read/write path, 503 contract)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both fixes landed as two separate atomic commits (dependency bump, then diagnostics fix)"
    requirement: "D3"
    verification:
      - kind: other
        ref: "git log --oneline -2 -> c5df68d (bump), 22cc5f8 (diagnostics+test)"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-08-21
status: complete
---

# Quick Task 260821-mn5: Fix API "Database Unavailable" (better-sqlite3 ABI bump) Summary

**Bumped `better-sqlite3` to ^12.6.2 for a Node-24 ABI-137 prebuilt binary and added loud-on-failure/quiet-on-absent logging to `getDb()`/`getWriteDb()`, restoring `/api/health` from 503 to 200 without changing any 503 contract.**

## Performance

- **Duration:** ~3 min between task commits (excludes reading/planning time)
- **Started:** 2026-08-21T16:27:10+02:00 (Task 1 commit)
- **Completed:** 2026-08-21T16:30:18+02:00 (Task 2 commit)
- **Tasks:** 2 completed
- **Files modified:** 4 (`package.json`, `package-lock.json`, `db/index.js`, plus 1 new test file)

## Accomplishments
- `web/api/package.json` `better-sqlite3` moved `^11.10.0` -> `^12.6.2`; npm resolved and installed `12.11.1` via a prebuilt binary (no node-gyp/compile step — install completed in ~3s with no Visual Studio toolchain present)
- Verified the real, git-tracked `data/scanner.db` opens through the exported readonly `getDb()`: `schema_version` = 10, `integrity_check` = ok, `signals` = 263544, `runs` = 52 — exact match to the CONTEXT.md baseline
- Added a shared `_logDbOpenFailure(fnName, dbPath, err)` helper in `web/api/db/index.js`, called from both `getDb()`'s and `getWriteDb()`'s catch blocks (immediately before their existing `return null`), replacing the discarded `_err`/`_` bindings
- New `web/api/tests/db-open-failure.test.js` covers all 5 required behaviors: loud-on-failure for both the read (`getDb()`) and write (`enqueueJob()` -> `getWriteDb()`) paths, silent-on-absent-file for both paths, and an unchanged 503 status/body contract on `GET /api/health`
- `npm test` in `web/api`: 76/76 passing (71 pre-existing + 5 new), run twice to confirm no cross-file ordering flake
- `pytest -q` at repo root: 466/466 passing, unaffected — no `scanner/` or `scan.py` files touched

## Task Commits

Each task was committed atomically:

1. **Task 1: Bump better-sqlite3 to ^12.6.2 and prove the real database opens end-to-end** - `c5df68d` (fix)
2. **Task 2: Log the swallowed open error in getDb/getWriteDb, keeping the 503 contract intact** - `22cc5f8` (fix)

_No separate plan-metadata commit was made prior to this SUMMARY; the final docs commit follows this file per the execute-plan workflow._

## Files Created/Modified
- `web/api/package.json` - `better-sqlite3` dependency bumped `^11.10.0` -> `^12.6.2`
- `web/api/package-lock.json` - regenerated; resolved to `12.11.1`
- `web/api/db/index.js` - added `_logDbOpenFailure` helper; wired into both catch blocks with the previously-discarded error binding now passed through
- `web/api/tests/db-open-failure.test.js` (new) - 5 tests covering loud/quiet paths on both `getDb()` and `getWriteDb()`, plus the 503 HTTP contract

## Decisions Made
- Installed `better-sqlite3@12.11.1` (within the `^12.6.2` declared range) — first version tested was whatever npm resolved; confirmed >= 12.2.0 (the first Node-24-prebuilt release) per plan constraint.
- No once-only/rate-limited logging: every open failure logs on every request, by design (D2/D-02) — this fault previously ran silently for a day.
- Test assertions on the caught error avoid `toBeInstanceOf(Error)` in favor of `typeof err.message === 'string'` checks, to sidestep a Jest cross-realm `instanceof` false-negative caused by better-sqlite3's native addon binding cache being shared across per-test-file VM sandboxes (see Issues Encountered).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion `toBeInstanceOf(Error)` failed non-deterministically under the full test suite**
- **Found during:** Task 2, running `npm test` after `npx jest tests/db-open-failure.test.js --runInBand` passed in isolation
- **Issue:** `expect(err).toBeInstanceOf(Error)` failed with "Received constructor: SqliteError" only when `db-open-failure.test.js` ran alongside sibling test files in the same `--runInBand` process. Root cause: better-sqlite3's native addon is `dlopen`'d once per process and cached at that level, but Jest sandboxes each test file into its own VM realm with its own `Error` global — so the native module's `SqliteError` class can be bound to a different realm's `Error` than the one the assertion checks against, depending on file execution order.
- **Fix:** Replaced `expect(err).toBeInstanceOf(Error)` with shape-based assertions (`typeof err.message === 'string'` and `err.message.length > 0`) in both loud-path tests (Test 1 and Test 2). Behavior coverage is unchanged — the tests still prove a real error object with a message reached the logger.
- **Files modified:** `web/api/tests/db-open-failure.test.js`
- **Verification:** `npm test` run twice consecutively — 76/76 passing both times, no flake.
- **Committed in:** `22cc5f8` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in test code, not implementation)
**Impact on plan:** No scope creep — the fix stayed within the planned test file and did not touch `db/index.js` logic or the 503 contract. All plan-mandated behaviors (loud/quiet paths, 503 contract) remain fully covered.

## Issues Encountered
- Jest's per-test-file VM sandboxing combined with better-sqlite3's process-level native-addon cache produces a cross-realm `instanceof Error` false-negative that only manifests when the new test file runs alongside other test files that also load `better-sqlite3` — not when run in isolation. Resolved per deviation above; documented in a code comment at both assertion sites in `db-open-failure.test.js` so it is not re-discovered as a mystery flake later.

## User Setup Required
None - no external service configuration required.

## Verification

Measured values, as required by the plan's `<output>` spec:

- **Installed `better-sqlite3` version:** `12.11.1` (satisfies declared range `^12.6.2`)
- **`process.versions.modules`:** `137`
- **`node -v`:** `v24.19.0`
- **Real `data/scanner.db` readonly open via `getDb()`:**
  - `schema_version`: `10`
  - `PRAGMA integrity_check`: `ok`
  - `signals` count: `263544`
  - `runs` count: `52`
  - (Exact match to CONTEXT.md baseline — no divergence)
- **`console.error` message format emitted by `_logDbOpenFailure`:**
  ```
  [db] <fnName> failed to open database at <resolvedDbPath> — driver/open error: <err>
  ```
  where `<fnName>` is `getDb` or `getWriteDb`, `<resolvedDbPath>` is the absolute path from `resolvedDbPath()`, and `<err>` is the caught error object passed as `console.error`'s second argument (Node renders its message and stack).
- **`npm test` final line (web/api):** `Tests: 76 passed, 76 total` (`Test Suites: 7 passed, 7 total`) — run twice, both green, no flake.
- **`pytest -q` (repo root):** `466 passed, 2 warnings` — warnings are pre-existing and unrelated (divide-by-zero in `test_seasonality.py` log-return edge cases).
- **`git diff --stat HEAD~2 -- scanner scan.py`:** no output — Python side untouched.
- **Two commits confirmed:**
  - `c5df68d` — `fix(quick-260821-mn5): bump better-sqlite3 to ^12.6.2 for Node 24 ABI 137 prebuilt binary` — touches only `web/api/package.json`, `web/api/package-lock.json`
  - `22cc5f8` — `fix(quick-260821-mn5): log swallowed DB open errors in getDb/getWriteDb, keep 503 contract intact` — touches only `web/api/db/index.js`, `web/api/tests/db-open-failure.test.js`
- **`node_modules/` not committed:** confirmed via `git check-ignore -q node_modules` and both commits' `git show --stat` listing only source/lockfile paths.

## Next Phase Readiness
- The API now answers from the real database again — `/api/health` returns 200, not 503.
- A future driver/open failure is attributable from the server console alone (no source reading required) because the caught error is logged with `[db]`-prefixing, the failing function name, the resolved path, and the underlying error text.
- The absent-database path remains byte-for-byte as quiet and as 503-shaped as before this change.
- No blockers or concerns for downstream work.

---
*Phase: quick-260821-mn5*
*Completed: 2026-08-21*

## Self-Check: PASSED
- FOUND: web/api/tests/db-open-failure.test.js
- FOUND: .planning/quick/260821-mn5-fix-api-database-unavailable-bump-better/260821-mn5-SUMMARY.md
- FOUND commit: c5df68d
- FOUND commit: 22cc5f8
