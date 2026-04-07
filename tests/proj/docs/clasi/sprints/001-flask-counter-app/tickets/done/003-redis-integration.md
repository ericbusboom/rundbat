---
id: '003'
title: Redis integration
status: in-progress
use-cases:
- SUC-003
- SUC-006
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Redis integration

## Description

Add Redis connection, counter read, and counter increment to `app.py`.
The app reads `REDIS_URL` from dotconfig at startup. Helper functions
`get_redis_count()` and `increment_redis()` use redis-py. Redis key
initialization is lazy — `INCR` creates the key starting from 0 if
absent; `GET` returns `None` which is treated as 0.

## Acceptance Criteria

- [ ] `app.py` reads `REDIS_URL` from dotconfig at startup (alongside
  `DATABASE_URL` from ticket 002 — both come from the same `load_config()` call).
- [ ] `get_redis_count()` returns the integer value of the `counter` key,
  or 0 if the key does not exist.
- [ ] `increment_redis()` executes `INCR counter` and returns the new value.
- [ ] After `rundbat create-env dev`, `get_redis_count()` returns 0 on a
  fresh Redis instance.
- [ ] After one call to `increment_redis()`, `get_redis_count()` returns 1.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001 and 002 tests must pass).
- **New tests to write**: Unit tests for `get_redis_count()` and
  `increment_redis()` using either a real dev Redis or the `fakeredis`
  library for isolation.
- **Verification command**: `uv run pytest`

## Implementation Plan

### Approach

Add `get_redis_client()` returning a `redis.Redis` instance parsed from
`REDIS_URL`. Add `get_redis_count()` (GET counter, coerce `None` to 0)
and `increment_redis()` (INCR counter). No explicit startup initialization
needed — Redis handles key creation on first INCR.

### Files to Modify

- `app.py`:
  - `load_config()` from ticket 002 already captures `REDIS_URL`; add
    module-level `REDIS_URL` variable.
  - Add `get_redis_client()` — returns `redis.Redis.from_url(REDIS_URL)`.
  - Add `get_redis_count()` — `GET counter`, returns `int(val)` if val
    is not None, else 0.
  - Add `increment_redis()` — `INCR counter`, returns new integer value.

### Files to Create

None beyond what ticket 001 established.

### Documentation Updates

None required for this ticket.
