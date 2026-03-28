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
            cache_prompt=cfg.get("cache_prompt", True),
            mirostat=cfg.get("mirostat"),
            mirostat_tau=cfg.get("mirostat_tau"),
            mirostat_eta=cfg.get("mirostat_eta"),
            typical_p=cfg.get("typical_p"),
            frequency_penalty=cfg.get("frequency_penalty"),
            presence_penalty=cfg.get("presence_penalty"),
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
def aicp_voice_pipeline(
    audio_input: str,
    audio_output: str = "/tmp/aicp_mcp_voice_response.wav",
) -> str:
    """Full voice pipeline: transcribe audio → send to LLM → speak the response.

    Takes an audio file as input, transcribes it, sends the text to the local LLM,
    converts the response to speech, and saves it as a WAV file.

    Args:
        audio_input: Absolute path to the input audio file (wav, mp3, ogg, flac).
        audio_output: Where to write the response WAV file.

    Returns:
        JSON with transcription, LLM response, and output audio path.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    input_path = Path(audio_input)
    if not input_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_input}")

    result = backend.voice_pipeline(
        input_path, Path(audio_output),
        mode=Mode.THINK,
        project_path=Path.cwd(),
        whisper_model=cfg.get("whisper_model", "whisper-1"),
        tts_model=cfg.get("tts_model", "piper-tts"),
    )
    return json.dumps(result, indent=2)


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
def aicp_grammar(
    prompt: str,
    grammar: str,
    mode: str = "think",
) -> str:
    """Generate text constrained by a GBNF grammar using the local LLM.

    GBNF grammars force the model output to conform to a formal grammar.
    More powerful than JSON mode — can constrain to YAML, CSV, enums, custom formats.

    Example grammars:
      - Boolean: 'root ::= ("yes" | "no")'
      - Rating:  'root ::= ("1" | "2" | "3" | "4" | "5")'
      - CSV row: 'root ::= field "," field "," field "\\n"  field ::= [a-zA-Z0-9 ]+'

    Args:
        prompt: The text prompt.
        grammar: GBNF grammar string defining allowed output format.
        mode: Permission mode — think, edit, or act. Defaults to think.

    Returns:
        The grammar-constrained model response.
    """
    backend = _get_backend()
    m = Mode(mode) if mode in ("think", "edit", "act") else Mode.THINK
    return backend.execute_grammar(prompt, grammar, m, Path.cwd())


@mcp.tool()
def aicp_rerank(
    query: str,
    documents: list[str],
    top_n: int = 5,
) -> str:
    """Rerank documents by relevance to a query using a local cross-encoder model (BGE-reranker).

    Useful for improving RAG results — first retrieve candidates with embedding search,
    then rerank them with this tool for higher precision.

    Args:
        query: The search query.
        documents: List of document strings to score against the query.
        top_n: Number of top results to return (default: 5).

    Returns:
        JSON array of results with index, relevance_score, and document text.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    model = cfg.get("reranker_model", "bge-reranker-v2-m3")
    results = backend.rerank(query, documents, model=model, top_n=top_n)
    # Enrich results with the original document text
    for r in results:
        idx = r.get("index", 0)
        if 0 <= idx < len(documents):
            r["document"] = documents[idx]
    return json.dumps(results, indent=2)


@mcp.tool()
def aicp_system() -> str:
    """Get LocalAI system status: active GPU model, installed backends, and all available models.

    Useful for understanding which model is currently loaded in GPU memory
    (with SINGLE_ACTIVE_BACKEND, only one GPU model is loaded at a time).

    Returns:
        JSON with loaded_models (in GPU), backends, and all configured models.
    """
    backend = _get_backend()
    from aicp.core.observability import get_system_info, get_loaded_models
    sys_info = get_system_info(backend.base_url)
    models = get_loaded_models(backend.base_url)
    return json.dumps({
        "active_gpu_model": sys_info.get("loaded_models", []),
        "installed_backends": sys_info.get("backends", []),
        "configured_models": models,
    }, indent=2)


