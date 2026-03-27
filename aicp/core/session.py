"""Session continuity — persist LocalAI conversation history across single-shot calls.

Usage::

    # First call — starts a new session named "myfeature"
    aicp --session myfeature "What files are in the auth module?"

    # Second call — continues the same conversation with full history
    aicp --session myfeature "Show me the login function in detail"

    # List sessions
    aicp --session-list

Sessions are stored as JSON files in ``~/.aicp/sessions/<name>.json``.
Each file holds the full ``messages[]`` array (system + user + assistant turns).

Only LocalAI uses sessions — Claude Code manages its own session continuity via
``--continue-session`` and ``--resume``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sessions_dir() -> Path:
    base = Path(os.environ.get("AICP_HOME", Path.home() / ".aicp"))
    d = base / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_session(name: str) -> List[Dict[str, str]]:
    """Load message history for a named session.

    Returns an empty list if the session doesn't exist yet.
    The caller is responsible for prepending the system message if needed.
    """
    path = _sessions_dir() / f"{_safe_name(name)}.json"
    if not path.exists():
        return []

    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("messages", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_session(name: str, messages: List[Dict[str, str]]) -> None:
    """Persist message history for a named session."""
    path = _sessions_dir() / f"{_safe_name(name)}.json"
    data = {
        "name": name,
        "updated": datetime.utcnow().isoformat() + "Z",
        "message_count": len(messages),
        "messages": messages,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def delete_session(name: str) -> bool:
    """Delete a named session. Returns True if it existed."""
    path = _sessions_dir() / f"{_safe_name(name)}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions() -> List[Dict[str, Any]]:
    """List all sessions, newest first."""
    sessions = []
    for p in sorted(_sessions_dir().glob("*.json"), reverse=True):
        try:
            with open(p) as f:
                data = json.load(f)
            sessions.append({
                "name": data.get("name", p.stem),
                "updated": data.get("updated", ""),
                "turns": data.get("message_count", 0) // 2,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def _safe_name(name: str) -> str:
    """Sanitize session name for use as a filename."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:64]
