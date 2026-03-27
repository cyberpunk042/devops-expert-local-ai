"""Post-execution response guardrails.

Two scanners are provided:

1. ``scan_think_mode`` — warns when a local model sneaks shell commands or
   file-write instructions into a THINK-mode response (advisory enforcement).

2. ``scan_response_secrets`` — warns when any response (any mode, any backend)
   appears to echo back secret material: API keys, tokens, private key blocks.
   Useful when a prompt asks the model to summarise a config file and the model
   helpfully reproduces credentials verbatim.

Neither scanner blocks the response — they surface warnings so the user can
decide whether to trust and act on the output.
"""

from __future__ import annotations

import re
from typing import List

from aicp.core.modes import Mode


# Patterns that suggest shell command execution in a THINK-mode response.
# Intentionally conservative — prefer false negatives over false positives.
_SHELL_PATTERNS: List[re.Pattern] = [
    # Shell prompt lines: $ cmd, # cmd
    re.compile(r"^\s*[$#]\s+\S", re.MULTILINE),
    # Backtick command substitution: `cmd`
    re.compile(r"`[^`]{3,}`"),
    # Explicit sudo / rm -rf
    re.compile(r"\bsudo\s+\w", re.IGNORECASE),
    re.compile(r"\brm\s+-[a-z]*f[a-z]*\s", re.IGNORECASE),
    # Curl/wget piped to bash (common RCE pattern)
    re.compile(r"\b(curl|wget)\b.+\|\s*(ba)?sh\b", re.IGNORECASE | re.DOTALL),
]

# Patterns that suggest file writes in a THINK-mode response.
_WRITE_PATTERNS: List[re.Pattern] = [
    # Shell redirects: > /path or >> /path (with at least 4-char path)
    re.compile(r">\s*/\w{2,}"),
    # tee command writing to file
    re.compile(r"\btee\s+\S+"),
    # Python file writes: open(... 'w'), .write_text, Path(...).write
    re.compile(r"""open\s*\([^)]+['"]\s*w[ab]?['"]\s*\)"""),
    re.compile(r"\.(write_text|write_bytes)\s*\("),
]


# ── Secret-leakage patterns ─────────────────────────────────────────────────
# Conservative: only match high-confidence patterns to keep false positives low.
# The goal is to catch cases where a model reproduces secrets from context, not
# to be a general-purpose secret scanner.

_SECRET_PATTERNS: List[tuple[str, re.Pattern]] = [
    # AWS access key IDs: AKIA / ASIA / AROA / AIDA / ANPA / ANVA / AIPA prefix + 16 uppercase alphanum
    ("AWS access key", re.compile(r"\b(AKIA|ASIA|AROA|AIDA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b")),
    # Generic high-entropy API key: key=<32+ hex/base64 chars>
    ("API key", re.compile(r"""(?i)\b(api[_\-]?key|apikey|access[_\-]?key)\s*[=:]\s*['"]?[A-Za-z0-9+/\-_]{32,}['"]?""")),
    # Bearer tokens in Authorization headers
    ("Bearer token", re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9\-_\.]{20,}")),
    # JWT: three base64url segments separated by dots
    ("JWT", re.compile(r"\bey[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\b")),
    # PEM private key block
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    # GitHub PAT: ghp_ / gho_ / ghs_ / ghu_ prefix + 36 chars
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    # Generic password= / passwd= / secret= with non-trivial value
    ("password/secret", re.compile(r"""(?i)\b(password|passwd|secret|token)\s*[=:]\s*['"]?[^\s'"]{12,}['"]?""")),
]


def scan_response_secrets(response: str) -> List[str]:
    """Scan a response for patterns that look like leaked secrets.

    Returns a list of warning strings describing what was found.
    Called for all modes and backends — secret leakage can happen anywhere.
    """
    warnings = []
    seen: set = set()

    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(response) and label not in seen:
            seen.add(label)
            warnings.append(
                f"Response may contain a {label}. "
                "Review before sharing or logging. "
                "Check that your prompt did not expose secrets from context files."
            )

    return warnings


# ── THINK-mode command/write patterns ────────────────────────────────────────

def scan_think_mode(response: str, mode: Mode) -> List[str]:
    """Scan a response for content that violates THINK-mode constraints.

    Returns a list of warning strings. Empty list means no violations detected.
    Only runs for Mode.THINK — returns [] for Edit/Act where writes are expected.
    """
    if mode != Mode.THINK:
        return []

    warnings = []

    for pattern in _SHELL_PATTERNS:
        if pattern.search(response):
            warnings.append(
                "THINK mode: response may contain shell commands. "
                "Review before acting. Use --mode act if you intended to run commands."
            )
            break  # One shell warning is enough

    for pattern in _WRITE_PATTERNS:
        if pattern.search(response):
            warnings.append(
                "THINK mode: response may contain file-write instructions. "
                "Review before acting. Use --mode edit if you intended to make edits."
            )
            break  # One write warning is enough

    return warnings
