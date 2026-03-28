"""Interactive REPL mode for LocalAI conversations."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx

from aicp.core.context import build_project_context
from aicp.core.modes import Mode

if TYPE_CHECKING:
    from aicp.backends.localai import LocalAIBackend


# ── Slash commands ──────────────────────────────────────────────────────────

_SLASH_HELP = """\
Slash commands:
  /vision <path> [prompt]   Analyze an image (default: describe it)
  /transcribe <path>        Transcribe audio → use as next message
  /speak                    Speak the last AI response via TTS
  /imagine <prompt>         Generate an image (saved to /tmp/aicp_imagine.png)
  /voice <path>             Voice pipeline: audio in → LLM → audio out
  /kb search <query>        Search the knowledge base (with reranking)
  /kb status                Show KB stats (sources, chunks)
  /grammar <grammar> <prompt>  Constrain output with GBNF grammar
  /tools <prompt>           Agentic mode: LLM can call tools (file, grep, KB, system)
  /store set <text>         Store text in working memory (ephemeral)
  /store find <query>       Search working memory by similarity
  /sound <prompt>           Generate sound/music from text description
  /complete <text>          Raw text completion (no chat template)
  /edit <instruction> | <text>  Edit text by instruction (e.g. fix grammar)
  /tokenize <text>          Count tokens in text
  /health                   Check LocalAI health, readiness, and features
  /backends                 List installed LocalAI backends
  /help                     Show this help
  /exit                     Quit
