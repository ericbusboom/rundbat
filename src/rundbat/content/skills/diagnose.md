# diagnose

Diagnose deployment issues — read state, compare config vs actual
container state, report problems.

## Steps

1. Load config: `dotconfig load -d {env} --json -S` (sectioned)
2. Check system: `rundbat discover --json`
3. Validate environment: `rundbat validate {env} --json`
4. If container issues: `docker inspect {container}` for details
5. Report findings with specific remediation steps
