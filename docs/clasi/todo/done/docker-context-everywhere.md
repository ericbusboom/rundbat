---
status: done
sprint: '005'
tickets:
- 005-004
---

# Use Docker contexts uniformly across all deployments

All deployments (dev, test, prod) should use named Docker contexts.
The generated Justfile uses `DOCKER_CONTEXT` env var so all docker
commands target the right host automatically.

## Changes

1. `rundbat init` detects the current default Docker context name
   (default, orbstack, colima, etc.) and stores it as `docker_context`
   for dev/test in rundbat.yaml
2. Config schema changes from `host` to `docker_context` in deployments
3. `deploy-init` creates a named context and stores context name
4. `deploy.py` uses `docker_context` from config instead of deriving it
5. Generated Justfile passes `DOCKER_CONTEXT` from config to all recipes
6. All recipes (up, down, build, logs, deploy) become context-aware
