---
id: "005"
title: "Manager field and skill doc refresh"
status: todo
use-cases: [SUC-005]
depends-on: ['004']
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Manager field and skill doc refresh

## Description

Promote the `manager_context_for()` helper from a placeholder into
a real config-driven field, and rewrite `docker-secrets-swarm.md`
to describe the post-T04 interface end-to-end.

### Config

Add an optional `manager:` field per deployment in `rundbat.yaml`:

```yaml
deployments:
  prod:
    docker_context: swarm2
    manager: swarm1
    swarm: true
```

Implementation: `manager_context_for(deployment_cfg)` returns
`deployment_cfg.get("manager") or deployment_cfg["docker_context"]`.
This is the only place the routing rule lives.

Apply it in:
- `cmd_secret_create` (singular)
- `cmd_secrets` and helpers (plural)
- Any other secret-related code path introduced earlier

Lifecycle commands (`up`, `down`, `restart`, `logs`) keep using
`docker_context` — do not change them.

### Skill / docs refresh

Rewrite `src/rundbat/content/skills/docker-secrets-swarm.md`:

- Drop the back-fill workflow about `name:` overrides on the
  external secret entry — rotation now runs through
  `rundbat secrets <env> --rotate <target>`
- Replace the flat-list example with the per-target map example
  (mention that flat-list still works as a shorthand)
- Document the `manager:` field and how secret commands route
  there
- Document `rundbat secrets` (`--list`, `--dry-run`,
  `--rotate <target>`) and `rundbat secret create --from-file`
- Remove any "hand-edit the compose file" residue if it remains

Touch up `src/rundbat/content/skills/docker-secrets.md` (the
router doc) if it points anywhere stale, and the deployment-expert
agent bullet (`.claude/agents/...` if applicable) if it
references the old interface.

### Sprint-close prep

This is the last ticket. After committing, leave the sprint
ready for `mcp__clasi__close_sprint`. Do not tag manually — the
close call handles the tag (and per the kickoff, accept the
close-time pyproject regression).

## Acceptance Criteria

- [ ] `manager:` is an optional field on each deployment in
      `rundbat.yaml` (validated on load)
- [ ] `manager_context_for(deployment_cfg)` returns
      `manager` when set, else `docker_context`
- [ ] All secret-related commands route through
      `manager_context_for` (no remaining hardcoded
      `dep["docker_context"]` in secret code paths)
- [ ] `docker-secrets-swarm.md` describes the declarative schema,
      the plural command, `--from-file`, the `manager:` field, and
      rotation; no "hand-edit" residue remains
- [ ] Adjacent docs / skill files updated where they reference the
      pre-sprint interface
- [ ] New unit test verifies `manager_context_for` defaulting
- [ ] Version bumped via `clasi version bump`
- [ ] All tests pass; commit references T05

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**:
  - `test_manager_context_default` — when `manager:` absent, falls
    back to `docker_context`
  - `test_manager_context_explicit` — when `manager:` set, that
    value is used
  - `test_secret_commands_use_manager` — secret CLI commands pass
    `--context <manager>` (mocked via `_run_cmd*`)
- **Verification command**: `uv run pytest`
