---
id: '002'
title: Probe records Swarm state in rundbat.yaml
status: in-progress
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T02 — Probe records Swarm state in rundbat.yaml

## Description

Extend `cmd_probe` at `src/rundbat/cli.py:280` to call the new
`detect_swarm(context)` helper (from T01) alongside the existing
Caddy detection. Write the result back into the deployment entry in
`rundbat.yaml`.

Fields written to the deployment entry:
- `swarm: true | false | "unknown"`
- `swarm_role: "manager" | "worker"` (omit when `swarm` is `unknown`
  or `false`)

**Transient-failure rule** (pre-resolved, per architecture doc):

| Prior `swarm` | Probe result | Action |
|---|---|---|
| absent / false | reachable, not swarm | write `swarm: false` |
| absent / false | reachable, swarm | write `swarm: true` + role |
| absent / false | unreachable | write `swarm: "unknown"`, omit role |
| true | reachable, not swarm | write `swarm: false` (explicit downgrade; probe saw a reachable daemon) |
| true | reachable, swarm | write `swarm: true` + role |
| true | unreachable | **do NOT overwrite**; leave `swarm: true` |

Invariant: an unreachable probe MUST NOT silently downgrade
`swarm: true` to `swarm: false`.

## Affected Files

- `src/rundbat/cli.py` — `cmd_probe` (EDIT around cli.py:280)
- `tests/unit/test_cli.py` — add probe-with-swarm tests (NEW
  additions)

## Acceptance Criteria

- [x] `cmd_probe` calls `detect_swarm(context)` after the Caddy probe
- [x] `swarm` and `swarm_role` are written to the deployment entry
      (subject to the transient-failure rule)
- [x] Unreachable probe with prior `swarm: true` does NOT overwrite
- [x] `swarm: "unknown"` is written only when prior is absent AND
      probe is unreachable
- [x] Probe still records `reverse_proxy` (regression)
- [x] `--json` output (if supported) includes swarm fields
- [x] Unit tests cover all six rows of the transient-failure table
- [x] `uv run pytest` passes
- [x] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_cli.py`
- **New tests to write**:
  - `test_probe_writes_swarm_true_manager`
  - `test_probe_writes_swarm_false_when_inactive`
  - `test_probe_transient_failure_preserves_true`
  - `test_probe_unreachable_from_absent_writes_unknown`
  - `test_probe_reachable_downgrades_explicit_true_to_false`
  - `test_probe_still_records_caddy`
- **Verification command**: `uv run pytest`

## Notes

- Depends on T01 — `detect_swarm` must exist. Mock it in unit tests.
- Bump `pyproject.toml` version.
