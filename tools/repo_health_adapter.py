#!/usr/bin/env python3
"""Repo-local health adapter for aimSoloAnalysis."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
VALID_STATUSES = {"ok", "warn", "error", "unknown", "unavailable", "not_applicable"}
STATUS_PRIORITY = {
    "error": 5,
    "warn": 4,
    "unavailable": 4,
    "unknown": 3,
    "ok": 1,
    "not_applicable": 0,
}


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def summarize_text(*parts: str, limit: int = 220) -> str:
    compact = " | ".join(part.strip() for part in parts if part and part.strip())
    compact = " ".join(compact.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def derive_overall_status(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "unknown"
    return max((str(check.get("status") or "unknown") for check in checks), key=lambda item: STATUS_PRIORITY.get(item, 3))


def make_check(
    *,
    name: str,
    category: str,
    status: str,
    summary: str,
    command: list[str] | None = None,
    duration_seconds: float | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "category": category,
        "status": status if status in VALID_STATUSES else "unknown",
        "summary": summary.strip() or f"{name} produced no summary",
        "observed_at": utc_now(),
    }
    if command is not None:
        payload["command"] = command
    if duration_seconds is not None:
        payload["duration_seconds"] = round(duration_seconds, 3)
    if details:
        payload["details"] = details
    return payload


def run_command(command: list[str], *, timeout_seconds: float) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_seconds=time.monotonic() - started,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            duration_seconds=time.monotonic() - started,
            timed_out=True,
            error=f"timed out after {timeout_seconds:.1f}s",
        )
    except OSError as exc:
        return CommandResult(
            command=command,
            exit_code=None,
            stdout="",
            stderr="",
            duration_seconds=time.monotonic() - started,
            timed_out=False,
            error=str(exc),
        )


def result_details(result: CommandResult) -> dict[str, Any]:
    details: dict[str, Any] = {
        "exit_code": result.exit_code,
        "stdout_excerpt": summarize_text(result.stdout, limit=400),
        "stderr_excerpt": summarize_text(result.stderr, limit=400),
    }
    if result.error:
        details["error"] = result.error
    if result.timed_out:
        details["timed_out"] = True
    return details


def pytest_command() -> list[str] | None:
    venv_python = REPO_ROOT / ".venv-tests" / "bin" / "python"
    if venv_python.exists():
        return [str(venv_python), "-m", "pytest", "-q"]
    for candidate in (sys.executable, shutil.which("python3")):
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-m", "pytest", "--version"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return [candidate, "-m", "pytest", "-q"]
    return None


def build_check(timeout_seconds: float) -> dict[str, Any]:
    npm = shutil.which("npm")
    if not npm:
        return make_check(name="build", category="build", status="unavailable", summary="npm is not installed on this machine.")
    command = [npm, "run", "build"]
    result = run_command(command, timeout_seconds=timeout_seconds)
    if result.exit_code == 0:
        return make_check(
            name="build",
            category="build",
            status="ok",
            summary="npm run build passed.",
            command=command,
            duration_seconds=result.duration_seconds,
            details=result_details(result),
        )
    status = "error" if result.exit_code is not None else "unavailable"
    return make_check(
        name="build",
        category="build",
        status=status,
        summary="npm run build failed." if status == "error" else "Build command could not be executed.",
        command=command,
        duration_seconds=result.duration_seconds,
        details=result_details(result),
    )


def tests_check(timeout_seconds: float) -> dict[str, Any]:
    command = pytest_command()
    if command is None:
        return make_check(
            name="tests",
            category="tests",
            status="unavailable",
            summary="pytest is not available; aimSoloAnalysis tests cannot run on this machine.",
        )
    result = run_command(command, timeout_seconds=timeout_seconds)
    if result.exit_code == 0:
        return make_check(
            name="tests",
            category="tests",
            status="ok",
            summary="pytest suite passed.",
            command=command,
            duration_seconds=result.duration_seconds,
            details=result_details(result),
        )
    return make_check(
        name="tests",
        category="tests",
        status="error",
        summary="pytest suite failed.",
        command=command,
        duration_seconds=result.duration_seconds,
        details=result_details(result),
    )


def coverage_check() -> dict[str, Any]:
    coverage_artifacts = [
        REPO_ROOT / ".coverage",
        REPO_ROOT / "coverage.xml",
        REPO_ROOT / "htmlcov" / "index.html",
    ]
    present = [str(path.relative_to(REPO_ROOT)) for path in coverage_artifacts if path.exists()]
    if present:
        return make_check(
            name="coverage",
            category="coverage",
            status="ok",
            summary=f"Coverage artifacts present: {', '.join(present)}",
            details={"artifacts": present},
        )
    return make_check(
        name="coverage",
        category="coverage",
        status="unknown",
        summary="Coverage artifacts are not configured or were not generated.",
    )


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    checks = [
        build_check(timeout_seconds=args.command_timeout),
        tests_check(timeout_seconds=max(args.command_timeout, 240.0)),
        coverage_check(),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "overall_status": derive_overall_status(checks),
        "headline": summarize_text(*(f"{check['category']}={check['status']}" for check in checks)),
        "checks": checks,
        "metadata": {"repo_root": str(REPO_ROOT)},
    }


def render_snapshot(payload: dict[str, Any]) -> str:
    lines = [
        f"aimSoloAnalysis health generated at {payload.get('generated_at')}",
        f"overall_status={payload.get('overall_status')}",
    ]
    for check in payload.get("checks", []):
        lines.append(f"- {check.get('category')} {check.get('status')}: {check.get('summary')}")
    return "\n".join(lines)


def command_snapshot(args: argparse.Namespace) -> int:
    payload = build_snapshot(args)
    if args.json:
        print(json_dumps(payload))
    else:
        print(render_snapshot(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="aimSoloAnalysis repo-local health adapter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot", help="Emit a repo-health snapshot")
    snapshot_parser.add_argument("--command-timeout", type=float, default=60.0)
    snapshot_parser.add_argument("--json", action="store_true")
    snapshot_parser.set_defaults(func=command_snapshot)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
