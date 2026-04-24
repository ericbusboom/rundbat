---
id: "001"
title: "Swarm discovery: detect_swarm() in discovery.py"
status: todo
use-cases: [SUC-001]
depends-on: []
github-issue: ""
todo: swarm-support-in-rundbat.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# T01 — Swarm discovery: detect_swarm() in discovery.py

## Description

Add a new `detect_swarm(context: str) -> dict` function to
`src/rundbat/discovery.py`, modeled after the existing `detect_caddy()`
at discovery.py:157. The function probes a Docker context to determine
whether Swarm mode is active and the node's role.

Mechanism: run `docker info --format '{{json .Swarm}}'` under the
given Docker context via the existing `_run_command` helper. Parse
the JSON output and return:

```python
{
    "swarm": bool,           # True iff LocalNodeState == "active"
    "swarm_role": str,       # "manager" | "worker" | ""
    "reachable": bool,       # False if docker info failed to run
}
```

On non-zero exit, JSON-parse failure, or missing fields, return
`{"swarm": False, "swarm_role": "", "reachable": False}`. The probe
command (T02) interprets `reachable: False` via the transient-failure
rule — this function only reports facts.

## Affected Files

- `src/rundbat/discovery.py` — add `detect_swarm()` (NEW)
- `tests/unit/test_discovery.py` — add tests (NEW additions)

## Acceptance Criteria

- [ ] `detect_swarm(context)` exists in `src/rundbat/discovery.py`
- [ ] Runs `docker info --format '{{json .Swarm}}'` with
      `--context <context>`
- [ ] Parses JSON; returns `{swarm, swarm_role, reachable}`
- [ ] `LocalNodeState == "active"` → `swarm: True`
- [ ] `ControlAvailable: true` → `swarm_role: "manager"`; swarm
      active but not control-available → `"worker"`; inactive → `""`
- [ ] Non-zero exit → `{swarm: False, swarm_role: "", reachable: False}`
- [ ] JSON parse error → same fallback
- [ ] Docstring mirrors `detect_caddy`
- [ ] Unit tests cover: active-manager, active-worker, inactive,
      command-failed, bad-json
- [ ] `uv run pytest` passes
- [ ] `pyproject.toml` version bumped

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_discovery.py`
- **New tests to write**:
  - `test_detect_swarm_active_manager` — mocked subprocess returns
    `{"LocalNodeState":"active","ControlAvailable":true,...}`; assert
    `swarm=True`, `swarm_role="manager"`, `reachable=True`
  - `test_detect_swarm_active_worker` — `ControlAvailable: false`;
    assert `swarm_role="worker"`
  - `test_detect_swarm_inactive` — `LocalNodeState: "inactive"`;
    assert `swarm=False`, `swarm_role=""`, `reachable=True`
  - `test_detect_swarm_command_failed` — subprocess returncode=1;
    assert `reachable=False`, `swarm=False`
  - `test_detect_swarm_bad_json` — stdout is garbage; assert
    `reachable=False`, `swarm=False`
- **Verification command**: `uv run pytest`

## Notes

- Use the existing `_run_command` helper so tests can mock
  consistently.
- Bump `pyproject.toml` version per project rule.
