"""AICP PreToolUse safety hook — Layer A (R01-R04) + Layer B (R05 stage-gate).

Runs as a Claude Code PreToolUse hook. Reads tool invocation JSON from stdin,
emits structured response on stdout that either denies or allows the operation.

Layer A — universal safety baseline (stateless):
  R01 (Bash):       block 'sudo' invocations
  R02 (Write/Edit): block writes under .git/ (except top-level .gitignore/.gitattributes)
  R03 (Write/Edit): block writes to .env files (except .env.example, .env.template)
  R04 (Bash):       block 'git push --force' / 'git push -f' / '--no-verify'

Layer B — stage-gate enforcement (stateful):
  R05 (Write/Edit/MultiEdit): block writes to forbidden_zones for the active task's
                              current stage, per backend-ai-platform-python domain profile.
                              Active task source priority: .aicp/state.yaml → git branch
                              name parse → no enforcement.

Hook contract (Claude Code):
  stdin:  JSON {"tool_name": str, "tool_input": dict, ...}
  stdout: JSON {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny"|"allow", "permissionDecisionReason": str}}
  exit code: 0 always (the response JSON conveys the decision; exit code is for
             hook-system errors only).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # Layer B disabled if PyYAML unavailable; Layer A still works


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = REPO_ROOT / ".aicp" / "state.yaml"
DOMAIN_PROFILE = REPO_ROOT / "wiki" / "config" / "domain-profiles" / "backend-ai-platform-python.yaml"
TASKS_DIR = REPO_ROOT / "wiki" / "backlog" / "tasks"

SUDO_RE = re.compile(r"(^|\s)sudo(\s|$)")
GIT_FORCE_RE = re.compile(r"\bgit\s+push\b.*?(--force(?:-with-lease)?|--no-verify|\s-f(\s|$))")
BRANCH_TASK_RE = re.compile(r"^(?:feat|fix|refactor|docs|chore|test)/T(\d+)-")
ALLOWED_GIT_ROOT = {".gitignore", ".gitattributes", ".gitmodules"}
ENV_ALLOWLIST = {".env.example", ".env.template", ".env.sample"}


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _allow() -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def check_bash(command: str) -> dict:
    """R01 + R04 — bash tool checks."""
    if SUDO_RE.search(command):
        return _deny(
            "R01: sudo blocked — AICP's IaC must work without elevated privileges. "
            "If you genuinely need it, run the command in your own terminal."
        )
    if GIT_FORCE_RE.search(command):
        return _deny(
            "R04: git push --force / --no-verify blocked — confirm out-of-band that "
            "you want this destructive operation; force pushes can lose remote work."
        )
    return _allow()


def check_write_or_edit_safety(path: str) -> dict:
    """R02 + R03 — universal file-write safety. Returns deny if matched, allow otherwise."""
    norm = path.lstrip("./")

    if "/.git/" in path or path.startswith(".git/"):
        if norm not in ALLOWED_GIT_ROOT:
            return _deny(
                "R02: .git/ writes blocked — modifying git internals via Write/Edit "
                "risks corrupting the repo; use git CLI in your terminal."
            )

    basename = path.rsplit("/", 1)[-1]
    if basename not in ENV_ALLOWLIST:
        if basename == ".env" or basename.startswith(".env."):
            return _deny(
                "R03: .env writes blocked — secrets must be edited out-of-band. "
                "Templates allowed: .env.example, .env.template, .env.sample."
            )

    return _allow()


def _read_active_state() -> dict | None:
    """Layer B source 1: .aicp/state.yaml. Returns None if missing/unreadable."""
    if yaml is None or not STATE_FILE.exists():
        return None
    try:
        return yaml.safe_load(STATE_FILE.read_text(encoding="utf-8")) or None
    except (yaml.YAMLError, OSError):
        return None


def _infer_task_from_branch() -> str | None:
    """Layer B source 2: git branch name. Returns task ID like 'T001' or None."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        match = BRANCH_TASK_RE.match(branch)
        return f"T{match.group(1).zfill(3)}" if match else None
    except (subprocess.SubprocessError, OSError):
        return None