"""


def _handle_slash(
    command: str,
    messages: List[Dict[str, str]],
    backend: Optional[LocalAIBackend],
    config: dict,
    mode: Mode,
    project_path: Path,
) -> Optional[str]:
    """Handle a slash command. Returns a user-message string to inject, or None."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/help":
        print(_SLASH_HELP)
        return None

    if not backend:
        print("[error] Multimodal commands require a LocalAI backend.", file=sys.stderr)
        return None

    local_cfg = config.get("backends", {}).get("local", {})

    if cmd == "/vision":
        vparts = arg.split(maxsplit=1)
        img_path = Path(vparts[0]) if vparts else None
        prompt = vparts[1] if len(vparts) > 1 else "Describe this image in detail."
        if not img_path or not img_path.exists():
            print(f"[error] Image not found: {img_path}", file=sys.stderr)
            return None
        try:
            suffix = img_path.suffix.lower()
            mime_map = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            }
            mime = mime_map.get(suffix, "image/png")
            image_data = base64.b64encode(img_path.read_bytes()).decode("ascii")
            result = backend.execute_vision(prompt, image_data, mode, project_path, image_mime=mime)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[Analyzed image: {img_path.name}] {prompt}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Vision failed: {e}", file=sys.stderr)
        return None

    if cmd == "/transcribe":
        audio_path = Path(arg) if arg else None
        if not audio_path or not audio_path.exists():
            print(f"[error] Audio file not found: {audio_path}", file=sys.stderr)
            return None
        try:
            whisper_model = local_cfg.get("whisper_model", "whisper-1")
            result = backend.transcribe(audio_path, model=whisper_model)
            text = result.get("text", "").strip()
            if text:
                print(f"  [transcribed] {text}")
                return text  # inject as user message
            else:
                print("[warning] No speech detected.", file=sys.stderr)
        except Exception as e:
            print(f"[error] Transcription failed: {e}", file=sys.stderr)
        return None

    if cmd == "/speak":
        # Speak the last assistant message
        last_ai = None
        for m in reversed(messages):
            if m["role"] == "assistant":
                last_ai = m["content"]
                break
        if not last_ai:
            print("[error] No AI response to speak.", file=sys.stderr)
            return None
        try:
            tts_model = local_cfg.get("tts_model", "piper-tts")
            out = Path("/tmp/aicp_interactive_tts.wav")
            backend.speak(last_ai, out, model=tts_model)
            print(f"  [audio saved to {out}]")
        except Exception as e:
            print(f"[error] TTS failed: {e}", file=sys.stderr)
        return None

    if cmd == "/imagine":
        if not arg:
            print("[error] Usage: /imagine <prompt>", file=sys.stderr)
            return None
        try:
            img_model = local_cfg.get("image_model", "stablediffusion")
            out = Path("/tmp/aicp_interactive_imagine.png")
            backend.generate_image(arg, out, model=img_model)
            print(f"  [image saved to {out}]")
            messages.append({"role": "user", "content": f"[Generated image: {arg}]"})
            messages.append({"role": "assistant", "content": f"Image generated and saved to {out}"})
        except Exception as e:
            print(f"[error] Image generation failed: {e}", file=sys.stderr)
        return None

    if cmd == "/voice":
        audio_path = Path(arg) if arg else None
        if not audio_path or not audio_path.exists():
            print(f"[error] Audio file not found: {audio_path}", file=sys.stderr)
            return None
        try:
            out = Path("/tmp/aicp_interactive_voice.wav")
            result = backend.voice_pipeline(
                audio_path, out, mode, project_path,
                whisper_model=local_cfg.get("whisper_model", "whisper-1"),
                tts_model=local_cfg.get("tts_model", "piper-tts"),
            )
            print(f"  [you said] {result['transcription']}")
            print(f"\nai> {result['response']}\n")
            print(f"  [audio response saved to {out}]")
            messages.append({"role": "user", "content": result["transcription"]})
            messages.append({"role": "assistant", "content": result["response"]})
        except Exception as e:
            print(f"[error] Voice pipeline failed: {e}", file=sys.stderr)
        return None

    if cmd == "/kb":
        subcmd_parts = arg.split(maxsplit=1)
        subcmd = subcmd_parts[0] if subcmd_parts else ""
        subarg = subcmd_parts[1].strip() if len(subcmd_parts) > 1 else ""

        if subcmd == "search" and subarg:
            if not backend:
                print("[error] KB search requires a LocalAI backend.", file=sys.stderr)
                return None
            try:
                from aicp.core.kb import KnowledgeBase
                from aicp.config.loader import load_config
                kb_config = load_config()
                kb = KnowledgeBase(backend, kb_config)
                results = kb.search(subarg)
                if not results:
                    print("  [no results found]")
                else:
                    for i, r in enumerate(results, 1):
                        src = Path(r["source"]).name if "/" in r["source"] else r["source"]
                        preview = r["text"][:150].replace("\n", " ")
                        if len(r["text"]) > 150:
                            preview += "..."
                        print(f"  #{i} (score: {r['score']:.3f}) [{src}] {preview}")
            except ImportError:
                print("[error] Knowledge base module not available.", file=sys.stderr)
            except Exception as e:
                print(f"[error] KB search failed: {e}", file=sys.stderr)
            return None

        if subcmd == "status":
            try:
                from aicp.core.rag import VectorStore
                from aicp.config.loader import load_config, get_rag_config
                kb_config = load_config()
                rag_cfg = get_rag_config(kb_config)
                db_path = Path(rag_cfg["db_path"])
                if not db_path.is_absolute():
                    db_path = project_path / db_path
                if db_path.exists():
                    vs = VectorStore(db_path)
                    info = vs.stats(rag_cfg["store_name"])
                    vs.close()
                    print(f"  Store:   {info['store']}")
                    print(f"  Sources: {info['total_sources']}")
                    print(f"  Chunks:  {info['total_chunks']}")
                else:
                    print("  [KB database not found — ingest files with: aicp --kb add --kb-arg <path>]")
            except Exception as e:
                print(f"[error] KB status failed: {e}", file=sys.stderr)
            return None

        print("[error] Usage: /kb search <query> | /kb status", file=sys.stderr)
        return None

    if cmd == "/store":
        subcmd_parts = arg.split(maxsplit=1)
        subcmd = subcmd_parts[0] if subcmd_parts else ""
        subarg = subcmd_parts[1].strip() if len(subcmd_parts) > 1 else ""

        if subcmd == "set" and subarg:
            try:
                backend.store_set([subarg], store_name="memory")
                print(f"  [stored] {subarg[:100]}")
            except Exception as e:
                print(f"[error] Store failed: {e}", file=sys.stderr)
            return None

        if subcmd == "find" and subarg:
            try:
                results = backend.store_find(subarg, store_name="memory", top_k=5)
                if not results:
                    print("  [no results in working memory]")
                else:
                    for i, r in enumerate(results, 1):
                        preview = r["value"][:150].replace("\n", " ")
                        if len(r["value"]) > 150:
                            preview += "..."
                        print(f"  #{i} (sim: {r['similarity']:.3f}) {preview}")
            except Exception as e:
                print(f"[error] Store search failed: {e}", file=sys.stderr)
            return None

        print("[error] Usage: /store set <text> | /store find <query>", file=sys.stderr)
        return None

    if cmd == "/tools":
        if not backend:
            print("[error] Tool-use mode requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /tools <prompt>", file=sys.stderr)
            print("  The LLM will autonomously call tools to answer your prompt.", file=sys.stderr)
            return None
        try:
            result = backend.execute_with_native_tools(arg, mode, project_path)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[tools] {arg}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Tool-use failed: {e}", file=sys.stderr)
        return None

    if cmd == "/sound":
        if not arg:
            print("[error] Usage: /sound <description>", file=sys.stderr)
            print("  Example: /sound a gentle piano melody with rain", file=sys.stderr)
            return None
        try:
            sound_model = config.get("backends", {}).get("local", {}).get("sound_model", "transformers-musicgen")
            out = Path("/tmp/aicp_interactive_sound.wav")
            backend.generate_sound(arg, out, model=sound_model)
            print(f"  [sound saved to {out}]")
            messages.append({"role": "user", "content": f"[Generated sound: {arg}]"})
            messages.append({"role": "assistant", "content": f"Sound generated and saved to {out}"})
        except Exception as e:
            print(f"[error] Sound generation failed: {e}", file=sys.stderr)
        return None

    if cmd == "/complete":
        if not arg:
            print("[error] Usage: /complete <text to continue>", file=sys.stderr)
            return None
        try:
            result = backend.complete(arg)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[complete] {arg}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Completion failed: {e}", file=sys.stderr)
        return None

    if cmd == "/edit":
        if not arg or "|" not in arg:
            print("[error] Usage: /edit <instruction> | <text>", file=sys.stderr)
            print("  Example: /edit fix grammar | Their going to the store", file=sys.stderr)
            return None
        instruction, input_text = arg.split("|", 1)
        instruction = instruction.strip()
        input_text = input_text.strip()
        if not instruction or not input_text:
            print("[error] Both instruction and text are required.", file=sys.stderr)
            return None
        try:
            result = backend.edit(input_text, instruction)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[edit: {instruction}] {input_text}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Edit failed: {e}", file=sys.stderr)
        return None

    if cmd == "/tokenize":
        if not arg:
            print("[error] Usage: /tokenize <text>", file=sys.stderr)
            return None
        try:
            result = backend.tokenize(arg)
            print(f"  Tokens: {result['count']}")
            if result["count"] <= 50:
                print(f"  IDs:    {result['tokens']}")
        except Exception as e:
            print(f"[error] Tokenize failed: {e}", file=sys.stderr)
        return None

    if cmd == "/health":
        if not backend:
            print("[error] Health commands require a LocalAI backend.", file=sys.stderr)
            return None
        try:
            health = backend.health_check()
            ready = backend.is_ready()
            h_status = "healthy" if health.get("healthy") else health.get("error", "unhealthy")
            r_status = "ready" if ready else "not ready"
            print(f"  Health:    {h_status}")
            print(f"  Readiness: {r_status}")
            srv = backend.server_config()
            features = srv.get("features", [])
            if features:
                print(f"  Features:  {', '.join(features)}")
            models = srv.get("models", [])
            if models:
                print(f"  Models:    {', '.join(models)}")
        except Exception as e:
            print(f"[error] Health check failed: {e}", file=sys.stderr)
        return None

    if cmd == "/backends":
        if not backend:
            print("[error] Backend commands require a LocalAI backend.", file=sys.stderr)
            return None
        try:
            bl = backend.backends_list()
            if bl:
                for b in bl:
                    name = b if isinstance(b, str) else b.get("name", str(b))
                    print(f"  - {name}")
            else:
                print("  No backends found (endpoint may not be available)")
        except Exception as e:
            print(f"[error] Backends list failed: {e}", file=sys.stderr)
        return None

    if cmd == "/grammar":
        if not backend:
            print("[error] Grammar commands require a LocalAI backend.", file=sys.stderr)
            return None
        # Parse: /grammar <grammar> <prompt>
        # Grammar is typically quoted or ends at a recognizable boundary
        # Support: /grammar root ::= ("yes" | "no") Is Python compiled?
        # Or: /grammar "root ::= (\"yes\" | \"no\")" Is Python compiled?
        if not arg:
            print("[error] Usage: /grammar <gbnf-grammar> | <prompt>", file=sys.stderr)
            print("  Example: /grammar root ::= (\"yes\" | \"no\") | Is Python compiled?", file=sys.stderr)
            return None
        # Split on | delimiter: grammar | prompt
        if "|" in arg:
            grammar_str, prompt_str = arg.split("|", 1)
            grammar_str = grammar_str.strip()
            prompt_str = prompt_str.strip()
        else:
            print("[error] Use | to separate grammar and prompt:", file=sys.stderr)
            print("  /grammar root ::= (\"yes\" | \"no\") | Is the sky blue?", file=sys.stderr)
            return None
        if not grammar_str or not prompt_str:
            print("[error] Both grammar and prompt are required.", file=sys.stderr)
            return None
        try:
            result = backend.execute_grammar(prompt_str, grammar_str, mode, project_path)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[Grammar: {grammar_str}] {prompt_str}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Grammar generation failed: {e}", file=sys.stderr)
        return None

    print(f"[error] Unknown command: {cmd}. Type /help for commands.", file=sys.stderr)
    return None


