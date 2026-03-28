"""Built-in tools for function calling with LocalAI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional


# ── Tool definitions (OpenAI tools format) ───────────────────────────────────

TOOL_FILE_READ = {
    "type": "function",
    "function": {
        "name": "file_read",
        "description": "Read the contents of a file. Returns the file text.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to read",
                },
            },
            "required": ["path"],
        },
    },
}

TOOL_FILE_LIST = {
    "type": "function",
    "function": {
        "name": "file_list",
        "description": "List files and directories at a given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter results (e.g. '*.py')",
                },
            },
            "required": [],
        },
    },
}

TOOL_GREP = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search for a pattern in files. Returns matching lines with file paths and line numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (default: current directory)",
                },
                "glob": {
                    "type": "string",
                    "description": "File glob filter (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
    },
}

TOOL_SHELL = {
    "type": "function",
    "function": {
        "name": "shell",
        "description": "Execute a shell command and return its output. Use for build, test, and system commands.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
            },
            "required": ["command"],
        },
    },
}

# All available tools
ALL_TOOLS = [TOOL_FILE_READ, TOOL_FILE_LIST, TOOL_GREP, TOOL_SHELL]

# Tools safe for think mode (read-only)
THINK_TOOLS = [TOOL_FILE_READ, TOOL_FILE_LIST, TOOL_GREP]


# ── Tool implementations ────────────────────────────────────────────────────

def _execute_file_read(args: dict, project_path: Path) -> str:
    """Read a file and return its contents."""
    path = Path(args["path"])
    if not path.is_absolute():
        path = project_path / path
    if not path.exists():
        return f"Error: file not found: {path}"
    if not path.is_file():
        return f"Error: not a file: {path}"
    try:
        text = path.read_text(errors="replace")
        if len(text) > 10000:
            return text[:10000] + f"\n... (truncated, {len(text)} chars total)"
        return text
    except Exception as e:
        return f"Error reading {path}: {e}"


def _execute_file_list(args: dict, project_path: Path) -> str:
    """List directory contents."""
    path = Path(args.get("path", "."))
    if not path.is_absolute():
        path = project_path / path
    if not path.exists():
        return f"Error: path not found: {path}"
    pattern = args.get("pattern", "*")
    try:
        entries = sorted(path.glob(pattern))[:100]
        lines = []
        for e in entries:
            prefix = "d " if e.is_dir() else "f "
            lines.append(f"{prefix}{e.relative_to(path)}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"Error listing {path}: {e}"


def _execute_grep(args: dict, project_path: Path) -> str:
    """Search for a pattern in files using grep."""
    pattern = args["pattern"]
    path = args.get("path", ".")
    glob_filter = args.get("glob", "")
    cmd = ["grep", "-rn", "--include", glob_filter, pattern, path] if glob_filter else [
        "grep", "-rn", pattern, path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, cwd=str(project_path),
        )
        output = result.stdout.strip()
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        return output if output else "(no matches)"
    except subprocess.TimeoutExpired:
        return "Error: search timed out (10s)"
    except Exception as e:
        return f"Error: {e}"


def _execute_shell(args: dict, project_path: Path) -> str:
    """Execute a shell command."""
    command = args["command"]
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(project_path),
        )
        output = result.stdout + result.stderr
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        exit_info = f"(exit code: {result.returncode})" if result.returncode != 0 else ""
        return f"{output.strip()}\n{exit_info}".strip()
    except subprocess.TimeoutExpired:
        return "Error: command timed out (30s)"
    except Exception as e:
        return f"Error: {e}"


# Tool name → implementation mapping
_TOOL_REGISTRY: dict[str, Callable] = {
    "file_read": _execute_file_read,
    "file_list": _execute_file_list,
    "grep": _execute_grep,
    "shell": _execute_shell,
}


def execute_tool(name: str, arguments: str, project_path: Path) -> str:
    """Execute a tool by name with JSON-encoded arguments.

    Returns the tool output as a string.
    """
    handler = _TOOL_REGISTRY.get(name)
    if not handler:
        return f"Error: unknown tool '{name}'"
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        return f"Error: invalid arguments JSON: {e}"
    return handler(args, project_path)


def get_tools_for_mode(mode_name: str) -> list[dict]:
    """Return the appropriate tool set for the given permission mode."""
    if mode_name == "act":
        return ALL_TOOLS
    if mode_name == "edit":
        return THINK_TOOLS  # no shell in edit mode
    return THINK_TOOLS  # think mode: read-only tools
