"""Smart routing — pick the best backend for a task.

Routing strategy (from CLAUDE.md):
  - Fleet ops (heartbeat, status, chat post)    → local (hermes-3b)
  - Direct HTTP ops (read_context, agent_status) → local (no LLM needed)
  - Simple tasks (Q&A, summarize, format)        → local (hermes-3b)
  - Simple reviews (test pass/fail)              → local (hermes-3b)
  - Complex implementation                       → claude (opus)
  - Architecture / security / planning           → claude (opus)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from aicp.backends.base import Backend
from aicp.core.modes import Mode


# Fleet / infrastructure operations — always LocalAI, zero Claude tokens
_FLEET_OPS = re.compile(
    r"\b(heartbeat|HEARTBEAT_OK|fleet_read_context|fleet_agent_status|"
    r"fleet_chat|agent.?status|node.?status|health.?check|ping)\b",
    re.IGNORECASE,
)

# Keywords that suggest complex tasks better suited for Claude Code
_COMPLEX_KEYWORDS = re.compile(
    r"\b(refactor|rewrite|implement|architect|design|debug|fix|migrate|"
    r"optimize|review|test|deploy|security|audit|explain\s+why|"
    r"multi.?file|across\s+files|entire\s+project|codebase|"
    r"sprint|planning|roadmap|strategy|vulnerability|threat.?model)\b",
    re.IGNORECASE,
)

# Keywords that suggest simple tasks LocalAI can handle
_SIMPLE_KEYWORDS = re.compile(
    r"\b(what\s+is|define|list|name|describe|summarize|"
    r"how\s+many|translate|convert|format|hello|hi|hey|"
    r"status|check|verify|validate|confirm|pass.?fail|"
    r"accept|reject|approve|deny)\b",
    re.IGNORECASE,
)


def classify_task(
    prompt: str,
    mode: Mode,
    backends: Dict[str, Backend],
    config: Dict[str, Any] = None,
) -> str:
    """Classify a task and return the recommended backend name.

    Returns 'local' or 'claude' with a reason string via classify_task_with_reason().
    """
    backend, _ = classify_task_with_reason(prompt, mode, backends, config)
    return backend


def classify_task_with_reason(
    prompt: str,
    mode: Mode,
    backends: Dict[str, Backend],
    config: Dict[str, Any] = None,
) -> Tuple[str, str]:
    """Classify a task and return (backend_name, reason)."""

    local = backends.get("local")
    claude = backends.get("claude")
    local_available = local and local.is_available()
    claude_available = claude and claude.is_available()

    # If only one backend is available, use it
    if local_available and not claude_available:
        return "local", "claude unavailable"
    if claude_available and not local_available:
        return "claude", "local unavailable"
    if not local_available and not claude_available:
        return "local", "no backends available"

    # Fleet operations → always local (zero Claude tokens)
    fleet_matches = _FLEET_OPS.findall(prompt)
    if fleet_matches:
        return "local", "fleet operation ({})".format(fleet_matches[0])

    # Act mode → Claude (hard enforcement via CLI flags)
    if mode == Mode.ACT:
        return "claude", "act mode needs hard enforcement"

    # Edit mode → Claude (hard enforcement via CLI flags)
    if mode == Mode.EDIT:
        return "claude", "edit mode needs hard enforcement"

    # Long prompts → Claude (better at complex reasoning)
    if len(prompt) > 500:
        return "claude", "long prompt ({} chars)".format(len(prompt))

    # Complex keywords → Claude
    complex_matches = _COMPLEX_KEYWORDS.findall(prompt)
    if complex_matches:
        return "claude", "complex task ({})".format(complex_matches[0])

    # Simple keywords → Local
    simple_matches = _SIMPLE_KEYWORDS.findall(prompt)
    if simple_matches:
        return "local", "simple task"

    # Default: local for think mode (fast + private)
    if mode == Mode.THINK:
        return "local", "default for think mode"

    return "local", "default"


def recommend_model(prompt: str, config: Dict[str, Any] = None) -> Optional[str]:
    """Suggest the best LocalAI model for a prompt.

    Returns a model name (e.g. 'hermes-3b', 'hermes', 'codellama') or None
    to use the default.
    """
    config = config or {}
    local_cfg = config.get("backends", {}).get("local", {})

    # Fleet/heartbeat ops → lightweight 3B model
    if _FLEET_OPS.search(prompt):
        return local_cfg.get("fleet_model", "hermes-3b")

    # Code tasks → code model
    code_keywords = re.search(
        r"\b(code|function|class|method|import|def |return |variable|syntax|compile)\b",
        prompt, re.IGNORECASE,
    )
    if code_keywords:
        return local_cfg.get("code_model", "codellama")

    # Default: main model
    return None
