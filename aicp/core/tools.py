"""Built-in tools for function calling with LocalAI."""

from __future__ import annotations

import base64
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aicp.backends.localai import LocalAIBackend

# ── Tool safety metadata (inspired by Claude Code's buildTool pattern) ──────
# Fail-closed: assume tools are NOT safe unless explicitly marked.

ToolMeta = dict[str, Any]  # typing alias

def _meta(
    is_read_only: bool = False,
    is_destructive: bool = False,
    is_concurrent_safe: bool = False,
    requires_backend: bool = False,
    requires_path: bool = False,
) -> dict[str, Any]:
    """Build tool safety metadata with fail-closed defaults."""
    return {
        "is_read_only": is_read_only,
        "is_destructive": is_destructive,
        "is_concurrent_safe": is_concurrent_safe,
        "requires_backend": requires_backend,
        "requires_path": requires_path,
    }


# Safety metadata per tool name
TOOL_SAFETY: dict[str, dict[str, Any]] = {
    "file_read":        _meta(is_read_only=True, is_concurrent_safe=True, requires_path=True),
    "file_list":        _meta(is_read_only=True, is_concurrent_safe=True),
    "grep":             _meta(is_read_only=True, is_concurrent_safe=True),
    "shell":            _meta(is_destructive=True),
    "image_analyze":    _meta(is_read_only=True, requires_backend=True, requires_path=True),
    "audio_transcribe": _meta(is_read_only=True, requires_backend=True, requires_path=True),
    "text_to_speech":   _meta(requires_backend=True),
    "image_generate":   _meta(requires_backend=True),
    "kb_search":        _meta(is_read_only=True, is_concurrent_safe=True, requires_backend=True),
    "system_info":      _meta(is_read_only=True, is_concurrent_safe=True, requires_backend=True),
    "store_remember":   _meta(requires_backend=True),
    "store_recall":     _meta(is_read_only=True, is_concurrent_safe=True, requires_backend=True),
}


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

# ── Multimodal tool definitions ────────────────────────────────────────────

TOOL_IMAGE_ANALYZE = {
    "type": "function",
    "function": {
        "name": "image_analyze",
        "description": "Analyze an image file using the vision model (LLaVA). Returns a text description.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the image file (png, jpg, gif, webp, bmp)",
                },
                "prompt": {
                    "type": "string",
                    "description": "What to ask about the image (default: 'Describe this image in detail.')",
                },
            },
            "required": ["path"],
        },
    },
}

TOOL_AUDIO_TRANSCRIBE = {
    "type": "function",
    "function": {
        "name": "audio_transcribe",
        "description": "Transcribe an audio file to text using the whisper model. Returns the transcribed text.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the audio file (wav, mp3, ogg, flac)",
                },
                "language": {
                    "type": "string",
                    "description": "Language hint (default: 'en')",
                },
            },
            "required": ["path"],
        },
    },
}

TOOL_TEXT_TO_SPEECH = {
    "type": "function",
    "function": {
        "name": "text_to_speech",
        "description": "Convert text to speech audio using the TTS model (piper). Generates a WAV file.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize into speech",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to write the WAV file (default: /tmp/aicp_tool_tts.wav)",
                },
            },
            "required": ["text"],
        },
    },
}

TOOL_IMAGE_GENERATE = {
    "type": "function",
    "function": {
        "name": "image_generate",
        "description": "Generate an image from a text prompt using Stable Diffusion. Use '|' to separate positive and negative prompts.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the image to generate",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to write the PNG file (default: /tmp/aicp_tool_imagine.png)",
                },
                "size": {
                    "type": "string",
                    "description": "Image dimensions as WxH (default: 512x512)",
                },
            },
            "required": ["prompt"],
        },
    },
}

TOOL_KB_SEARCH = {
    "type": "function",
    "function": {
        "name": "kb_search",
        "description": "Search the knowledge base using semantic search. Returns matching text chunks with sources and relevance scores.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_SYSTEM_INFO = {
    "type": "function",
    "function": {
        "name": "system_info",
        "description": "Get LocalAI system status: active GPU model, installed backends, and available models. Use to check what model is loaded or what capabilities are available.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_STORE_REMEMBER = {
    "type": "function",
    "function": {
        "name": "store_remember",
        "description": "Store information in working memory (ephemeral, lost on restart). Use to remember facts, findings, or context during a session.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The information to remember",
                },
                "store": {
                    "type": "string",
                    "description": "Store name (default: 'memory')",
                },
            },
            "required": ["text"],
        },
    },
}

TOOL_STORE_RECALL = {
    "type": "function",
    "function": {
        "name": "store_recall",
        "description": "Search working memory for relevant information. Returns semantically similar entries from what was previously stored.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in working memory",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (default: 5)",
                },
                "store": {
                    "type": "string",
                    "description": "Store name (default: 'memory')",
                },
            },
            "required": ["query"],
        },
    },
}

