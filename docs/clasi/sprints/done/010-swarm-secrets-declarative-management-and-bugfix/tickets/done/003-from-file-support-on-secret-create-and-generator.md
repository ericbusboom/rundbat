---
id: '003'
title: From-file support on secret create and generator
status: done
use-cases:
- SUC-003
depends-on:
- '002'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# From-file support on secret create and generator

## Description

Add `--from-file` support to the singular `rundbat secret create`
command and wire `from_file` entries in the declarative schema
(T02) through the same path. The generator emits the secret
attachment without auto-creating a `*_FILE` env var (the user
adds it explicitly if their app needs it).

### CLI changes

Add to `cmd_secret_create`:
- `--from-file <path>` — path argument is a dotconfig `--file`
  source; rundbat runs
  `dotconfig load -d <env> --file <path> --stdout` and pipes the
  output into `docker secret create`
- `--target-name <name>` — the logical secret target. When
  `--from-file` is set, `--target-name` defaults to the file stem
  (e.g. `stu1884.pem` → `stu1884`); when omitted on env-var
  creation, behavior is unchanged
- `--from-env` and `--from-file` are mutually exclusive on the
  command line

### config.py

Add `load_env_file(env: str, filename: str) -> str`:

```python
def load_env_file(env: str, filename: str) -> str:
    """Decrypt and return the contents of a dotconfig --file entry."""
    return _run_dotconfig(["load", "-d", env, "--file", filename,
                           "--stdout"])
```

### Schema and generator

`from_file` entries flow through the normalized attachment shape
introduced in T02 with `source_kind == "file"`. The generator:

- Adds the per-service `secrets:` attachment exactly like
  env-backed secrets
- **Skips** `*_FILE` env-var emission for `source_kind == "file"`
- Adds the top-level external entry once

## Acceptance Criteria

- [x] `rundbat secret create <env> --from-file <path>
      [--target-name <name>]` succeeds end-to-end with mocked
      dotconfig + docker
- [x] `--from-file` and the positional `<KEY>` are mutually
      exclusive (clear error message)
- [x] `--target-name` defaults to the file stem when `--from-file`
      is set
- [x] `config.load_env_file(env, filename)` exists and is unit-tested
- [x] Schema validation accepts `from_file: <path>` per-target and
      rejects `from_file` + `from_env` together (the validation
      branch was scaffolded in T02; this ticket fills it in)
- [x] Generator emits per-service attachments for `from_file`
      entries with no `*_FILE` env var
- [x] New tests cover: singular CLI happy path, schema validation
      for file form, generator emission for file form
- [x] Version bumped via `clasi version bump`
- [x] All tests pass; commit references T03

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**:
  - `test_secret_create_from_file` — mocked dotconfig and docker;
    asserts the file content is piped to docker secret create
  - `test_secret_create_from_file_target_name_default` — file stem
    used when `--target-name` not given
  - `test_generator_from_file_no_env_var` — file-backed entries
    do not emit `*_FILE` env vars
- **Verification command**: `uv run pytest`
