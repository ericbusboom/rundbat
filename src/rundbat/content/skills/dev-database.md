# dev-database

Quick local dev database via `docker run` (no compose needed).

## Steps

1. Load config: `dotconfig load -d dev --json --flat -S`
2. Check if database already exists: `rundbat health dev --json`
3. If not: `rundbat create-env dev --json`
4. Return connection string: `rundbat get-config dev --json`
