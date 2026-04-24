---
id: '003'
title: ssh-transfer image tag reconciliation with compose image field
status: in-progress
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# ssh-transfer image tag reconciliation with compose image field

## Description

`_get_buildable_images()` in `src/rundbat/deploy.py` currently derives
image names purely from the compose project-dir naming convention
(`<project>-<service>`). Now that the generator emits explicit
`image:` fields, the ssh-transfer `docker save | docker load` pipe
must transfer the tag that the remote stack actually references.

Change `_get_buildable_images()` to prefer the service's `image:`
field (if declared in the compose YAML) and fall back to the
`<project>-<service>` default only when no `image:` is set. Services
with only `image:` and no `build:` stay excluded (nothing to build
or transfer).

Bump `pyproject.toml` version.

## Acceptance Criteria

- [ ] `_get_buildable_images()` returns the `image:` field value for
      any service that has both `image:` and `build:`.
- [ ] Services with `build:` but no `image:` still resolve to the
      compose-default `<project>-<service>` (regression preserved).
- [ ] Services with only `image:` and no `build:` are excluded
      (current behavior preserved).
- [ ] New unit tests cover: image+build present → image tag;
      build only → default tag; image only → excluded.
- [ ] `uv run pytest` passes.
- [ ] Version bumped in `pyproject.toml`.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_deploy.py`
  (if present) and full suite.
- **New tests to write**: three-case unit test for
  `_get_buildable_images()` as above.
- **Verification command**: `uv run pytest`
