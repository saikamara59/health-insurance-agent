---
name: healthflow-data-refresh
description: Use when adding, modifying, or debugging a real-data fetcher in scripts/refresh_data.py — CMS, HUD, FDA, the in-flight ACA Marketplace fetcher, or any new public-data source feeding healthflow_data.db. Covers the cache → fetch → seed-fallback pattern and the JSON round-trip gotchas.
---

# HealthFlow Data Refresh Pattern

`scripts/refresh_data.py` builds `healthflow_data.db` from public sources (CMS plans, HUD ZIP↔county, FDA drugs) with a consistent layered pattern. New sources (next up: ACA Marketplace) should follow it.

## The four layers

```
SEED_X constant           ← always at module top, last-resort fallback
download_x() → result|None ← per-source fetcher
_load_or_fetch(key, ttl)  ← JSON cache at ~/.cache/healthflow/<key>.json
main() fallback ladder    ← if None, log and use SEED_X
build_database()          ← atomic write: .tmp → os.replace()
```

## Adding a new data source — the recipe

1. **Add `SEED_X`** at the top of the module. Real-shape data, not placeholders. CI runs `--seed-only` and must produce a usable DB.
2. **Write `download_x() -> Result | None`**. Hard rules:
   - Return `None` on *any* failure (network error, missing token, missing httpx). Do not raise.
   - Guard `if httpx is None: return None` at the top.
   - Guard missing required tokens (`os.environ.get("X_TOKEN")`) → log a warning naming the env var → return `None`.
   - Use `with httpx.Client(timeout=...)` — CMS uses 60s, HUD uses 120s for the big crosswalk, FDA uses 30s per request.
3. **Wire through `_load_or_fetch`** in `main()`:
   ```python
   result = _load_or_fetch("x_cache_key", ttl_days=N,
                           fetch_fn=download_x, force=args.force_refresh)
   ```
   Pick TTL by source volatility: CMS=7d, HUD/FDA=30d. Marketplace is rate-limited and key-rotated → 7d is reasonable.
4. **Fall back in `main()`**: `if result is None: ... = SEED_X` with an INFO log naming the source.
5. **Pipe into `build_database`** — never write SQLite directly outside this function.

## The JSON round-trip gotcha (most common bug)

`_load_or_fetch` calls `_serialize_for_cache` which converts `set` → sorted list and goes through `json.dump`. This means **on a cache hit, every set becomes a list and every tuple becomes a list**.

Consequences you must handle:
- **Tuples**: explicit coerce after cache: `plans = [tuple(p) for p in plans]` (see `main()` for both `plans` and `drugs`).
- **Sets**: write join helpers to accept any iterable, not assume `set`. See `build_zip_mappings` — it works on either, by design.
- **Don't** rely on set semantics (membership, dedup) on cache-rehydrated data without re-wrapping.

If a fetcher returns `None`, `_load_or_fetch` does NOT write the cache. Good — failures don't get pinned.

## Atomic DB write

`build_database` writes to `<db_path>.tmp`, then `os.replace()`s it onto the real path. A crash mid-build leaves the previous DB intact. Don't shortcut this — don't write to `db_path` directly even for "small" updates.

## CLI flags (already wired, reuse)

- `--seed-only`: skip downloads, use seeds. CI uses this.
- `--force-refresh`: bypass cache, re-fetch everything.
- `--verbose`: DEBUG logging (cache hits, pagination, row counts).
- `--db-path`: override output. Tests use this with tmpdirs.

## Logging & error contract

- **WARNING** for expected-degraded paths (token missing, source down, falling back to seed).
- **INFO** for normal progress and final row counts.
- **DEBUG** for per-row skips and cache file reads.
- When a known sunset condition matches (e.g. CMS HTTP 410), append a hint pointing to the README — see `download_cms_data` for the pattern.
- Error messages must name the env var or URL involved. "HUD download failed" is useless; "HUD_API_TOKEN not set; using seed ZIP mappings" is actionable.

## When you're about to add the ACA Marketplace fetcher

`MARKETPLACE_API_KEY` rotates every ~60 days. The fetcher should:
- Return `None` if the key is missing (same pattern as `HUD_API_TOKEN`).
- Distinguish HTTP 401 (key expired — log "MARKETPLACE_API_KEY rejected; request a new key at https://developer.cms.gov/marketplace-api/") from other failures. Don't retry on 401.
- Per the API docs, this endpoint is "designed for live access, NOT bulk extraction" — keep TTL short (~7d) and avoid wide queries.
- Cache key suggestion: `marketplace_<query-hash>` if queries vary, or just `marketplace_landscape` if you fetch one canonical slice.

## Quick checklist before merging a new fetcher

- [ ] `SEED_X` exists and `--seed-only` produces a valid DB
- [ ] `download_x` returns `None` on every failure path (no raises bubble up)
- [ ] Required env vars guarded with named warning, not silent failure
- [ ] Wired through `_load_or_fetch` with a sensible TTL
- [ ] `main()` has explicit `if result is None:` fallback with INFO log
- [ ] If output contains tuples or sets, `main()` coerces (`[tuple(x) for x in ...]`) after cache
- [ ] DB write goes through `build_database` (atomic via `.tmp` + `os.replace`)
- [ ] Log message on failure names the env var or URL
