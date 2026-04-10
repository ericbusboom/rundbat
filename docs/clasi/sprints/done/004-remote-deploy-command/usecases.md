---
status: draft
---

# Sprint 004 Use Cases

## SUC-001: Developer deploys to a named remote host

- **Actor**: Developer (human or AI agent)
- **Preconditions**:
  - `rundbat.yaml` has a `deployments.prod` entry with `host` and
    `compose_file`.
  - SSH access to the host works (key already distributed).
  - Docker is running locally.
- **Main Flow**:
  1. Developer runs `rundbat deploy prod`.
  2. rundbat reads the `prod` deployment config from `rundbat.yaml`.
  3. rundbat ensures a Docker context exists (creates one if needed from
     the `host` field).
  4. rundbat runs `docker --context <ctx> compose -f <file> up -d --build`.
  5. rundbat prints success summary with hostname if configured.
- **Postconditions**:
  - Application is running on the remote host.
- **Acceptance Criteria**:
  - [ ] `rundbat deploy prod` completes without error when SSH works.
  - [ ] `--json` returns structured result with status and command run.
  - [ ] `--dry-run` prints command without executing.
  - [ ] `--no-build` skips the build step.
  - [ ] Clear error if deployment name not found in config.

## SUC-002: Developer sets up a new deploy target

- **Actor**: Developer
- **Preconditions**:
  - SSH access to remote host works.
  - Docker is installed on the remote host.
- **Main Flow**:
  1. Developer runs `rundbat deploy-init prod --host ssh://root@docker1.example.com`.
  2. rundbat verifies SSH+Docker access: `ssh root@host docker info`.
  3. rundbat creates Docker context: `docker context create <app>-prod`.
  4. rundbat adds `deployments.prod` to `rundbat.yaml`.
  5. rundbat confirms setup complete.
- **Postconditions**:
  - Docker context exists locally.
  - `rundbat.yaml` has the deployment config.
  - `rundbat deploy prod` is ready to use.
- **Acceptance Criteria**:
  - [ ] Verifies SSH+Docker connectivity before saving config.
  - [ ] Creates Docker context with correct host.
  - [ ] Saves deployment entry to `rundbat.yaml`.
  - [ ] Works with pre-existing Docker contexts (skips creation).

## SUC-003: AI agent deploys via Justfile

- **Actor**: AI coding agent
- **Preconditions**:
  - Generated Justfile has `rundbat deploy` recipe.
  - Deploy config exists in `rundbat.yaml`.
- **Main Flow**:
  1. Agent runs `just deploy prod` or `rundbat deploy prod --json`.
  2. rundbat deploys and returns JSON output.
  3. Agent reads result to confirm success.
- **Acceptance Criteria**:
  - [ ] Generated Justfile has `rundbat deploy {{env}}` recipe.
  - [ ] `--json` output includes `status` field.
  - [ ] Non-zero exit code on failure.
