---
status: ready
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010 Use Cases

## SUC-001: Operator creates a swarm secret that actually works

- **Actor**: Project operator running `rundbat` against a swarm deployment
- **Preconditions**: Project has dotconfig set up with a key in its
  encrypted secrets. Deployment has `swarm: true` and a
  `docker_context`.
- **Main Flow**:
  1. Operator runs `rundbat secret create prod MEETUP_CLIENT_ID`.
  2. rundbat calls `dotconfig load -d prod --no-export --json --flat
     -S` and parses the JSON dict.
  3. The key is found; the value is the byte-for-byte plaintext
     (no `export ` prefix, no surrounding quotes, no inline-comment
     suffix).
  4. rundbat pipes the value into `docker --context <mgr> secret
     create <app>_<key_lc>_v<YYYYMMDD> -` on stdin.
- **Postconditions**: `docker secret inspect` shows the secret
  exists; the data field matches the dotconfig value byte-for-byte.
  Pre-fix bug behavior ("Key not found") is gone.
- **Acceptance Criteria**:
  - [ ] Plain string values create cleanly
  - [ ] Single-quoted, double-quoted, and `#`-bearing values create
        without quote / comment artifacts
  - [ ] Regression test asserts byte-for-byte content via the parse
        path

## SUC-002: Project declares swarm secrets in rundbat.yaml

- **Actor**: Project owner adding swarm secrets to a rundbat project
- **Preconditions**: A swarm deployment exists in `rundbat.yaml`.
- **Main Flow**:
  1. Owner adds a `secrets:` block under `deployments.<env>` in
     `rundbat.yaml` using the per-target map form.
  2. Owner runs `rundbat generate prod`.
  3. The generated compose file attaches each secret only to its
     listed services. Each service gets the matching `*_FILE` env
     var only for the secrets it owns (env-backed only — file-backed
     secrets do not auto-emit `*_FILE`).
  4. The top-level `secrets:` block lists every declared secret as
     `external: true`.
- **Postconditions**: No service receives credentials it does not
  need; the "don't share credentials" rule is enforced by config.
- **Acceptance Criteria**:
  - [ ] Per-target map schema is parsed and validated at config load
  - [ ] Flat list `secrets: [KEY1]` keeps working as a back-compat
        shorthand expanding to
        `{KEY1: {from_env: KEY1, services: [app]}}`
  - [ ] Generator emits per-service attachments matching `services:`
  - [ ] An invalid schema (both `from_env` and `from_file` set, or
        neither) raises a clear `ConfigError`

## SUC-003: Operator stores a file-based secret

- **Actor**: Operator with a SOPS-encrypted file in dotconfig (PEM,
  TLS cert, JSON service-account blob)
- **Preconditions**: dotconfig has a `--file` entry the operator
  wants surfaced as a Swarm secret.
- **Main Flow**:
  1. Singular: `rundbat secret create prod --from-file stu1884.pem
     --target-name meetup_private_key` pipes
     `dotconfig load -d prod --file stu1884.pem --stdout` into
     `docker --context <mgr> secret create
     <app>_meetup_private_key_v<YYYYMMDD> -`.
  2. Declarative: `rundbat.yaml` declares
     `meetup_private_key: {from_file: stu1884.pem, services: [cron]}`;
     `rundbat secrets prod` dispatches `from_file` entries through
     the same code path.
  3. Generator emits the attachment to the listed services with no
     `*_FILE` env var by default.
- **Postconditions**: File-based secrets work end-to-end with no
  scripted bash.
- **Acceptance Criteria**:
  - [ ] `--from-file <path>` flag exists on `rundbat secret create`
  - [ ] `--target-name <name>` flag exists for file-based secrets
  - [ ] Declarative `from_file` entries flow through the same path
  - [ ] No `*_FILE` env var emitted automatically for `from_file`
        entries (env-backed entries still emit it)

## SUC-004: Operator manages secrets in bulk

- **Actor**: Operator deploying or rotating swarm secrets
- **Preconditions**: `rundbat.yaml` has a populated `secrets:`
  block.
- **Main Flow**:
  1. `rundbat secrets prod --list` queries `docker --context <mgr>
     secret ls --filter name=<app>_` and prints a present/missing
     report against the declared targets.
  2. `rundbat secrets prod` (no flags) creates each missing secret
     idempotently using the versioned external name.
  3. `rundbat secrets prod --dry-run` prints the docker commands
     that would execute (stdin redacted).
  4. `rundbat secrets prod --rotate api_token` creates a new
     versioned secret, issues `docker service update --secret-rm
     <old> --secret-add source=<new>,target=api_token` against each
     service attaching `api_token`, polls tasks until convergence,
     and removes the old version.
- **Postconditions**: Secrets are managed declaratively; rotation
  is auditable.
- **Acceptance Criteria**:
  - [ ] `--list` reports each declared target's status
  - [ ] Default action is idempotent (no-op when up to date)
  - [ ] `--dry-run` never runs `docker secret create`
  - [ ] `--rotate` performs the full create → swap → wait → remove
        sequence and stops cleanly on partial failure

## SUC-005: Manager context is separate from runtime context

- **Actor**: Operator running on a multi-context swarm cluster
- **Preconditions**: Deployment specifies `manager: swarm1` and
  `docker_context: swarm2`.
- **Main Flow**:
  1. `rundbat secrets prod --list` targets `docker --context
     swarm1 secret ls`.
  2. `rundbat up prod` targets `docker --context swarm2 stack
     deploy …`.
  3. `rundbat down prod` targets `docker --context swarm2 stack rm
     …`.
- **Postconditions**: Secret-management commands and lifecycle
  commands route to the right context. When `manager:` is omitted,
  it defaults to `docker_context` so single-context deployments are
  unaffected.
- **Acceptance Criteria**:
  - [ ] `manager:` field is optional and defaults to `docker_context`
  - [ ] Secret-related commands target `manager`
  - [ ] Lifecycle commands (`up`, `down`, `restart`, `logs`)
        continue targeting `docker_context`
  - [ ] Skill `docker-secrets-swarm.md` documents the split
