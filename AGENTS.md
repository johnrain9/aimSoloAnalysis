# Repo Agent Instructions

## Planner Consistency
- When the user asks for planning, delegation, requirements management, or integration coordination, load `skills/planner-orchestrator/SKILL.md` first.
- Before broad repo exploration, run `pwsh -File tools/update_bootstrap.ps1` and read `PROJECT_BOOTSTRAP.md`.
- Treat `REQUIREMENTS_BASELINE.md`, `TASKS.md`, and `PLANNER_PROMPT_TEMPLATE.md` as canonical planning docs.

## Incremental State Updates
- Re-run `pwsh -File tools/update_bootstrap.ps1` after integrating each task batch.
- Prefer targeted reads based on recent-file and gap data from `PROJECT_BOOTSTRAP.md` instead of full directory scans.
