# diagnose

Read system and environment state, compare config against actual
container state, and report issues with specific remediation steps.

## When to use

- "My container won't start"
- "I can't connect to the database"
- "Something is wrong with my deployment"
- "Why isn't this working?"

## Steps

1. **Check system prerequisites:**
   ```bash
   rundbat discover --json
   ```
   Verify: Docker installed and running, dotconfig initialized.

2. **Validate the environment:**
   ```bash
   rundbat validate <env> --json
   ```
   This checks: config exists, secrets present, container running,
   database reachable. Each check reports ok/failed with detail.

3. **If validation fails, dig deeper:**

   - **Config missing?** → `rundbat init` or `rundbat create-env <env>`
   - **Secrets missing?** → Check `dotconfig load -d <env> --json -S`
     for DATABASE_URL. May need `rundbat set-secret`.
   - **Container not running?** → `rundbat start <env>` to restart.
     If missing, `rundbat create-env <env>` to recreate.
   - **Database unreachable?** → Check port conflicts:
     ```bash
     docker inspect <container> --format '{{json .NetworkSettings.Ports}}'
     ```

4. **Check for drift:**
   ```bash
   rundbat check-drift --json
   ```
   App name at source (package.json) may differ from stored name.

5. **Report findings** with specific commands the developer should run.

## Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Container not found" | Never created or was removed | `rundbat create-env <env>` |
| "Connection refused" | Container stopped | `rundbat start <env>` |
| "Port already in use" | Conflicting service | Stop conflicting service or `rundbat create-env <env>` (auto-allocates new port) |
| "SOPS decryption failed" | Missing age key | Run `dotconfig keys` to check key status |
| "Config file not found" | Not initialized | `rundbat init` |
