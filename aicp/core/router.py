"""Smart routing — pick the best backend for a task.

Routing strategy (from CLAUDE.md):
  - Fleet ops (heartbeat, status, chat post)    → local/fast (qwen3-4b or qwen3-8b-fast)
  - Direct HTTP ops (read_context, agent_status) → local (no LLM needed)
  - Simple tasks (Q&A, summarize, format)        → local/fast (qwen3-8b-fast, no thinking)
  - Simple reviews (test pass/fail)              → local/fast (qwen3-8b-fast, no thinking)
  - Complex local tasks (analysis, reasoning)    → local (qwen3-8b, with thinking)
  - Complex implementation                       → claude (opus)
  - Architecture / security / planning           → claude (opus)

Confidence scoring:
  Each prompt is analyzed for complexity signals. A score 0.0-1.0 determines
  which backend tier to use:
    0.0 - 0.3  → local (simple, fast)
    0.3 - 0.6  → local with thinking or openrouter
    0.6 - 1.0  → claude (complex, needs deep reasoning)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# Prompt complexity analysis (E-M07, E-M08, E-M11)
# ---------------------------------------------------------------------------

@dataclass
class ComplexityScore:
    """Weighted complexity analysis of a prompt."""

    score: float                   # 0.0 (trivial) to 1.0 (very complex)
    signals: Dict[str, float] = field(default_factory=dict)  # signal → weight
    recommended_tier: str = ""     # local, openrouter, claude

    @property
    def summary(self) -> str:
        top = sorted(self.signals.items(), key=lambda x: -x[1])[:3]
        parts = [f"{k}={v:.2f}" for k, v in top]
        return f"{self.score:.2f} ({', '.join(parts)})" if parts else f"{self.score:.2f}"


def analyze_complexity(
    prompt: str,
    mode: Mode,
    config: Dict[str, Any] = None,
) -> ComplexityScore:
    """Analyze prompt complexity and return a weighted score.

    Signals and their weights:
      - mode:           ACT/EDIT = 0.4, THINK = 0.0
      - prompt_length:  0.0-0.25 scaled by character count
      - complex_kw:     0.15 per complex keyword match (max 0.45)
      - simple_kw:      -0.1 per simple keyword match (max -0.3)
      - code_signals:   0.1 for code-related content
      - multi_step:     0.15 if prompt implies multiple steps
      - question_mark:  -0.05 (questions tend to be simpler)
      - fleet_op:       -0.3 (fleet ops are always simple)

    Tier thresholds are configurable via config["router"]["complexity_thresholds"]
    (default: [0.3, 0.6]).
    """
    signals: Dict[str, float] = {}

    # Mode signal
    if mode == Mode.ACT:
        signals["mode_act"] = 0.40
    elif mode == Mode.EDIT:
        signals["mode_edit"] = 0.30

    # Prompt length (longer = more complex, up to 0.25)
    length = len(prompt)
    if length > 2000:
        signals["long_prompt"] = 0.25
    elif length > 500:
        signals["medium_prompt"] = 0.15
    elif length > 200:
        signals["short_prompt"] = 0.05

    # Complex keyword matches
    complex_hits = _COMPLEX_KEYWORDS.findall(prompt)
    if complex_hits:
        weight = min(len(complex_hits) * 0.15, 0.45)
        signals["complex_keywords"] = weight

    # Simple keyword matches (reduce score)
    simple_hits = _SIMPLE_KEYWORDS.findall(prompt)
    if simple_hits:
        weight = max(len(simple_hits) * -0.10, -0.30)
        signals["simple_keywords"] = weight

    # Code signals
    code_match = re.search(
        r"\b(code|function|class|method|import|def |return |syntax|compile|"
        r"refactor|implement|debug|traceback|unittest|pytest)\b",
        prompt, re.IGNORECASE,
    )
    if code_match:
        signals["code_content"] = 0.10

    # Multi-step indicators
    multi_step = re.search(
        r"\b(then|after that|next|step \d|first.*then|also|additionally|"
        r"and then|finally|once.*done)\b",
        prompt, re.IGNORECASE,
    )
    if multi_step:
        signals["multi_step"] = 0.15

    # Question mark (simpler)
    if prompt.strip().endswith("?"):
        signals["question"] = -0.05

    # Fleet operations (always simple)
    if _FLEET_OPS.search(prompt):
        signals["fleet_op"] = -0.30

    # Calculate final score, clamped to [0, 1]
    raw = sum(signals.values())
    score = max(0.0, min(1.0, raw))

    # Determine tier (thresholds configurable via profile/config)
    router_cfg = (config or {}).get("router", {})
    thresholds = router_cfg.get("complexity_thresholds", [0.3, 0.6])
    low_cutoff = thresholds[0] if len(thresholds) > 0 else 0.3
    high_cutoff = thresholds[1] if len(thresholds) > 1 else 0.6

    if score < low_cutoff:
        tier = "local"
    elif score < high_cutoff:
        tier = "openrouter"
    else:
        tier = "claude"

    return ComplexityScore(score=round(score, 3), signals=signals, recommended_tier=tier)


# ---------------------------------------------------------------------------
# Response quality scoring (E-M48)
# ---------------------------------------------------------------------------

def score_response_quality(response: str, prompt: str) -> float:
    """Score a response's quality heuristically (0.0-1.0).

    Checks:
      - Non-empty response
      - Reasonable length relative to prompt
      - Not a refusal / error
      - Contains substantive content (not just filler)
      - Coherent structure (sentences, paragraphs)

    This is a fast heuristic, not a semantic evaluation.
    Used to decide whether to auto-escalate to a better backend.
    """
    if not response or not response.strip():
        return 0.0

    score = 0.5  # baseline for any non-empty response
    text = response.strip()

    # Length check — too short for the prompt is suspicious
    if len(text) < 10:
        score -= 0.3
    elif len(text) < 50 and len(prompt) > 100:
        score -= 0.15

    # Refusal / error patterns
    refusal = re.search(
        r"\b(I cannot|I'm unable|I don't know|as an AI|I apologize|"
        r"error occurred|failed to|not supported|out of context)\b",
        text, re.IGNORECASE,
    )
    if refusal:
        score -= 0.2

    # Repetition check (same phrase repeated)
    words = text.lower().split()
    if len(words) > 20:
        # Check for 3-gram repetition
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        unique_ratio = len(set(trigrams)) / len(trigrams) if trigrams else 1.0
        if unique_ratio < 0.5:
            score -= 0.3  # heavy repetition

    # Structure signals (positive)
    if "\n" in text:
        score += 0.1  # has paragraph breaks
    if re.search(r"^\s*[-*•]\s", text, re.MULTILINE):
        score += 0.05  # has bullet points
    if re.search(r"```", text):
        score += 0.05  # has code blocks

    # Substantive length bonus
    if len(text) > 200:
        score += 0.1
    if len(text) > 500:
        score += 0.05

    return max(0.0, min(1.0, round(score, 3)))


# ---------------------------------------------------------------------------
# Cost tracking (E-M08)
# ---------------------------------------------------------------------------

# Approximate costs per 1M tokens (input, output) — updated 2026-04
_BACKEND_COSTS: Dict[str, Tuple[float, float]] = {
    "local": (0.0, 0.0),           # free
    "openrouter": (0.0, 0.0),      # free tier default
    "openrouter:paid": (0.5, 1.5), # generic paid estimate
    "claude": (15.0, 75.0),        # opus pricing
}


def estimate_cost(
    backend: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    model: str = "",
) -> float:
    """Estimate cost in USD for a request."""
    key = backend
    if backend == "openrouter" and ":free" not in model:
        key = "openrouter:paid"
    costs = _BACKEND_COSTS.get(key, (0.0, 0.0))
    return (prompt_tokens * costs[0] + completion_tokens * costs[1]) / 1_000_000


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
