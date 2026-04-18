"""AICP PreToolUse safety hook — Layer A (R01-R04) baseline.

Runs as a Claude Code PreToolUse hook. Reads tool invocation JSON from stdin,
emits structured response on stdout that either denies or allows the operation.

Rules implemented:
  R01 (Bash):       block 'sudo' invocations
  R02 (Write/Edit): block writes under .git/ (except top-level .gitignore/.gitattributes)
  R03 (Write/Edit): block writes to .env files (except .env.example, .env.template)
  R04 (Bash):       block 'git push --force' / 'git push -f'

Stateless — no task-state lookup. Rules apply to every Claude Code session in
this repo. See wiki/decisions/01_drafts/pretooluse-hooks-layered-approach.md
for the design rationale and the planned Layer B (stage-gate enforcement).

Hook contract (Claude Code):
  stdin: JSON with at least {"tool_name": str, "tool_input": dict}
  stdout: JSON {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny"|"allow", "permissionDecisionReason": str}}
  exit code: 0 always (the response JSON is what conveys the decision)
"""

from __future__ import annotations

import json
import re
import sys


SUDO_RE = re.compile(r"(^|\s)sudo(\s|$)")
GIT_FORCE_RE = re.compile(r"\bgit\s+push\b.*?(--force(?:-with-lease)?|--no-verify|\s-f(\s|$))")
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


def check_write_or_edit(path: str) -> dict:
    """R02 + R03 — file write checks."""
    norm = path.lstrip("./")

    if "/.git/" in path or path.startswith(".git/"):
        return _allow() if norm in ALLOWED_GIT_ROOT else _deny(
            "R02: .git/ writes blocked — modifying git internals via Write/Edit "
            "risks corrupting the repo; use git CLI in your terminal."
        )

    basename = path.rsplit("/", 1)[-1]
    if basename in ENV_ALLOWLIST:
        return _allow()
    if basename == ".env" or basename.startswith(".env."):
        return _deny(
            "R03: .env writes blocked — secrets must be edited out-of-band. "
            "Templates allowed: .env.example, .env.template, .env.sample."
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

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        decision = check_bash(command)
    elif tool_name in ("Write", "Edit", "MultiEdit"):
        path = tool_input.get("file_path") or tool_input.get("path", "")
        decision = check_write_or_edit(path)
    else:
        decision = _allow()

    print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