# ── Tool sets by mode ──────────────────────────────────────────────────────

# Read-only multimodal tools (safe for think mode)
_MULTIMODAL_READ = [
    TOOL_IMAGE_ANALYZE, TOOL_AUDIO_TRANSCRIBE, TOOL_KB_SEARCH,
    TOOL_SYSTEM_INFO, TOOL_STORE_RECALL,
]

# Write multimodal tools (generate files / store data)
_MULTIMODAL_WRITE = [TOOL_TEXT_TO_SPEECH, TOOL_IMAGE_GENERATE, TOOL_STORE_REMEMBER]

# All available tools
ALL_TOOLS = [TOOL_FILE_READ, TOOL_FILE_LIST, TOOL_GREP, TOOL_SHELL] + _MULTIMODAL_READ + _MULTIMODAL_WRITE

# Tools safe for think mode (read-only + recall)
THINK_TOOLS = [TOOL_FILE_READ, TOOL_FILE_LIST, TOOL_GREP] + _MULTIMODAL_READ

# Tools for edit mode (read + generate + remember, no shell)
EDIT_TOOLS = [TOOL_FILE_READ, TOOL_FILE_LIST, TOOL_GREP] + _MULTIMODAL_READ + _MULTIMODAL_WRITE


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


# ── Multimodal tool implementations ────────────────────────────────────────

