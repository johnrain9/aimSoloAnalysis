"""Generate planner bootstrap snapshots without requiring PowerShell."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

EXCLUDED_PARTS = {".git", ".worktrees", "__pycache__", ".pytest_cache"}
PLANNER_ENTRYPOINTS = [
    "PROJECT_BOOTSTRAP.md",
    "REQUIREMENTS_BASELINE.md",
    "TASKS.md",
    "PLANNER_PROMPT_TEMPLATE.md",
    "skills/planner-orchestrator/SKILL.md",
]


def _git_lines(repo_root: Path, args: Sequence[str]) -> List[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    if result.returncode != 0:
        return []

    return [line for line in result.stdout.splitlines() if line is not None]


def _read_pattern_lines(path: Path, pattern: str) -> List[str]:
    if not path.exists():
        return []

    matcher = re.compile(pattern)
    lines: List[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if matcher.search(raw_line):
            lines.append(re.sub(r"^- ", "", raw_line.strip()))
    return lines


def _is_excluded_path(path: str) -> bool:
    if not path or not path.strip():
        return True
    parts = {part for part in Path(path).parts if part}
    return bool(parts & EXCLUDED_PARTS)


def _strip_status_path(status_line: str) -> str:
    raw = status_line[3:].strip() if len(status_line) > 3 else ""
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1].strip()
    return raw


def _dedupe_preserving_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _recent_paths_from_git(
    repo_root: Path,
    *,
    commit_count: int,
    max_file_count: int,
    status_lines: Sequence[str],
) -> List[str]:
    candidates: List[str] = []

    for line in status_lines:
        path = _strip_status_path(line)
        if path and not _is_excluded_path(path):
            candidates.append(path)

    for line in _git_lines(repo_root, ["log", "--name-only", "--pretty=format:", "-n", str(commit_count)]):
        path = line.strip()
        if path and not _is_excluded_path(path):
            candidates.append(path)

    return _dedupe_preserving_order(candidates)[:max_file_count]


def _recent_files_from_filesystem(repo_root: Path, *, max_file_count: int) -> List[Dict[str, str]]:
    files: List[Dict[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_PARTS]
        for filename in filenames:
            full_path = Path(dirpath) / filename
            relative = full_path.relative_to(repo_root).as_posix()
            if _is_excluded_path(relative):
                continue
            files.append(
                {
                    "path": relative,
                    "last_write": datetime.fromtimestamp(full_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

    files.sort(key=lambda item: item["last_write"], reverse=True)
    return files[:max_file_count]


def _recent_file_records(
    repo_root: Path,
    *,
    commit_count: int,
    max_file_count: int,
    status_lines: Sequence[str],
    use_filesystem_scan: bool,
) -> List[Dict[str, str]]:
    recent_files: List[Dict[str, str]] = []
    recent_paths = _recent_paths_from_git(
        repo_root,
        commit_count=commit_count,
        max_file_count=max_file_count,
        status_lines=status_lines,
    )

    for path_str in recent_paths:
        full_path = repo_root / path_str
        last_write = "(missing)"
        if full_path.exists():
            last_write = datetime.fromtimestamp(full_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        recent_files.append({"path": path_str.replace("\\", "/"), "last_write": last_write})

    if use_filesystem_scan or not recent_files:
        return _recent_files_from_filesystem(repo_root, max_file_count=max_file_count)

    return recent_files


def _recent_commits(repo_root: Path, *, commit_count: int) -> List[Dict[str, str]]:
    commits: List[Dict[str, str]] = []
    for line in _git_lines(repo_root, ["log", "--date=short", "--pretty=format:%h|%ad|%s", "-n", str(commit_count)]):
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        commits.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
    return commits


def _gap_snapshot(repo_root: Path, recent_commits: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    gap_lines = _read_pattern_lines(repo_root / "REQUIREMENTS_BASELINE.md", r"^- GAP-")
    gaps_by_id: Dict[str, str] = {}
    for line in gap_lines:
        match = re.search(r"(GAP-\d+)", line)
        if match:
            gaps_by_id[match.group(1)] = line

    recent_subjects = " || ".join(commit["subject"] for commit in recent_commits)
    likely_closed: "OrderedDict[str, str]" = OrderedDict()

    if "upsert" in recent_subjects and "GAP-001" in gaps_by_id:
        likely_closed["GAP-001"] = "Recent commit subjects indicate upsert conflict-ID fix landed."
    if re.search(r"import run-meta lookup|connection lifecycle|import", recent_subjects) and "GAP-002" in gaps_by_id:
        likely_closed["GAP-002"] = "Recent commit subjects indicate /import connection-lifecycle bug fix landed."
    if re.search(r"compare lap query params|compare", recent_subjects) and "GAP-003" in gaps_by_id:
        likely_closed["GAP-003"] = "Recent commit subjects indicate /compare explicit lap query support landed."

    likely_closed_ids = set(likely_closed.keys())
    active_gaps: List[str] = []
    for line in gap_lines:
        match = re.search(r"(GAP-\d+)", line)
        gap_id = match.group(1) if match else ""
        if gap_id and gap_id in likely_closed_ids:
            continue
        active_gaps.append(line)

    return {
        "likely_closed_gaps": [{"id": gap_id, "reason": reason} for gap_id, reason in likely_closed.items()],
        "active_gaps": active_gaps,
    }


def build_snapshot(
    *,
    repo_root: Path,
    recent_commit_count: int,
    recent_file_count: int,
    use_filesystem_scan: bool,
) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    branch_lines = _git_lines(repo_root, ["branch", "--show-current"])
    branch = branch_lines[0].strip() if branch_lines and branch_lines[0].strip() else "(detached)"

    head_lines = _git_lines(repo_root, ["rev-parse", "--short", "HEAD"])
    head = head_lines[0].strip() if head_lines and head_lines[0].strip() else "(unknown)"

    status_lines = _git_lines(repo_root, ["status", "--short"])
    dirty = bool(status_lines)

    recent_commits = _recent_commits(repo_root, commit_count=recent_commit_count)
    recent_files = _recent_file_records(
        repo_root,
        commit_count=recent_commit_count,
        max_file_count=recent_file_count,
        status_lines=status_lines,
        use_filesystem_scan=use_filesystem_scan,
    )
    gaps = _gap_snapshot(repo_root, recent_commits)
    open_task_items = _read_pattern_lines(repo_root / "TASKS.md", r"^- \[(todo|in-progress)\]")

    return {
        "generated_at": generated_at,
        "repo": {
            "root": str(repo_root),
            "branch": branch,
            "head": head,
            "dirty": dirty,
            "status": status_lines,
        },
        "recent_commits": recent_commits,
        "recent_files": recent_files,
        "likely_closed_gaps": gaps["likely_closed_gaps"],
        "active_gaps": gaps["active_gaps"],
        "open_task_items": open_task_items,
        "planner_entrypoints": PLANNER_ENTRYPOINTS,
    }


def _render_markdown(snapshot: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Project Bootstrap Snapshot")
    lines.append("")
    lines.append(f"Generated: {snapshot['generated_at']}")
    lines.append("Purpose: Fast planner startup cache. Refresh with `python3 tools/update_bootstrap.py`.")
    lines.append("")
    lines.append("## Repo State")
    lines.append(f"- Root: `{snapshot['repo']['root']}`")
    lines.append(f"- Branch: `{snapshot['repo']['branch']}`")
    lines.append(f"- HEAD: `{snapshot['repo']['head']}`")
    lines.append(f"- Dirty: `{snapshot['repo']['dirty']}`")
    lines.append("")
    lines.append("### Working Tree Changes")
    status_lines = snapshot["repo"]["status"]
    if not status_lines:
        lines.append("- none")
    else:
        for line in status_lines:
            lines.append(f"- `{line}`")
    lines.append("")
    lines.append("## Recently Modified Files")
    if not snapshot["recent_files"]:
        lines.append("- none")
    else:
        for item in snapshot["recent_files"]:
            lines.append(f"- `{item['path']}` ({item['last_write']})")
    lines.append("")
    lines.append("## Recent Commits")
    if not snapshot["recent_commits"]:
        lines.append("- none")
    else:
        for commit in snapshot["recent_commits"]:
            lines.append(f"- `{commit['hash']}` {commit['date']} - {commit['subject']}")
    lines.append("")
    lines.append("## Requirement Gap Snapshot")
    if snapshot["likely_closed_gaps"]:
        lines.append("### Likely Closed (verify in baseline update)")
        for item in snapshot["likely_closed_gaps"]:
            lines.append(f"- `{item['id']}`: {item['reason']}")
        lines.append("")
    lines.append("### Active Gaps")
    if not snapshot["active_gaps"]:
        lines.append("- none")
    else:
        for gap in snapshot["active_gaps"]:
            lines.append(f"- {gap}")
    lines.append("")
    lines.append("## Open Task Items (`TASKS.md`)")
    if not snapshot["open_task_items"]:
        lines.append("- none")
    else:
        for item in snapshot["open_task_items"]:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("## Planner Entrypoints")
    for entry in snapshot["planner_entrypoints"]:
        lines.append(f"- `{entry}`")
    lines.append("")
    lines.append("## Incremental Update Protocol")
    lines.append("1. Refresh snapshot.")
    lines.append("2. Read this file first.")
    lines.append("3. Deep-read only files touched by new handoffs.")
    lines.append("4. Re-run refresh after integration.")
    lines.append("")
    return "\n".join(lines)


def write_snapshot(snapshot: Dict[str, Any], *, output_markdown: Path, output_json: Path) -> None:
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    output_markdown.write_text(_render_markdown(snapshot), encoding="utf-8")
    output_json.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh planner bootstrap snapshots without PowerShell.")
    parser.add_argument("--repo-root", default=".", help="Repository root to scan.")
    parser.add_argument("--recent-commit-count", type=int, default=12, help="Number of recent commits to include.")
    parser.add_argument("--recent-file-count", type=int, default=25, help="Number of recent files to include.")
    parser.add_argument("--output-markdown", default="PROJECT_BOOTSTRAP.md", help="Markdown snapshot path.")
    parser.add_argument("--output-json", default="artifacts/project_bootstrap.json", help="JSON snapshot path.")
    parser.add_argument(
        "--use-filesystem-scan",
        action="store_true",
        help="Use filesystem mtimes instead of git history for recent files.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    snapshot = build_snapshot(
        repo_root=repo_root,
        recent_commit_count=args.recent_commit_count,
        recent_file_count=args.recent_file_count,
        use_filesystem_scan=args.use_filesystem_scan,
    )
    write_snapshot(
        snapshot,
        output_markdown=(repo_root / args.output_markdown),
        output_json=(repo_root / args.output_json),
    )
    print(
        json.dumps(
            {
                "generated_at": snapshot["generated_at"],
                "output_markdown": str((repo_root / args.output_markdown).resolve()),
                "output_json": str((repo_root / args.output_json).resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