@mcp.tool()
def aicp_agent(
    prompt: str,
    mode: str = "think",
    max_rounds: int = 5,
) -> str:
    """Run a prompt with native function calling — the local LLM can autonomously call tools.

    The LLM gets access to tools matching the permission mode (file_read, grep, kb_search,
    system_info, etc.) and can call them in a loop to gather information before answering.
    Uses OpenAI-compatible native function calling with grammar-constrained output.

    Args:
        prompt: The task or question for the agent.
        mode: Permission mode — think (read-only tools), edit (+ generate), act (+ shell). Default: think.
        max_rounds: Maximum tool-call loops before forcing a final answer (default: 5).

    Returns:
        The agent's final answer after using tools.
    """
    backend = _get_backend()
    m = Mode(mode) if mode in ("think", "edit", "act") else Mode.THINK
    return backend.execute_with_native_tools(prompt, m, Path.cwd(), max_rounds=max_rounds)


@mcp.tool()
def aicp_store_set(text: str, store: str = "memory") -> str:
    """Store text in LocalAI's ephemeral working memory (in-memory, lost on restart).

    Embeds the text automatically and stores it for later similarity search.
    Use for session-scoped notes, findings, or context the agent needs to remember.

    Args:
        text: The text to store.
        store: Store name (default: "memory"). Different names create separate stores.

    Returns:
        Confirmation message.
    """
    backend = _get_backend()
    backend.store_set([text], store_name=store)
    return f"Stored in '{store}': {text[:100]}"


@mcp.tool()
def aicp_store_find(query: str, top_k: int = 5, store: str = "memory") -> str:
    """Search LocalAI's ephemeral working memory by semantic similarity.

    Returns the most relevant entries previously stored with aicp_store_set.

    Args:
        query: What to search for.
        top_k: Number of results (default: 5).
        store: Store name (default: "memory").

    Returns:
        JSON array of results with value and similarity score.
    """
    backend = _get_backend()
    results = backend.store_find(query, store_name=store, top_k=top_k)
    return json.dumps(results, indent=2)


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


@mcp.tool()
def aicp_tokenize(text: str) -> str:
    """Count tokens in text using the local model's tokenizer.

    Useful for checking prompt size before sending, or for guardrails.

    Args:
        text: The text to tokenize.

    Returns:
        JSON with token count and token IDs.
    """
    backend = _get_backend()
    result = backend.tokenize(text)
    return json.dumps(result, indent=2)


@mcp.tool()
def aicp_edit(input_text: str, instruction: str) -> str:
    """Edit text based on an instruction using the local LLM.

    Uses /v1/edits endpoint for instruction-based text transformation.

    Args:
        input_text: The text to edit.
        instruction: What edit to perform (e.g. "fix grammar", "translate to French").

    Returns:
        The edited text.
    """
    backend = _get_backend()
    return backend.edit(input_text, instruction)


@mcp.tool()
def aicp_p2p_status() -> str:
    """Get P2P cluster status — online workers, federation nodes, and statistics.

    Shows the state of the LocalAI distributed inference cluster.

    Returns:
        JSON with cluster stats and worker list.
    """
    backend = _get_backend()
    stats = backend.p2p_stats()
    workers = backend.p2p_workers()
    return json.dumps({"stats": stats, "workers": workers}, indent=2)


@mcp.tool()
def aicp_sound(
    prompt: str,
    output_path: str = "/tmp/aicp_mcp_sound.wav",
) -> str:
    """Generate sound or music from a text description using a local model.

    Args:
        prompt: Description of the sound to generate (e.g. "a gentle piano melody with rain").
        output_path: Where to write the audio file (default: /tmp/aicp_mcp_sound.wav).

    Returns:
        Path to the generated audio file.
    """
    backend = _get_backend()
    cfg = get_backend_config(_config, "local")
    model = cfg.get("sound_model", "transformers-musicgen")
    out = Path(output_path)
    backend.generate_sound(prompt, out, model=model)
    return str(out)


@mcp.tool()
def aicp_complete(
    prompt: str,
    max_tokens: int = 512,
    stop: str = "",
) -> str:
    """Raw text completion using /v1/completions (no chat template overhead).

    Better than chat for code infill, text continuation, and single-shot generation
    where chat framing is unnecessary.

    Args:
        prompt: The text to complete.
        max_tokens: Maximum tokens to generate (default: 512).
        stop: Comma-separated stop sequences (e.g. "\\n,###").

    Returns:
        The completed text.
    """
    backend = _get_backend()
    stop_list = [s.strip() for s in stop.split(",") if s.strip()] if stop else None
    return backend.complete(prompt, max_tokens=max_tokens, stop=stop_list)


