---
status: draft
---

# Sprint 005 Use Cases

## SUC-001: Developer uses rundbat with clean 4-command surface

- **Actor**: Developer or AI agent
- **Preconditions**: rundbat installed
- **Main Flow**:
  1. `rundbat init` — sets up project, checks prerequisites, warns if
     Docker or dotconfig missing
  2. `rundbat init-docker` — generates Docker artifacts
  3. `rundbat deploy-init prod --host ssh://root@host` — sets up deploy target
  4. `rundbat deploy prod` — deploys
  5. For database ops, agent uses `docker compose` directly
  6. For secrets, agent uses `dotconfig` directly
- **Postconditions**: All workflows complete with 4 commands + compose + dotconfig
- **Acceptance Criteria**:
  - [ ] `rundbat --help` shows only init, init-docker, deploy, deploy-init
  - [ ] Skills guide agent to use compose/dotconfig for removed operations
  - [ ] init validates Docker and dotconfig are available
