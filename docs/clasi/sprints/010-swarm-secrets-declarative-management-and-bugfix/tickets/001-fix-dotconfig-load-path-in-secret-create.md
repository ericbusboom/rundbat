---
id: '001'
title: Fix dotconfig load path in secret create
status: in-progress
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo: secret-create-cannot-find-dotconfig-keys.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix dotconfig load path in secret create

## Description

`rundbat secret create <env> <KEY>` is unusable: it always returns
"Key not found" even when the key is plainly present in
`dotconfig load -d <env>`. The cause is that `cmd_secret_create`
uses `_parse_env_text` against dotconfig's default text output,
which (1) keeps the `export ` prefix in keys, (2) leaves quotes
around values, and (3) folds inline comments into values.

Fix: stop parsing text. Use dotconfig's JSON output, which is a
clean dict.

### Implementation

Add `load_env_dict(env: str) -> dict` in `src/rundbat/config.py`:

```python
def load_env_dict(env: str) -> dict:
    """Load a deployment's merged env as a {KEY: value} dict."""
    out = _run_dotconfig(["load", "-d", env, "--no-export",
                          "--json", "--flat", "-S"])
    return json.loads(out)
```

In `src/rundbat/cli.py::cmd_secret_create`, replace the text-parse
block with `env_map = config.load_env_dict(env_name)` and look up
`env_map[key]` directly.

Leave `_parse_env_text` and `load_env` in place — other callers
(if any) keep working; only the secret command moves over.

### Also do this commit

- Stage and commit the `.clasi-oop` marker (already created at
  session start) so subsequent code work writes directly per the
  established sprint 008/009 pattern.
- Run `clasi version bump` (no `--tag`, no `--push`).

## Acceptance Criteria

- [x] `src/rundbat/config.py` has `load_env_dict(env)` returning a
      `dict[str, str]` from
      `dotconfig load -d <env> --no-export --json --flat -S`
- [x] `cmd_secret_create` uses `load_env_dict` (no `_parse_env_text`
      call in the secret-create code path)
- [x] Regression test exercises `load_env_dict` with a
      monkeypatched dotconfig response covering plain, single-quoted,
      double-quoted, `#`-in-value, and inline-comment cases; asserts
      the returned dict contains the unquoted plaintext for each
- [x] Regression test calls `cmd_secret_create` with mocked dotconfig
      + docker and asserts (a) the key is found, (b) the value
      piped to `docker secret create` is the unquoted plaintext
      byte-for-byte, (c) the secret name has the format
      `<app>_<key_lc>_v<YYYYMMDD>`
- [x] `.clasi-oop` marker committed
- [x] Version bumped via `clasi version bump`
- [x] All tests pass (`uv run pytest`)
- [x] Commit message references T01

## Testing

- **Existing tests to run**: `uv run pytest` — all 294+ tests must pass
- **New tests to write**: see acceptance criteria above
- **Verification command**: `uv run pytest`