# ── Main interactive loop ──────────────────────────────────────────────────

def run_interactive(
    base_url: str,
    model: str,
    mode: Mode,
    project_path: Path,
    max_tokens: int = 2048,
    stream: bool = True,
    backend: Optional[LocalAIBackend] = None,
    config: Optional[dict] = None,
) -> int:
    """Run an interactive chat session against LocalAI.

    Args:
        base_url:     LocalAI API base URL.
        model:        Model alias to use.
        mode:         Permission mode (think/edit/act).
        project_path: Project directory for context injection.
        max_tokens:   Max completion tokens per turn (from config).
        stream:       If True, stream responses token-by-token (default: True).
        backend:      LocalAI backend for multimodal commands.
        config:       Full config dict for model names.
    """
    system = _build_system(mode, project_path)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    config = config or {}

    # Auto-RAG setup: augment prompts with KB context when enabled
    _auto_rag_kb = None
    _auto_rag_max_chars = 3000
    if backend and config:
        rag_cfg = config.get("rag", {})
        if rag_cfg.get("enabled", False):
            try:
                from aicp.core.kb import KnowledgeBase
                kb = KnowledgeBase(backend, config)
                if kb.stats().get("total_chunks", 0) > 0:
                    _auto_rag_kb = kb
                    _auto_rag_max_chars = rag_cfg.get("max_context_chars", 3000)
            except Exception:
                pass

    mm_hint = " | /help for commands" if backend else ""
    rag_hint = " | RAG: on" if _auto_rag_kb else ""
    print(f"AICP interactive — {model} @ {base_url}")
    print(f"Mode: {mode.value} | Project: {project_path.name} | Stream: {stream}{mm_hint}{rag_hint}")
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

        # Handle slash commands
        if prompt.startswith("/"):
            injected = _handle_slash(prompt, messages, backend, config, mode, project_path)
            if injected:
                # Slash command returned text to inject as user message
                prompt = injected
            else:
                continue

        # Auto-RAG: augment with KB context if enabled
        display_prompt = prompt
        if _auto_rag_kb and not prompt.startswith("/"):
            try:
                augmented = _auto_rag_kb.augment_prompt(prompt, max_context_chars=_auto_rag_max_chars)
                if augmented != prompt:
                    prompt = augmented
            except Exception:
                pass  # Silently fall back to unaugmented prompt

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
        "cache_prompt": True,
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
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "cache_prompt": True},
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