def _read_task_stage(task_id: str) -> str | None:
    """Read current_stage from wiki/backlog/tasks/<task_id>-*.md frontmatter."""
    if yaml is None or not TASKS_DIR.exists():
        return None
    matches = list(TASKS_DIR.glob(f"{task_id}-*.md"))
    if not matches:
        return None
    text = matches[0].read_text(encoding="utf-8")
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        return None
    try:
        meta = yaml.safe_load(fm_match.group(1)) or {}
        return meta.get("current_stage")
    except yaml.YAMLError:
        return None


def _read_forbidden_zones(stage: str) -> list[str]:
    """Read forbidden_zones for the given stage from the domain profile."""
    if yaml is None or not DOMAIN_PROFILE.exists():
        return []
    try:
        profile = yaml.safe_load(DOMAIN_PROFILE.read_text(encoding="utf-8")) or {}
        stage_def = profile.get("stage_overrides", {}).get(stage, {})
        return stage_def.get("forbidden_zones", []) or []
    except (yaml.YAMLError, OSError):
        return []


def check_stage_gate(path: str) -> dict:
    """R05 — Layer B stage-gate enforcement.

    Resolves active stage from .aicp/state.yaml first, then git branch name fallback.
    If neither resolves, returns allow (Layer B is best-effort; Layer A still applies).
    """
    state = _read_active_state()

    stage: str | None = None
    if state and isinstance(state, dict):
        stage = state.get("active_stage")
        # Cross-check: if state.yaml has stage but task file disagrees, trust the file
        task_id = state.get("active_task")
        if task_id:
            file_stage = _read_task_stage(task_id)
            if file_stage and file_stage != stage:
                stage = file_stage  # task frontmatter is the canonical source

    if stage is None:
        # Fallback: parse git branch
        task_id = _infer_task_from_branch()
        if task_id:
            stage = _read_task_stage(task_id)

    if stage is None:
        return _allow()  # No active task discoverable; Layer A still applies

    forbidden_zones = _read_forbidden_zones(stage)
    if not forbidden_zones:
        return _allow()  # No forbidden_zones for this stage (or profile not found)

    norm_path = path.lstrip("./")
    for pattern in forbidden_zones:
        # forbidden_zones use trailing-slash convention for directories
        prefix = pattern.rstrip("/")
        if norm_path.startswith(prefix + "/") or norm_path == prefix:
            return _deny(
                f"R05: stage `{stage}` forbids writes to `{pattern}` per "
                f"backend-ai-platform-python domain profile. The current task is in stage "
                f"`{stage}` (per .aicp/state.yaml or git branch). Either: (a) advance the "
                f"task to a stage that allows this path, (b) verify you're working on the "
                f"right task, or (c) update .aicp/state.yaml if the active task changed."
            )
        # Glob-style patterns (e.g., "tests/**")
        if fnmatch.fnmatchcase(norm_path, pattern) or fnmatch.fnmatchcase(norm_path, prefix + "/*"):
            return _deny(
                f"R05: stage `{stage}` forbids writes matching `{pattern}` per "
                f"backend-ai-platform-python domain profile."
            )

    return _allow()


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps(_allow()))
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Don't block on malformed input — let Claude Code surface its own error
        print(json.dumps(_allow()))
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    decision = _allow()

    if tool_name == "Bash":
        decision = check_bash(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit", "MultiEdit"):
        path = tool_input.get("file_path") or tool_input.get("path", "")

        # Layer A safety first (highest-precedence: never let through dangerous writes)
        layer_a = check_write_or_edit_safety(path)
        if layer_a["hookSpecificOutput"]["permissionDecision"] == "deny":
            decision = layer_a
        else:
            # Layer B: stage-gate
            decision = check_stage_gate(path)

    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
