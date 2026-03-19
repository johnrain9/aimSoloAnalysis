import json
import subprocess
from pathlib import Path

from tools import update_bootstrap


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Bootstrap Test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "bootstrap baseline"], cwd=repo_root, check=True)


def test_build_snapshot_writes_planner_critical_outputs(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "TASKS.md").write_text("- [todo] TASK-1: test task\n- [done] TASK-2: closed\n", encoding="utf-8")
    (repo_root / "REQUIREMENTS_BASELINE.md").write_text(
        "- GAP-010 (High): example unresolved gap.\n",
        encoding="utf-8",
    )
    (repo_root / "PLANNER_PROMPT_TEMPLATE.md").write_text("# prompt\n", encoding="utf-8")
    skill_dir = repo_root / "skills" / "planner-orchestrator"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    tracked = repo_root / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")

    _init_git_repo(repo_root)

    tracked.write_text("tracked but dirty\n", encoding="utf-8")

    snapshot = update_bootstrap.build_snapshot(
        repo_root=repo_root,
        recent_commit_count=5,
        recent_file_count=5,
        use_filesystem_scan=False,
    )
    output_markdown = repo_root / "PROJECT_BOOTSTRAP.md"
    output_json = repo_root / "artifacts" / "project_bootstrap.json"
    update_bootstrap.write_snapshot(snapshot, output_markdown=output_markdown, output_json=output_json)

    markdown = output_markdown.read_text(encoding="utf-8")
    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert "Refresh with `python3 tools/update_bootstrap.py`." in markdown
    assert payload["repo"]["dirty"] is True
    assert any(item.startswith("[todo] TASK-1") for item in payload["open_task_items"])
    assert payload["active_gaps"] == ["GAP-010 (High): example unresolved gap."]
    assert payload["planner_entrypoints"][-1] == "skills/planner-orchestrator/SKILL.md"
    assert set(payload.keys()) == {
        "generated_at",
        "repo",
        "recent_commits",
        "recent_files",
        "likely_closed_gaps",
        "active_gaps",
        "open_task_items",
        "planner_entrypoints",
    }


def test_build_snapshot_can_fall_back_to_filesystem_recent_files(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "TASKS.md").write_text("- [in-progress] TASK-1: test task\n", encoding="utf-8")
    (repo_root / "REQUIREMENTS_BASELINE.md").write_text("", encoding="utf-8")
    (repo_root / "PLANNER_PROMPT_TEMPLATE.md").write_text("# prompt\n", encoding="utf-8")
    skill_dir = repo_root / "skills" / "planner-orchestrator"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    newest = repo_root / "newest.txt"
    newest.write_text("newest\n", encoding="utf-8")

    snapshot = update_bootstrap.build_snapshot(
        repo_root=repo_root,
        recent_commit_count=3,
        recent_file_count=3,
        use_filesystem_scan=True,
    )

    assert snapshot["recent_files"]
    assert any(item["path"] == "newest.txt" for item in snapshot["recent_files"])