@mcp.tool()
def aicp_model_gallery(search: str = "") -> str:
    """Browse LocalAI's model gallery — see what's available to install.

    Args:
        search: Optional search filter (matches name or description).

    Returns:
        JSON array of available models with name, installed status, and tags.
    """
    backend = _get_backend()
    available = backend.models_available()
    if search:
        available = [m for m in available if search.lower() in m["name"].lower()
                     or search.lower() in m.get("description", "").lower()]
    return json.dumps(available[:30], indent=2)


@mcp.tool()
def aicp_model_install(model_id: str, name: str = "") -> str:
    """Install a model from the LocalAI gallery (async download).

    Args:
        model_id: Gallery model ID (e.g. "huggingface@user/model" or model name).
        name: Optional custom name for the installed model.

    Returns:
        JSON with job UUID for tracking progress.
    """
    backend = _get_backend()
    result = backend.model_apply(model_id, name=name)
    return json.dumps(result, indent=2)


@mcp.tool()
def aicp_model_status(model_or_job: str) -> str:
    """Check model state or download job progress.

    If given a UUID, checks download job progress.
    If given a model name, checks if the model is loaded and its memory usage.

    Args:
        model_or_job: Model name or job UUID.

    Returns:
        JSON with status information.
    """
    backend = _get_backend()
    # Try as job UUID first (UUIDs contain hyphens and are 36 chars)
    if len(model_or_job) > 30 and "-" in model_or_job:
        try:
            return json.dumps(backend.model_job_status(model_or_job), indent=2)
        except Exception:
            pass
    # Fall back to model monitor
    info = backend.model_monitor(model_or_job)
    state_map = {0: "uninitialized", 1: "busy", 2: "ready", -1: "error"}
    info["state_label"] = state_map.get(info.get("state", -1), "unknown")
    return json.dumps(info, indent=2)


@mcp.tool()
def aicp_model_unload(model_name: str) -> str:
    """Unload a model from GPU memory (does not delete files).

    Useful with SINGLE_ACTIVE_BACKEND to free GPU for another model.

    Args:
        model_name: Name of the model to unload.

    Returns:
        Success or failure message.
    """
    backend = _get_backend()
    success = backend.model_shutdown(model_name)
    return f"Unloaded: {model_name}" if success else f"Failed to unload: {model_name}"


@mcp.tool()
def aicp_tokenize_batch(texts: str) -> str:
    """Tokenize multiple texts at once. Provide texts separated by newlines.

    Args:
        texts: Newline-separated texts to tokenize.

    Returns:
        JSON array of {tokens: [...], count: N} for each input text.
    """
    backend = _get_backend()
    text_list = [t for t in texts.split("\n") if t.strip()]
    results = backend.tokenize_batch(text_list)
    return json.dumps(results)


@mcp.tool()
def aicp_health() -> str:
    """Check LocalAI health and readiness status.

    Returns:
        JSON with healthy (bool), ready (bool), and status details.
    """
    backend = _get_backend()
    health = backend.health_check()
    ready = backend.is_ready()
    return json.dumps({"healthy": health.get("healthy", False), "ready": ready, **health})


@mcp.tool()
def aicp_backends_list() -> str:
    """List installed LocalAI backends (execution engines).

    Returns:
        JSON array of installed backends.
    """
    backend = _get_backend()
    backends = backend.backends_list()
    return json.dumps(backends)


@mcp.tool()
def aicp_server_config() -> str:
    """Detect LocalAI server capabilities and features.

    Returns:
        JSON with health, readiness, loaded models, backends, and detected features.
    """
    backend = _get_backend()
    config = backend.server_config()
    return json.dumps(config)


@mcp.tool()
def aicp_model_delete(model_name: str) -> str:
    """Delete/uninstall a model from LocalAI.

    Args:
        model_name: Name of the model to delete.

    Returns:
        Success or failure message.
    """
    backend = _get_backend()
    success = backend.model_delete(model_name)
    return f"Deleted: {model_name}" if success else f"Failed to delete: {model_name}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_stdio() -> None:
    """Run the MCP server on stdio transport (for Claude Code integration)."""
    mcp.run(transport="stdio")


def main() -> None:
    """CLI entry point for aicp-mcp."""
    run_stdio()
