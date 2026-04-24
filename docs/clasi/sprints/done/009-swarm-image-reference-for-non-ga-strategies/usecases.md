---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 009 Use Cases

## SUC-001: Swarm-aware generate emits a deployable compose
Parent: Sprint 008 swarm follow-up

- **Actor**: Developer running `rundbat generate`
- **Preconditions**:
  - A deployment is configured with `swarm: true` and
    `build_strategy` in {`context`, `ssh-transfer`, `github-actions`}.
  - A valid `image:` is set on the deployment.
- **Main Flow**:
  1. Developer runs `rundbat generate`.
  2. Generator reads the deployment config.
  3. For swarm deployments, generator emits an `image:` field on the
     `app` service and also emits `build:` when the strategy builds
     on host.
  4. Compose file is written.
- **Postconditions**: `docker stack deploy -c <compose>` on the
  remote swarm succeeds — it has both a buildable source locally and
  an image reference for the swarm to pull/run.
- **Acceptance Criteria**:
  - [ ] Context-strategy swarm compose has both `image:` and `build:`.
  - [ ] ssh-transfer-strategy swarm compose has both `image:` and
        `build:`.
  - [ ] github-actions-strategy swarm compose has `image:` and no
        `build:` (unchanged from today).

## SUC-002: Missing image fails generate loudly
Parent: Sprint 008 swarm follow-up

- **Actor**: Developer running `rundbat generate`
- **Preconditions**: A deployment has `swarm: true` but no `image:`.
- **Main Flow**:
  1. Developer runs `rundbat generate`.
  2. Generator detects the missing image before writing files.
  3. Command exits non-zero with a clear error referencing the
     deployment name and suggesting remedies.
- **Postconditions**: No compose file written for the invalid
  deployment. The process does not proceed silently.
- **Acceptance Criteria**:
  - [ ] Error mentions the deployment name.
  - [ ] Error suggests `image: <tag>` or
        `build_strategy: github-actions`.
  - [ ] Exit code is non-zero (`_error`).
  - [ ] No partial compose file is left in `docker/`.

## SUC-003: deploy-init prompts for image when opting into stack mode
Parent: Sprint 008 swarm follow-up

- **Actor**: Developer running `rundbat deploy-init` interactively.
- **Preconditions**: Remote host is a Swarm manager, developer
  accepts the stack-mode opt-in, and the chosen strategy builds on
  host (context or ssh-transfer — i.e., not github-actions).
- **Main Flow**:
  1. After opt-in, `cmd_deploy_init` prompts for an image tag.
  2. User enters a tag (e.g. `myapp:prod`).
  3. Config is saved with `image: myapp:prod`.
- **Postconditions**: Subsequent `rundbat generate` succeeds
  immediately without a second manual edit.
- **Acceptance Criteria**:
  - [ ] Prompt appears for non-github-actions strategy + stack mode.
  - [ ] Default value shown is `<app_name>:<deployment_name>`.
  - [ ] `--json` path auto-fills the default tag (non-interactive).
  - [ ] Saved config has the `image` field set.
