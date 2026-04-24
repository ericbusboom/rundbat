---
status: done
sprint: '010'
tickets:
- '001'
---

# Bug: `rundbat secret create` can't find any dotconfig keys

`rundbat secret create <env> <KEY>` always returns
`"Key '<KEY>' not found in dotconfig env for '<env>'"` even when the
key is clearly present in the dotconfig output. Three independent
bugs in the `load_env` → `_parse_env_text` path; fixing just the first
gets past the error but would still produce wrong secret values.

## Environment

- rundbat: 0.20260424.6 (pipx-installed)
- dotconfig: 0.20260423.4 (JSON-prefix bug in dotconfig was fixed in
  this release — so this is no longer a dotconfig issue)

## Reproduction

Any project with a dotconfig-managed deployment. Example from
leaguesync:

```bash
$ rundbat secret create prod MEETUP_CLIENT_ID --json
{"error": "Key 'MEETUP_CLIENT_ID' not found in dotconfig env for 'prod'"}

$ dotconfig load -d prod --json --flat -S | jq 'keys | map(select(startswith("MEETUP")))'
[
  "MEETUP_AUTHORIZED_MEMBER_ID",
  "MEETUP_CLIENT_ID",
  "MEETUP_NETWORK_NAME",
  "MEETUP_PRIVATE_KEY"
]
```

The key exists in dotconfig but rundbat can't see it.

## Root cause

Three bugs in the `.env` parsing path:

### Bug 1 — `load_env` doesn't pass `--no-export`

`rundbat/config.py:131`:

```python
def load_env(env: str) -> str:
    """Load the assembled .env for a deployment via dotconfig (to stdout)."""
    return _run_dotconfig(["load", "-d", env, "--stdout"])
```

dotconfig's default output emits `export KEY=value` on every line. The
`--no-export` flag (shipped in dotconfig 0.20260423.3) strips that
prefix, but rundbat doesn't use it.

### Bug 2 — `_parse_env_text` keeps the `export ` prefix in keys

`rundbat/cli.py:864`:

```python
def _parse_env_text(text: str) -> dict:
    ...
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        if "=" not in line: continue
        key, value = line.split("=", 1)
        result[key.strip()] = value
    return result
```

For a line like `export MEETUP_CLIENT_ID='stu1884...'`, `split("=", 1)`
gives `key = "export MEETUP_CLIENT_ID"` (with the space, after strip).
The subsequent lookup `key not in env_map` (in `cmd_secret_create`)
correctly fails because it asks for `"MEETUP_CLIENT_ID"`.

### Bug 3 — values aren't unquoted

Same code as bug 2. For `MEETUP_CLIENT_ID='stu1884kfcr2sftkimel04d9lo'`,
the value captured is `"'stu1884kfcr2sftkimel04d9lo'"` — the surrounding
single quotes are included. rundbat pipes this value directly to
`docker secret create`, so the resulting Swarm secret would contain the
literal quotes around the value. Apps reading `/run/secrets/...`
would get `'stu1884...'` instead of `stu1884...`.

### Bug 4 — inline comments appear in values

dotconfig appends inline comments on some entries, e.g.:

```
export MEETUP_PRIVATE_KEY='config/files/stu1884.pem' # bTBcbbQC...
```

`split("=", 1)` on this line produces
`value = "'config/files/stu1884.pem' # bTBcbbQC..."`. That whole string
would be piped into `docker secret create`. The resulting secret would
have the comment suffix baked into its content.

## Fix — one-line, no parsing logic

Stop doing `.env` text parsing entirely. Use dotconfig's JSON output,
which gives a clean dict directly:

```python
# rundbat/config.py
import json

def load_env_dict(env: str) -> dict:
    """Load a deployment's merged env as a {KEY: value} dict."""
    out = _run_dotconfig(["load", "-d", env, "--no-export",
                          "--json", "--flat", "-S"])
    return json.loads(out)
```

Then in `rundbat/cli.py::cmd_secret_create`:

```python
env_map = config.load_env_dict(env_name)
if key not in env_map:
    _error(f"Key '{key}' not found in dotconfig env for '{env_name}'", args.json)
    return
value = env_map[key]
```

This kills all four bugs at once:

- No `export ` prefix (dotconfig strips it in `--no-export` mode)
- Proper unquoting (JSON string decoding handles this natively)
- Inline comments are already stripped by dotconfig before JSON
  serialization (verified against 0.20260423.4 output)
- No regex, no string splitting, no edge cases

`_parse_env_text` can stay for callers that need the raw text, but
secret creation should use the dict path.

## Acceptance criteria

- [ ] `rundbat secret create <env> <KEY>` succeeds for any key present
      in the deployment's dotconfig env
- [ ] The created Swarm secret's content matches the raw dotconfig value
      byte-for-byte (no surrounding quotes, no inline comments, no
      leading/trailing whitespace from line continuation)
- [ ] Test values that exercise each edge case:
  - Plain string: `FOO=bar`
  - Single-quoted: `FOO='bar baz'`
  - Double-quoted: `FOO="bar baz"`
  - With `#` in the value (comment-like but actual content)
  - With inline dotconfig comment: `FOO='bar' # hash:abc`
  - Multi-line value (PEM key style with embedded newlines — this may
    need a separate path via `dotconfig load --file` anyway)
- [ ] A regression test: call `rundbat secret create` against a fixture
      dotconfig deployment, verify `docker secret inspect` shows the
      correct byte-for-byte content

## Adjacent: file-based values

The current command takes only an env-var key. Swarm-secret-worthy
values are sometimes files (PEM keys, certs, TLS bundles) stored via
`dotconfig save --file`. Add a `--from-file <filename>` flag so:

```bash
rundbat secret create prod --from-file stu1884.pem \
                           --target-name meetup_private_key
```

pipes `dotconfig load -d prod --file stu1884.pem --stdout` into
`docker secret create`. This is the other half of why leaguesync's
`prod-make-secrets.sh` can't be replaced yet.

## Priority

Blocks the `rundbat secret create` command from being usable in any
project. Once fixed (plus the `--from-file` addition) leaguesync can
delete `docker/prod-make-secrets.sh`.
