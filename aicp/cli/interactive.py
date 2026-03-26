"""Interactive REPL mode for LocalAI conversations."""

from __future__ import annotations

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
) -> int:
    """Run an interactive chat session against LocalAI."""
    system = _build_system(mode, project_path)
    messages = [{"role": "system", "content": system}]  # type: List[Dict[str, str]]

    print(f"AICP interactive — {model} @ {base_url}")
    print(f"Mode: {mode.value} | Project: {project_path.name}")
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
            response = httpx.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 512,
                },
                timeout=120.0,
            )
            if response.status_code >= 400:
                print(f"[error] {response.status_code}: {response.text[:200]}", file=sys.stderr)
                messages.pop()  # remove failed user message
                continue

            try:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError):
                print(f"[error] Unexpected response: {response.text[:200]}", file=sys.stderr)
                messages.pop()
                continue
            messages.append({"role": "assistant", "content": content})
            print(f"\nai> {content}\n")

        except httpx.ConnectError:
            print("[error] Cannot connect to LocalAI. Is it running?", file=sys.stderr)
            messages.pop()
        except httpx.TimeoutException:
            print("[error] Request timed out.", file=sys.stderr)
            messages.pop()


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
