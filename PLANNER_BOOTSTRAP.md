# Planner Bootstrap Workflow

Use this flow to avoid full-repo rescans on every planning round.

## Command

```powershell
pwsh -File tools/update_bootstrap.ps1
```

Outputs:
- `PROJECT_BOOTSTRAP.md` (human-readable snapshot)
- `artifacts/project_bootstrap.json` (machine-readable snapshot)

Cost model:
- The script runs locally in PowerShell and does not call Codex.
- Token usage only occurs when Codex reads the small snapshot files.

## Standard Planner Startup
1. Run the bootstrap command.
2. Read `PROJECT_BOOTSTRAP.md`.
3. Only then deep-read targeted source/docs needed for the current request.
4. Generate task prompts using `PLANNER_PROMPT_TEMPLATE.md`.

## Incremental Update Loop
1. Receive worker handoff.
2. Validate requirement coverage + tests + commit hash.
3. Integrate (cherry-pick/merge).
4. Re-run bootstrap command.
5. Plan next batch from refreshed snapshot.

## Source of Truth Priority
1. `REQUIREMENTS_BASELINE.md` for requirement IDs and release gates.
2. `TASKS.md` for coarse backlog status.
3. `PLANNER_PROMPT_TEMPLATE.md` for delegation contract.
4. `PROJECT_BOOTSTRAP.md` for startup cache and recency hints.

## Notes
- Treat bootstrap as a fast cache; refresh whenever in doubt.
- Use "likely closed gaps" in bootstrap as hints, then update baseline docs explicitly when confirmed.
- Default recency is git-based for speed; pass `-UseFilesystemScan` only when you need timestamp-based discovery beyond git history.
