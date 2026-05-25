# API Key Handling

Use local, ignored files or shell environment variables for API credentials. Do not put real keys in tracked files, generated reports, command examples, or command-line arguments.

## Recommended Local Setup

Store the key in the already-ignored local Claude settings file:

```bash
mkdir -p .claude
printf '{"OPENAI_API_KEY":"sk-..."}\n' > .claude/settings.local.json
chmod 600 .claude/settings.local.json
export OPENAI_API_KEY_FILE="$PWD/.claude/settings.local.json"
```

The Pouya scripts can read either:

- `OPENAI_API_KEY`
- `OPENAI_API_KEY_FILE`
- solver-specific overrides such as `AIDER_SOLVER_API_KEY` or `SWEA_SOLVER_API_KEY`

Prefer `OPENAI_API_KEY_FILE` for repeated local runs because it survives new shells without placing the secret in scripts or copied command logs.

## Rules Before Pushing To GitHub

- Keep `.claude/settings.local.json`, `.env`, `.env.local`, `.secrets/`, and generated `runs/` artifacts out of git.
- Use environment variables for subprocesses. Avoid CLI flags such as `--api-key ...` because live process lists can expose them while a run is active.
- Redact keys in metadata and logs. Redaction is a backup, not the primary protection.
- Commit only source code, scripts, docs, and small curated summaries. Keep full benchmark run directories local, or publish them separately through an artifact store, release asset, DVC, or Git LFS if needed.

Quick checks:

```bash
git check-ignore -v .claude/settings.local.json .env .env.local .secrets/test runs/test
git grep -nE 'sk-(proj|admin|svcacct)-' -- . ':!runs' ':!bench_env' ':!.vendor'
```

The grep command should return no real keys before pushing.
