# Quick Task 260821-mn5 — Context

**Task:** Restore the web API's DB connectivity, broken by today's Node 22 -> 24 upgrade,
and stop `getDb()` from swallowing the cause.

## Root cause (measured, not assumed)

`better-sqlite3` is the only native module in `web/api` or `web/ui`. Its compiled binary
is ABI-locked:

```
better_sqlite3.node compiled against NODE_MODULE_VERSION 127  (Node 22)
current runtime requires             NODE_MODULE_VERSION 137  (Node 24.19.0)
-> ERR_DLOPEN_FAILED
```

`web/api/db/index.js::getDb()` catches that throw and returns `null`; every route then
answers `503 {"error":"Database unavailable"}`. The message blames the data; the fault is
the loader. The DB itself is healthy — verified: schema v10, 263,544 signals, 52 runs,
`PRAGMA integrity_check` = ok.

Node cannot be rolled back to 22: GSD 1.11.0 requires Node 24.

## Verified facts driving the fix

- `npm rebuild better-sqlite3` FAILS — no Visual Studio C++ build tools on this machine.
  Source compilation is not an available path; the fix must use a **prebuilt** binary.
- Prebuilt availability for `node-v137-win32-x64`, checked per release:

  | version | asset |
  |---|---|
  | 11.10.0 | 404 |
  | 12.0.0  | 404 |
  | 12.2.0  | 200 |
  | 12.4.1  | 200 |
  | 12.6.2  | 200 |

  Node 24 prebuilds begin at **12.2.0**. The pinned `^11.10.0` can never resolve to one.
- better-sqlite3 12.6.2 was installed in a scratch dir and opened the REAL
  `data/scanner.db` read-only without a compiler, returning the counts above. The bump is
  pre-validated against production data.

## Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Fix mechanism | Bump `web/api/package.json` `better-sqlite3` from `^11.10.0` to `^12.6.2`, reinstall so a prebuilt ABI-137 binary lands. |
| D2 | Diagnostics | `getDb()` (and `getWriteDb()`) must log the caught error before returning `null`, so the next loader failure is not misreported as a data failure. Keep returning `null` — the 503 contract is unchanged. |
| D3 | Scope | Both in one quick task, as separate atomic commits. |

## Constraints

- `npm test` (API) must stay green. Do not weaken or skip tests.
- The 503 response bodies and status codes must NOT change — only an added log line.
- Python side is untouched: no `pytest` impact, no schema change, no `store_db.py` edit.
- Do NOT commit `node_modules/`. `package-lock.json` SHOULD be committed.
- better-sqlite3 12.x is a major bump — the API uses only standard
  `prepare/all/get/run/pragma/transaction`, but `npm test` is the gate that proves it.
