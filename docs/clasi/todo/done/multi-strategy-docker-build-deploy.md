---
status: done
sprint: '005'
tickets:
- 005-005
---

# Multi-Strategy Docker Build & Deploy

Add three configurable build strategies per deployment in `rundbat.yaml`
so users can choose how images are built and delivered to remote hosts,
especially when local and remote architectures differ (e.g., Apple
Silicon → x86_64 Linux VPS).

## Strategies

1. **`context`** — Current Docker context behavior. Builds happen
   wherever the context points. Add post-deploy cleanup (`docker system
   prune -f`) to reclaim disk on small machines.

2. **`ssh-transfer`** — Build locally with `docker compose build
   --platform <remote-arch>`, then `docker save | ssh host docker load`,
   then `compose up -d` (no `--build`). Zero infrastructure needed,
   works offline. Requires Docker buildx for cross-platform builds.

3. **`github-actions`** — CI builds the image on push, pushes to GHCR
   (GitHub Container Registry), remote pulls. Push uses built-in
   `GITHUB_TOKEN` (zero config). Public repos need no pull auth; private
   repos use a PAT stored in dotconfig secrets.

## Config Changes

Each deployment in `rundbat.yaml` gets new fields:

```yaml
deployments:
  prod:
    build_strategy: ssh-transfer   # context | ssh-transfer | github-actions
    docker_context: proj-prod
    compose_file: docker/docker-compose.prod.yml
    host: ssh://root@host          # persisted (currently lost after init)
    platform: linux/amd64          # auto-detected from remote
    hostname: myapp.example.com
```

## Key Work Items

- **`discovery.py`**: Add `local_docker_platform()` helper
- **`deploy.py`**: Add helpers for remote platform detection, local
  build, image transfer, remote cleanup. Modify `deploy()` to branch on
  strategy. Persist `host` and `platform` in `init_deployment()`.
- **`cli.py`**: Add `--strategy` and `--platform` flags to deploy
  commands.
- **`generators.py`**: Update Justfile with `PLATFORM` variable and
  `deploy-transfer` recipe. Add `generate_github_workflow()` for the
  Actions strategy. Auto-add `LABEL org.opencontainers.image.source` to
  Dockerfile for GHCR visibility linking.
- **New skill `deploy-setup.md`**: Guided setup flow that walks users
  through SSH key generation, strategy selection, and strategy-specific
  config (buildx check, GHCR PAT for private repos, GitHub workflow
  generation, GitHub secrets setup).
- **Update `deployment-expert.md`**: Add strategies to decision
  framework.
- **`installer.py`**: Add new skill to manifest.
- **Tests**: Cover all three strategy paths, platform detection, image
  transfer, cleanup, and config persistence.

## References

- Full plan: `.claude/plans/twinkling-stargazing-clover.md`