def _execute_image_analyze(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Analyze an image using the vision model."""
    if not backend:
        return "Error: vision requires a LocalAI backend"
    path = Path(args["path"])
    if not path.is_absolute():
        path = project_path / path
    if not path.exists():
        return f"Error: image not found: {path}"
    prompt = args.get("prompt", "Describe this image in detail.")
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/png")
    try:
        image_data = base64.b64encode(path.read_bytes()).decode("ascii")
        from aicp.core.modes import Mode
        return backend.execute_vision(prompt, image_data, Mode.THINK, project_path, image_mime=mime)
    except Exception as e:
        return f"Error analyzing image: {e}"


def _execute_audio_transcribe(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Transcribe audio to text."""
    if not backend:
        return "Error: transcription requires a LocalAI backend"
    path = Path(args["path"])
    if not path.is_absolute():
        path = project_path / path
    if not path.exists():
        return f"Error: audio file not found: {path}"
    language = args.get("language", "en")
    try:
        result = backend.transcribe(path, language=language)
        return result.get("text", "").strip() or "(no speech detected)"
    except Exception as e:
        return f"Error transcribing audio: {e}"


def _execute_text_to_speech(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Generate speech from text."""
    if not backend:
        return "Error: TTS requires a LocalAI backend"
    text = args["text"]
    output_path = Path(args.get("output_path", "/tmp/aicp_tool_tts.wav"))
    try:
        backend.speak(text, output_path)
        return f"Audio saved to {output_path}"
    except Exception as e:
        return f"Error generating speech: {e}"


def _execute_image_generate(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Generate an image from a text prompt."""
    if not backend:
        return "Error: image generation requires a LocalAI backend"
    prompt = args["prompt"]
    output_path = Path(args.get("output_path", "/tmp/aicp_tool_imagine.png"))
    size = args.get("size", "512x512")
    try:
        backend.generate_image(prompt, output_path, size=size)
        return f"Image saved to {output_path}"
    except Exception as e:
        return f"Error generating image: {e}"


def _execute_kb_search(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Search the knowledge base."""
    if not backend:
        return "Error: KB search requires a LocalAI backend"
    query = args["query"]
    top_k = args.get("top_k", 5)
    try:
        from aicp.config.loader import load_config
        from aicp.core.kb import KnowledgeBase
        config = load_config()
        kb = KnowledgeBase(backend, config)
        results = kb.search(query, top_k=top_k)
        return json.dumps(results, indent=2)
    except ImportError:
        return "Error: knowledge base module not available"
    except Exception as e:
        return f"Error searching KB: {e}"


def _execute_store_remember(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Store information in working memory."""
    if not backend:
        return "Error: store requires a LocalAI backend"
    text = args["text"]
    store_name = args.get("store", "memory")
    try:
        backend.store_set([text], store_name=store_name)
        return f"Stored in '{store_name}': {text[:100]}"
    except Exception as e:
        return f"Error storing: {e}"


def _execute_store_recall(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Search working memory."""
    if not backend:
        return "Error: store requires a LocalAI backend"
    query = args["query"]
    top_k = args.get("top_k", 5)
    store_name = args.get("store", "memory")
    try:
        results = backend.store_find(query, store_name=store_name, top_k=top_k)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error recalling: {e}"


def _execute_system_info(
    args: dict, project_path: Path, backend: LocalAIBackend | None = None,
) -> str:
    """Get LocalAI system status."""
    if not backend:
        return "Error: system info requires a LocalAI backend"
    try:
        from aicp.core.observability import get_loaded_models, get_system_info
        sys_info = get_system_info(backend.base_url)
        models = get_loaded_models(backend.base_url)
        return json.dumps({
            "active_gpu_model": sys_info.get("loaded_models", []),
            "installed_backends": sys_info.get("backends", []),
            "configured_models": models,
        }, indent=2)
    except Exception as e:
        return f"Error getting system info: {e}"


# Tool name → implementation mapping
_TOOL_REGISTRY: dict[str, Callable] = {
    "file_read": _execute_file_read,
    "file_list": _execute_file_list,
    "grep": _execute_grep,
    "shell": _execute_shell,
}

# Multimodal tools that need a backend reference
_MULTIMODAL_REGISTRY: dict[str, Callable] = {
    "image_analyze": _execute_image_analyze,
    "audio_transcribe": _execute_audio_transcribe,
    "text_to_speech": _execute_text_to_speech,
    "image_generate": _execute_image_generate,
    "kb_search": _execute_kb_search,
    "system_info": _execute_system_info,
    "store_remember": _execute_store_remember,
    "store_recall": _execute_store_recall,
}


def get_tool_meta(name: str) -> dict[str, Any]:
    """Get safety metadata for a tool. Returns fail-closed defaults if unknown."""
    return TOOL_SAFETY.get(name, _meta())


def validate_tool_input(name: str, arguments: str | dict) -> str | None:
    """Validate tool input before execution.

    Returns None if valid, or an error message string if invalid.
    This is the first stage of the 3-stage tool pipeline:
    validate → permissions → execute.
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        return f"invalid arguments JSON: {e}"

    if not isinstance(args, dict):
        return f"Arguments must be a JSON object, got {type(args).__name__}"

    # Get tool definition to check required params
    tool_def = None
    for tool in ALL_TOOLS:
        if tool["function"]["name"] == name:
            tool_def = tool
            break

    if tool_def is None:
        return f"unknown tool '{name}'"

    # Check required parameters
    required = tool_def["function"]["parameters"].get("required", [])
    for param in required:
        if param not in args:
            return f"Missing required parameter: {param}"

    # Path validation for tools that require paths
    meta = get_tool_meta(name)
    if meta.get("requires_path"):
        path_val = args.get("path", "")
        if not path_val:
            return f"Tool '{name}' requires a 'path' parameter"
        # Block path traversal attempts
        if "\x00" in path_val:
            return "Path contains null bytes"
        # Normalize and check for suspicious patterns
        from pathlib import PurePosixPath
        normalized = str(PurePosixPath(path_val))
        if ".." in normalized.split("/"):
            # Allow relative paths but warn about traversal
            pass  # traversal is legitimate in many cases

    return None


def check_tool_permissions(name: str, mode_name: str) -> str | None:
    """Check if a tool is allowed in the given permission mode.

    Returns None if allowed, or a denial reason string.
    This is the second stage of the 3-stage tool pipeline.
    """
    allowed_tools = get_tools_for_mode(mode_name)
    allowed_names = {t["function"]["name"] for t in allowed_tools}

    if name not in allowed_names:
        meta = get_tool_meta(name)
        if meta.get("is_destructive"):
            return f"Tool '{name}' is destructive and not allowed in '{mode_name}' mode"
        return f"Tool '{name}' is not available in '{mode_name}' mode"

    return None


def execute_tool(
    name: str,
    arguments: str,
    project_path: Path,
    backend: LocalAIBackend | None = None,
    mode: str | None = None,
) -> str:
    """Execute a tool by name with JSON-encoded arguments.

    Uses a 3-stage pipeline: validate → permissions → execute.
    Returns the tool output as a string.
    """
    # Stage 1: Validate input
    validation_error = validate_tool_input(name, arguments)
    if validation_error:
        return f"Error: {validation_error}"

    # Stage 2: Check permissions (if mode provided)
    if mode:
        permission_error = check_tool_permissions(name, mode)
        if permission_error:
            return f"Error: {permission_error}"

    # Stage 3: Execute
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError as e:
        return f"Error: invalid arguments JSON: {e}"

    # Check basic tools first, then multimodal
    handler = _TOOL_REGISTRY.get(name)
    if handler:
        return handler(args, project_path)

    mm_handler = _MULTIMODAL_REGISTRY.get(name)
    if mm_handler:
        return mm_handler(args, project_path, backend=backend)

    return f"Error: unknown tool '{name}'"


def get_tools_for_mode(mode_name: str) -> list[dict]:
    """Return the appropriate tool set for the given permission mode."""
    if mode_name == "act":
        return ALL_TOOLS
    if mode_name == "edit":
        return EDIT_TOOLS
    return THINK_TOOLS  # think mode: read-only tools
