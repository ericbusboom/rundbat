---
id: '003'
title: Update Justfile generator and tests
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
todo: ''
---

# Update Justfile generator and tests

## Description

Update `generate_justfile()` in `generators.py` to emit a
`rundbat deploy` recipe instead of the current stub
(`docker compose up -d --pull always`).

The new deploy recipe:
```just
# Deploy to a remote environment
deploy env="prod":
    rundbat deploy {{env}}
```

Remove the stub push recipe since deploy handles everything.

## Acceptance Criteria

- [ ] `generate_justfile()` emits `rundbat deploy {{env}}` for the deploy recipe
- [ ] Deploy recipe has a default `env` parameter
- [ ] Existing recipes (build, up, down, logs, restart) unchanged
- [ ] `tests/unit/test_generators.py` updated with new assertions
- [ ] All existing generator tests still pass

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_generators.py`
- **New tests to write**: Update `TestGenerateJustfile` assertions for deploy recipe
- **Verification command**: `uv run pytest`
