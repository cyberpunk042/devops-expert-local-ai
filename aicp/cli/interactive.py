"""Interactive REPL mode for LocalAI conversations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import httpx

from aicp.core.context import build_project_context
from aicp.core.modes import Mode


def run_interactive(
    base_url: str,
    model: str,
    mode: Mode,
    project_path: Path,
    max_tokens: int = 2048,
    stream: bool = True,
) -> int:
    """Run an interactive chat session against LocalAI.

    Args:
        base_url:     LocalAI API base URL.
        model:        Model alias to use.
        mode:         Permission mode (think/edit/act).
        project_path: Project directory for context injection.
        max_tokens:   Max completion tokens per turn (from config).
        stream:       If True, stream responses token-by-token (default: True).
    """
    system = _build_system(mode, project_path)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]

    print(f"AICP interactive — {model} @ {base_url}")
    print(f"Mode: {mode.value} | Project: {project_path.name} | Stream: {stream}")
    print("Type 'exit' or Ctrl+D to quit.\n")

    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "/quit", "/exit"):
            print("Bye.")
            return 0

        messages.append({"role": "user", "content": prompt})

        try:
            if stream:
                content = _stream_turn(base_url, model, messages, max_tokens)
            else:
                content = _blocking_turn(base_url, model, messages, max_tokens)

            if content is None:
                messages.pop()
                continue

            messages.append({"role": "assistant", "content": content})

        except httpx.ConnectError:
            print("[error] Cannot connect to LocalAI. Is it running?", file=sys.stderr)
            messages.pop()
        except httpx.TimeoutException:
            print("[error] Request timed out.", file=sys.stderr)
            messages.pop()

    return 0


def _stream_turn(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
) -> str | None:
    """Send a streaming chat request; print tokens as they arrive.

    Returns the assembled response string, or None on error.
    """
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
    }

    collected = []
    print("\nai> ", end="", flush=True)
    try:
        with httpx.stream(
            "POST",
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=120.0,
        ) as resp:
            if resp.status_code >= 400:
                print(f"\n[error] {resp.status_code}: {resp.read().decode()[:200]}", file=sys.stderr)
                return None

            for line in resp.iter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        chunk = data["choices"][0].get("delta", {}).get("content", "")
                        if chunk:
                            print(chunk, end="", flush=True)
                            collected.append(chunk)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        print("\n")
        return "".join(collected)

    except Exception as e:
        print(f"\n[error] Stream error: {e}", file=sys.stderr)
        return None


def _blocking_turn(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
) -> str | None:
    """Send a blocking (non-streaming) chat request.

    Returns the response string, or None on error.
    """
    response = httpx.post(
        f"{base_url}/v1/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=120.0,
    )
    if response.status_code >= 400:
        print(f"[error] {response.status_code}: {response.text[:200]}", file=sys.stderr)
        return None

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"\nai> {content}\n")
        return content
    except (KeyError, IndexError, TypeError, ValueError):
        print(f"[error] Unexpected response: {response.text[:200]}", file=sys.stderr)
        return None


def _build_system(mode: Mode, project_path: Path) -> str:
    parts = []
    if mode == Mode.THINK:
        parts.append("You are a helpful assistant. Read-only mode: do not suggest edits or commands.")
    elif mode == Mode.EDIT:
        parts.append("You are a helpful assistant. Edit mode: you may suggest file edits but not commands.")
    else:
        parts.append("You are a helpful assistant. Full mode: you may suggest edits and commands.")

    parts.append(f"Project: {project_path.name}.")

    context = build_project_context(project_path, max_chars=800)
    if context:
        parts.append(context)

    return "\n\n".join(parts)
