# manage-secrets

Store and manage deployment secrets via dotconfig.

## Store a secret

```bash
rundbat set-secret <env> KEY=VALUE
```

## View current secrets (decrypted)

```bash
dotconfig load -d <env> --json -S
```

## Round-trip editing

```bash
dotconfig load -d <env> --json       # writes .env.json
# edit .env.json
dotconfig save --json                # writes back to config/
```
