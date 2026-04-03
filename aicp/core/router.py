"""Smart routing — pick the best backend for a task.

Routing strategy (from CLAUDE.md):
  - Fleet ops (heartbeat, status, chat post)    → local/fast (qwen3-4b or qwen3-8b-fast)
  - Direct HTTP ops (read_context, agent_status) → local (no LLM needed)
  - Simple tasks (Q&A, summarize, format)        → local/fast (qwen3-8b-fast, no thinking)
  - Simple reviews (test pass/fail)              → local/fast (qwen3-8b-fast, no thinking)
  - Complex local tasks (analysis, reasoning)    → local (qwen3-8b, with thinking)
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
    """Classify a task and return (backend_name, reason).

    4-tier routing:
      1. local   — free, fast, private (fleet ops, simple tasks)
      2. openrouter — free cloud models (medium complexity, local unavailable)
      3. claude  — expensive, powerful (complex, edit/act modes)
    """

    local = backends.get("local")
    claude = backends.get("claude")
    openrouter = backends.get("openrouter")
    local_available = local and local.is_available()
    claude_available = claude and claude.is_available()
    or_available = openrouter and openrouter.is_available()

    # If only one backend is available, use it
    if local_available and not claude_available and not or_available:
        return "local", "only backend available"
    if not local_available and not claude_available and not or_available:
        return "local", "no backends available"

    # Fleet operations → always local (zero tokens, zero cost)
    fleet_matches = _FLEET_OPS.findall(prompt)
    if fleet_matches:
        if local_available:
            return "local", "fleet operation ({})".format(fleet_matches[0])
        if or_available:
            return "openrouter", "fleet op, local unavailable"
        return "local", "fleet operation (local down)"

    # Act mode → Claude (hard enforcement via CLI flags)
    if mode == Mode.ACT:
        return "claude", "act mode needs hard enforcement"

    # Edit mode → Claude (hard enforcement via CLI flags)
    if mode == Mode.EDIT:
        return "claude", "edit mode needs hard enforcement"

    # Complex keywords → Claude (or OpenRouter as fallback)
    complex_matches = _COMPLEX_KEYWORDS.findall(prompt)
    if complex_matches:
        if claude_available:
            return "claude", "complex task ({})".format(complex_matches[0])
        if or_available:
            return "openrouter", "complex task, claude unavailable"
        return "local", "complex task, no cloud backends"

    # Long prompts → Claude or OpenRouter
    if len(prompt) > 500:
        if claude_available:
            return "claude", "long prompt ({} chars)".format(len(prompt))
        if or_available:
            return "openrouter", "long prompt, claude unavailable"

    # Simple keywords → Local (or cheapest available fallback)
    simple_matches = _SIMPLE_KEYWORDS.findall(prompt)
    if simple_matches:
        if local_available:
            return "local", "simple task"
        if or_available:
            return "openrouter", "simple task, local unavailable"
        if claude_available:
            return "claude", "simple task, local unavailable"

    # Default: prefer local → openrouter → claude
    if local_available:
        return "local", "default for think mode" if mode == Mode.THINK else "default"
    if or_available:
        return "openrouter", "local unavailable"
    if claude_available:
        return "claude", "local unavailable"
    return "local", "no backends available"


# Operations that can be handled without LLM (zero tokens)
_DIRECT_OPS = re.compile(
    r"\b(fleet_read_context|fleet_agent_status|fleet_node_status)\b",
    re.IGNORECASE,
)

# Operations that get a structured response (minimal tokens)
_HEARTBEAT_OPS = re.compile(
    r"\b(heartbeat|HEARTBEAT_OK|health.?check|ping)\b",
    re.IGNORECASE,
)


def categorize_operation(prompt: str) -> str:
    """Categorize an operation for routing decisions.

    Returns one of:
      - 'direct'    — handled via direct HTTP, no LLM needed
      - 'heartbeat' — structured response, minimal LLM or template
      - 'simple'    — simple task, LocalAI can handle
      - 'complex'   — needs Claude-level reasoning
      - 'default'   — no strong signal, use default backend
    """
    if _DIRECT_OPS.search(prompt):
        return "direct"
    if _HEARTBEAT_OPS.search(prompt):
        return "heartbeat"
    if _COMPLEX_KEYWORDS.search(prompt):
        return "complex"
    if _SIMPLE_KEYWORDS.search(prompt):
        return "simple"
    return "default"


def intercept_operation(prompt: str, config: Dict[str, Any] = None) -> Optional[str]:
    """Try to handle an operation without invoking an LLM.

    Returns a response string if the operation was handled, None otherwise.
    These are zero-token operations that don't need inference.
    """
    import socket

    category = categorize_operation(prompt)

    if category == "heartbeat":
        hostname = socket.gethostname()
        return f"HEARTBEAT_OK | node={hostname} | status=online"

    if category == "direct":
        # Direct HTTP operations — caller should route to MCP/HTTP handler
        # Return a marker so the caller knows to use direct HTTP
        return None  # Not handled here; controller should route to agent client

    return None


def classify_test_output(output: str) -> Optional[str]:
    """Classify test output as pass/fail without LLM inference.

    Returns 'pass', 'fail', or None if the output doesn't look like test results.
    This is a zero-token alternative for simple review tasks.
    """
    # Common test framework patterns
    pass_patterns = re.compile(
        r"\b(\d+ passed|PASSED|PASS|tests? passed|all tests|"
        r"OK \(\d+ test|✓|✅|BUILD SUCCESS|exit code 0)\b",
        re.IGNORECASE,
    )
    fail_patterns = re.compile(
        r"\b(\d+ failed|FAILED|FAIL|tests? failed|errors? found|"
        r"✗|❌|BUILD FAILURE|exit code [1-9]|AssertionError|"
        r"Error:|ERRORS?:)\b",
        re.IGNORECASE,
    )

    has_pass = bool(pass_patterns.search(output))
    has_fail = bool(fail_patterns.search(output))

    if has_fail:
        return "fail"
    if has_pass:
        return "pass"
    return None


def recommend_model(prompt: str, config: Dict[str, Any] = None) -> Optional[str]:
    """Suggest the best LocalAI model for a prompt.

    Returns a model name (e.g. 'qwen3-4b', 'qwen3-8b', 'qwen3-8b-fast') or
    None to use the default (main model with thinking enabled).

    Routing logic:
      - Fleet/heartbeat ops  → fleet_model (lightweight, e.g. qwen3-4b)
      - Simple tasks          → fast_model (no thinking overhead)
      - Code tasks            → code_model
      - Complex/default       → None (use main model with thinking)
    """
    config = config or {}
    local_cfg = config.get("backends", {}).get("local", {})

    # Fleet/heartbeat ops → lightweight model (zero-overhead)
    if _FLEET_OPS.search(prompt):
        return local_cfg.get("fleet_model", "qwen3-4b")

    # Code tasks → code model (check before simple — code needs reasoning)
    code_keywords = re.search(
        r"\b(code|function|class|method|import|def |return |variable|syntax|compile)\b",
        prompt, re.IGNORECASE,
    )
    if code_keywords:
        return local_cfg.get("code_model", "qwen3-8b")

    # Simple tasks → fast model (no thinking, fewer tokens)
    if _SIMPLE_KEYWORDS.search(prompt) and not _COMPLEX_KEYWORDS.search(prompt):
        return local_cfg.get("fast_model", "qwen3-8b-fast")

    # Default: main model (with thinking enabled for complex reasoning)
    return None
