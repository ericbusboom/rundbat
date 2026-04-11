---
id: '006'
title: Guided deployment initialization skill
status: todo
use-cases: [SUC-006]
depends-on: ['001', '002', '003', '004', '005']
github-issue: ''
todo: plan-deployment-initialization-guided-setup-and-configuration-model.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Guided deployment initialization skill

## Description

Create skill files that guide Claude Code users through deployment initialization. The centerpiece is `deploy-init.md` — a skill with explicit `AskUserQuestion` steps that walks users through all configuration decisions and writes a complete deployment entry to `rundbat.yaml`. Also create `github-deploy.md` for GitHub Actions-specific guidance and `generate.md` for the generate command. Update `deploy-setup.md` to reference the new guided path.

This ticket is all skill file content — no Python code. It depends on Tickets 001–005 so that the commands the skill invokes (`rundbat generate`, `rundbat build`, `rundbat up`) are all implemented.

## Acceptance Criteria

- [ ] `src/rundbat/content/skills/deploy-init.md` exists and is installed via `rundbat install`.
- [ ] `deploy-init.md` includes trigger phrases: "I want to deploy", "Set up deployment", "Configure a deployment", "Deploy my application".
- [ ] `deploy-init.md` defines 8 explicit `AskUserQuestion` steps: target, services, deploy mode (single-service only), SSH host (remote only), domain name (remote only), build strategy (remote only), env config, summary+confirm.
- [ ] Step 3 (deploy mode) is explicitly skipped for multi-service deployments with a note that compose is required.
- [ ] Steps 4–6 (SSH, domain, build strategy) are skipped for `dev` and `local` targets.
- [ ] GitHub Actions path in Step 6 includes instructions to generate workflow files and configure GitHub secrets.
- [ ] Summary table (Step 8) shows all chosen values before writing config.
- [ ] After summary, skill invokes `rundbat deploy-init <name> --host ... --strategy ... --deploy-mode ...` and `rundbat generate`.
- [ ] `src/rundbat/content/skills/github-deploy.md` exists covering: trigger phrases, prerequisite steps, `rundbat build <name>` and `rundbat up <name> --workflow`, GitHub secrets reference.
- [ ] `src/rundbat/content/skills/generate.md` exists covering: trigger phrases for artifact generation, `rundbat generate` usage, explanation of per-deployment files.
- [ ] `src/rundbat/content/skills/deploy-setup.md` updated: references `deploy-init.md` for guided path, retains SSH troubleshooting table.
- [ ] `uv run pytest` passes (installer test that discovers skill files should now find the new files).

## Implementation Plan

### Approach

Write skill files as Markdown. No Python code changes. Verify `installer.py` auto-discovers files in `content/skills/` (it already does — no change needed).

### Files to Create

**`src/rundbat/content/skills/deploy-init.md`**: 8-step guided interview. Each step formatted as:
```
## Step N: <Title>

AskUserQuestion:
  question: "..."
  header: "..."
  options: [...]

After answer: <what to do based on answer>
```
Steps and branching logic exactly as specified in the TODO.

**`src/rundbat/content/skills/github-deploy.md`**: Trigger phrases, prerequisites (gh CLI installed, `rundbat generate` run), step-by-step for:
1. `rundbat deploy-init prod --strategy github-actions --deploy-mode compose`
2. `rundbat generate` (creates both workflows)
3. Configure GitHub secrets (DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY)
4. `rundbat build prod` (triggers build workflow)
5. Monitor via `gh run watch`
6. `rundbat up prod --workflow` (triggers deploy workflow)

**`src/rundbat/content/skills/generate.md`**: Trigger phrases ("Generate Docker files", "Run rundbat generate"), what the command produces (one compose per deployment, Justfile recipes, Dockerfile, entrypoint, env files), when to re-run (after config changes).

### Files to Modify

**`src/rundbat/content/skills/deploy-setup.md`**: Add at top: "For guided setup, use the deploy-init skill (say 'I want to deploy'). This document covers manual steps and SSH troubleshooting." Simplify the intro section.

### Testing Plan

- No new unit tests needed for skill files themselves.
- Run `uv run pytest` to confirm no regressions. The installer test should pass with the new skill files discovered.
- Manual verification: run `rundbat install` in a test project and confirm new skill files appear in `.claude/`.
