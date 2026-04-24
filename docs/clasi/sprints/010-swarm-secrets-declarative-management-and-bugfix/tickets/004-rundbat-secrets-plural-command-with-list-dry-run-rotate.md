---
id: "004"
title: "rundbat secrets plural command with list dry-run rotate"
status: todo
use-cases: [SUC-004]
depends-on: ['003']
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# rundbat secrets plural command with list dry-run rotate

## Description

Add `rundbat secrets <env>` (plural) which walks the declarative
`secrets:` block and batch-creates / lists / rotates the secrets.

### Subcommand surface (single command, mode flags)

```
rundbat secrets <env>                  # create all (idempotent)
rundbat secrets <env> --list           # report present-vs-missing
rundbat secrets <env> --dry-run        # print docker calls only
rundbat secrets <env> --rotate <target>
```

`--list` and `--dry-run` are mutually exclusive with `--rotate`.

### State

Query the manager directly. No state file. Implementation:

```python
def _list_swarm_secrets(ctx: str, prefix: str) -> dict[str, str]:
    """Return {target: latest_versioned_name} on the manager."""
    out = _run_cmd_capture(["docker", "--context", ctx, "secret",
                            "ls", "--filter", f"name={prefix}",
                            "--format", "{{.Name}}"])
    # Parse names of the form <prefix>_<target>_v<YYYYMMDD>;
    # group by target, pick the highest dated version.
    ...
```

### Default action (idempotent create)

For each declared target:
1. Compute the desired versioned external name
   (`{app}_{target}_v{YYYYMMDD}`)
2. If a secret with the same name already exists on the manager,
   skip
3. Otherwise pipe the value (resolved per `from_env` / `from_file`)
   into `docker --context <mgr> secret create <name> -`

### `--list`

Print a table: target, declared source, latest version on
manager (or `(missing)`), age. JSON form available with
`--json`.

### `--dry-run`

Like default, but for each target print the docker command that
would run with stdin redacted, and skip execution.

### `--rotate <target>`

1. Resolve the target in the declarative map
2. Compute the new versioned name
3. Pipe the value into `docker secret create <new>`
4. For each service in the target's `services:` list, run
   `docker --context <mgr> service update --secret-rm <old>
   --secret-add source=<new>,target=<target> <stack>_<service>`
5. Poll service tasks via `docker service ps` until all listed
   services have a running task on the new spec or until a 90s
   timeout
6. On success, run `docker secret rm <old>`

If step 4 or 5 fails, leave the new secret in place, do not remove
the old one, and exit non-zero with a clear message describing
which step failed and what cleanup the operator should do.

### Manager context

Use `manager_context_for(deployment_cfg)` (placeholder allowed
here; T05 adds the actual `manager:` field — a ternary fallback
to `docker_context` is fine in this ticket and gets cleaned up
in T05).

## Acceptance Criteria

- [ ] `rundbat secrets <env>` exists as a top-level CLI subcommand
- [ ] Default action is idempotent — running it twice creates each
      secret only once
- [ ] `--list` reports each declared target's status
      (present/missing) with `--json` machine-readable form
- [ ] `--dry-run` never runs `docker secret create`
- [ ] `--rotate <target>` performs create → swap → wait → remove
      and exits non-zero with a clear message on partial failure
- [ ] Tests cover: list logic against mocked `docker secret ls`,
      idempotent-create skip behavior, dry-run no-execute,
      rotation success path, rotation partial-failure path
- [ ] Version bumped via `clasi version bump`
- [ ] All tests pass; commit references T04

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**:
  - `test_secrets_list_present_missing` — mocked `docker secret ls`
    output produces correct present/missing report
  - `test_secrets_default_idempotent` — second run does not
    re-create
  - `test_secrets_dry_run_no_execute` — no `docker secret create`
    invoked
  - `test_secrets_rotate_success` — full create → update → poll →
    remove sequence
  - `test_secrets_rotate_partial_failure_keeps_old` — failure in
    swap leaves old secret intact and exits non-zero
- **Verification command**: `uv run pytest`
