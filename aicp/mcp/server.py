"""AICP MCP Server — expose LocalAI capabilities as MCP tools.

Run with:  aicp --mcp          (stdio transport, for Claude Code integration)
           aicp-mcp             (standalone entry point)
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from aicp.backends.localai import LocalAIBackend
from aicp.config.loader import load_config, get_backend_config
from aicp.core.modes import Mode

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_config: dict[str, Any] = {}
_backend: LocalAIBackend | None = None


def _get_backend() -> LocalAIBackend:
    """Lazy-init the LocalAI backend from config."""
    global _config, _backend
    if _backend is None:
        _config = load_config()
        cfg = get_backend_config(_config, "local")
        _backend = LocalAIBackend(
            base_url=cfg.get("base_url", "http://localhost:8090"),
            model=cfg.get("model", "default"),
            max_tokens=cfg.get("max_tokens", 2048),
            api_key=cfg.get("api_key", ""),
            temperature=cfg.get("temperature"),
            top_p=cfg.get("top_p"),
            top_k=cfg.get("top_k"),
            repeat_penalty=cfg.get("repeat_penalty"),
            embedding_model=cfg.get("embedding_model", ""),
            code_model=cfg.get("code_model", ""),
            vision_model=cfg.get("vision_model", ""),
            auto_route=cfg.get("auto_route", False),
        )
    return _backend


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "aicp",
    instructions="AI Control Platform — local AI tools powered by LocalAI",
)


@mcp.tool()
def aicp_chat(prompt: str, mode: str = "think") -> str:
    """Send a prompt to the local LLM (Hermes / CodeLlama with auto-routing).

    Args:
        prompt: The text prompt to send.
        mode: Permission mode — think (read-only), edit, or act. Defaults to think.

    Returns:
        The model's response text.
    """
    backend = _get_backend()
    m = Mode(mode) if mode in ("think", "edit", "act") else Mode.THINK
    return backend.execute(prompt, m, Path.cwd())


@mcp.tool()
def aicp_transcribe(
    audio_path: str,
    language: str = "en",
) -> str:
    """Transcribe an audio file to text using the local Whisper model.

    Args:
        audio_path: Absolute path to the audio file (wav, mp3, ogg, flac).
        language: Language hint for transcription (default: en).

    Returns:
        The transcribed text.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    model = cfg.get("whisper_model", "whisper-1")
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    result = backend.transcribe(path, model=model, language=language)
    return result.get("text", "").strip()


@mcp.tool()
def aicp_speak(
    text: str,
    output_path: str = "/tmp/aicp_mcp_tts.wav",
) -> str:
    """Convert text to speech using the local Piper TTS model.

    Args:
        text: The text to synthesize into speech.
        output_path: Where to write the WAV file (default: /tmp/aicp_mcp_tts.wav).

    Returns:
        Path to the generated WAV file.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    model = cfg.get("tts_model", "piper-tts")
    out = Path(output_path)
    backend.speak(text, out, model=model)
    return str(out)


@mcp.tool()
def aicp_vision(
    image_path: str,
    prompt: str = "Describe this image in detail.",
) -> str:
    """Analyze an image using the local LLaVA vision model.

    Args:
        image_path: Absolute path to the image file (png, jpg, gif, webp, bmp).
        prompt: What to ask about the image.

    Returns:
        The vision model's description/analysis.
    """
    backend = _get_backend()
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/png")
    image_data = base64.b64encode(path.read_bytes()).decode("ascii")

    return backend.execute_vision(prompt, image_data, Mode.THINK, Path.cwd(), image_mime=mime)


@mcp.tool()
def aicp_imagine(
    prompt: str,
    output_path: str = "/tmp/aicp_mcp_imagine.png",
    size: str = "512x512",
) -> str:
    """Generate an image from a text prompt using local Stable Diffusion.

    Args:
        prompt: Text description of the image to generate. Use '|' to separate positive and negative prompts.
        output_path: Where to write the PNG file (default: /tmp/aicp_mcp_imagine.png).
        size: Image dimensions as 'WxH' (default: 512x512).

    Returns:
        Path to the generated image file.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    model = cfg.get("image_model", "stablediffusion")
    out = Path(output_path)
    backend.generate_image(prompt, out, model=model, size=size)
    return str(out)


@mcp.tool()
def aicp_embed(text: str) -> list[float]:
    """Generate an embedding vector for text using the local embedding model (nomic-embed).

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.
    """
    backend = _get_backend()
    return backend.embed(text)


@mcp.tool()
def aicp_models() -> str:
    """List all models currently loaded in LocalAI.

    Returns:
        JSON string with model IDs and status.
    """
    backend = _get_backend()
    import httpx
    try:
        resp = httpx.get(f"{backend.base_url}/v1/models", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            models = [{"id": m.get("id"), "object": m.get("object")} for m in data.get("data", [])]
            return json.dumps(models, indent=2)
        return f"Error: HTTP {resp.status_code}"
    except Exception as e:
        return f"LocalAI not reachable: {e}"


@mcp.tool()
def aicp_kb_search(query: str, top_k: int = 5) -> str:
    """Search the AICP knowledge base using semantic search (RAG).

    Args:
        query: The search query.
        top_k: Number of results to return (default: 5).

    Returns:
        JSON array of matching chunks with source and score.
    """
    try:
        from aicp.core.kb import KnowledgeBase
        backend = _get_backend()
        kb = KnowledgeBase(backend, _config)
        results = kb.search(query, top_k=top_k)
        return json.dumps(results, indent=2)
    except ImportError:
        return "Knowledge base module not available."
    except Exception as e:
        return f"KB search error: {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_stdio() -> None:
    """Run the MCP server on stdio transport (for Claude Code integration)."""
    mcp.run(transport="stdio")


def main() -> None:
    """CLI entry point for aicp-mcp."""
    run_stdio()
