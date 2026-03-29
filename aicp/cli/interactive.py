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
  /transcribe-detail <path> [lang]  Verbose transcription with timestamps
  /speak                    Speak the last AI response via TTS
  /tts [voice] [speed] <text>  Generate speech via OpenAI-compatible TTS API
  /voices                   List available TTS voices
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
  /detokenize <id1> <id2> ...  Convert token IDs back to text
  /token-count <text>      Quick token count (no IDs)
  /vad <audio_path>         Detect voice segments in audio file
  /detect <image_path>      Detect objects in image
  /health                   Check LocalAI health, readiness, and features
  /backends                 List installed LocalAI backends
  /metrics                  Live Prometheus metrics, GPU, and API call stats
  /batch <p1> | <p2> | ...  Run multiple prompts concurrently (pipe-separated)
  /infill <prefix> | <suffix>  Fill-in-the-middle code completion (Copilot-style)
  /embed-image <path>       Generate embedding for an image (CLIP-style)
  /lora load <model> <path> Load a LoRA adapter onto a model
  /lora list                List models with LoRA adapters
  /config [model]           Show model config (context_size, gpu_layers, …)
  /config set <key> <value> Update a model parameter at runtime
  /json <prompt>            Force JSON output (structured responses)
  /seed [number]            Set/show seed for reproducible inference (clear = random)
  /logprobs <prompt>        Show response with per-token log probabilities
  /bestof [N] <prompt>      Generate N completions, pick the best (default: 3)
  /chat-image <path> <prompt> Multi-turn visual chat (image added to history)
  /embed-typed <q|d> <text> Typed embedding (query vs document) for asymmetric search
  /warmup [model]           Pre-load a model into VRAM (avoid cold-start latency)
  /loaded                   List currently loaded models
  /complete-lp <text>       Raw completion with token log probabilities
  /complete-n [N] <text>    Generate N raw text completions (default: 3)
  /similarity <t1> | <t2>  Cosine similarity between two texts
  /neighbors <query> | <d1> | <d2> ...  Find nearest documents to query
  /fleet                    Show fleet status (all nodes)
  /fleet-run <prompt>       Run a task on the best available fleet node
  /fleet-route              Show where the next task would be routed
  /offload                  Show LocalAI offload metrics (progress toward 80% goal)
  /route <prompt>           Show routing decision without executing (backend + model)
  /status                   System status (GPU, model, routing, offload progress)
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

    if cmd == "/fleet":
        try:
            from aicp.core.cluster import load_fleet_config, check_cluster
            nodes = load_fleet_config()
            if not nodes:
                print("  No fleet configured. Run: make fleet-init", file=sys.stderr)
                return None
            nodes = check_cluster(nodes)
            print(f"\n  Fleet: {len(nodes)} node(s)\n")
            for n in nodes:
                status = "\033[0;32m●\033[0m online" if n.online else "\033[0;31m●\033[0m offline"
                print(f"    {n.name} ({n.host}:{n.port})  {status}")
                if n.gpus:
                    for g in n.gpus:
                        print(f"      GPU: {g.get('name', '?')} — {g.get('vram_free_mb', '?')}MB free / {g.get('vram_total_mb', '?')}MB")
                if n.models:
                    names = [m.get("name", "?") for m in n.models]
                    print(f"      Models: {', '.join(names)}")
            print()
        except Exception as e:
            print(f"[error] Fleet status failed: {e}", file=sys.stderr)
        return None

    if cmd == "/fleet-run":
        if not arg:
            print("[error] Usage: /fleet-run <prompt>", file=sys.stderr)
            return None
        try:
            from aicp.core.cluster import load_fleet_config, check_cluster, find_best_node, execute_remote
            nodes = load_fleet_config()
            if not nodes:
                print("  No fleet configured. Run: make fleet-init", file=sys.stderr)
                return None
            nodes = check_cluster(nodes)
            best = find_best_node(nodes)
            if not best:
                print("[error] No fleet nodes are online.", file=sys.stderr)
                return None
            print(f"  Routing to: {best.name} ({best.host}:{best.port})")
            result = execute_remote(best, arg, mode=str(mode.value), backend="local")
            text = result.get("result", "")
            duration = result.get("duration_seconds", 0)
            print(f"  [{best.name}, {duration}s]\n")
            print(text)
            messages.append({"role": "user", "content": arg})
            messages.append({"role": "assistant", "content": text})
        except Exception as e:
            print(f"[error] Fleet-run failed: {e}", file=sys.stderr)
        return None

    if cmd == "/fleet-route":
        try:
            from aicp.core.cluster import load_fleet_config, check_cluster, find_best_node
            from aicp.core.controller import _local_ips
            import socket as _sock

            nodes = load_fleet_config()
            if not nodes:
                print("  No fleet configured. Run: make fleet-init", file=sys.stderr)
                return None

            auto_route = config.get("cluster", {}).get("auto_route", False)
            nodes = check_cluster(nodes)
            best = find_best_node(nodes)

            print(f"\n  Fleet routing {'ENABLED' if auto_route else 'DISABLED'}")
            print(f"  Nodes: {len(nodes)} total, {sum(1 for n in nodes if n.online)} online")
            if best:
                local_ips = _local_ips()
                is_self = best.host in local_ips or best.name.lower() == _sock.gethostname().lower()
                where = "LOCAL (this machine)" if is_self else f"REMOTE → {best.name} ({best.host}:{best.port})"
                print(f"  Best node: {best.name} ({best.host})")
                print(f"  Next task would run: {where}")
                if best.gpus:
                    for g in best.gpus:
                        print(f"    GPU: {g.get('name', '?')} — {g.get('vram_free_mb', '?')}MB free")
            else:
                print("  Best node: NONE (all offline) → would run locally")
            if not auto_route:
                print("  To enable: set cluster.auto_route: true in config/default.yaml")
            print()
        except Exception as e:
            print(f"[error] Fleet-route failed: {e}", file=sys.stderr)
        return None

    if cmd == "/offload":
        try:
            from aicp.core.metrics import offload_report
            r = offload_report()

            if r["total_tasks"] == 0:
                print("\n  No task history yet. Run some tasks first.\n")
                return None

            goal_icon = "OK" if r["goal_met"] else "  "
            bar_len = 30
            filled = int(r["offload_pct"] / 100 * bar_len)
            bar = "#" * filled + "-" * (bar_len - filled)
            target_pos = int(80 / 100 * bar_len)
            bar_list = list(bar)
            if target_pos < bar_len:
                bar_list[target_pos] = "|"
            bar_str = "".join(bar_list)

            print(f"\n  LocalAI Offload Dashboard")
            print(f"  ========================")
            print(f"  [{bar_str}] {r['offload_pct']}% offloaded  {goal_icon}")
            print(f"                         {'          80% goal ^' :>40}")
            print(f"")
            fleet_info = f" ({r['fleet_tasks']} fleet-routed)" if r.get('fleet_tasks') else ""
            failover_info = f" ({r['failover_tasks']} failovers)" if r.get('failover_tasks') else ""
            print(f"  Tasks:   {r['local_tasks']} local / {r['claude_tasks']} claude / {r['total_tasks']} total{fleet_info}{failover_info}")
            print(f"  Tokens:  {r['local_tokens']:,} local / {r['claude_tokens']:,} claude ({r['token_savings_pct']}% local)")
            print(f"  Speed:   {r['avg_local_duration']}s avg local / {r['avg_claude_duration']}s avg claude")
            print(f"  Cost:    ${r['claude_cost_usd']:.4f} spent on Claude")
            print(f"  Saved:   ~${r['estimated_savings_usd']:.4f} by using LocalAI")
            print(f"  Activity: {r['today']} today / {r['this_week']} this week")
            print()
        except Exception as e:
            print(f"[error] Offload report failed: {e}", file=sys.stderr)
        return None

    if cmd == "/status":
        try:
            print("\n  AICP Status")
            print("  ===========")

            # GPU info
            try:
                from aicp.core.gpu import detect_gpus
                gpus = detect_gpus()
                for g in gpus:
                    used = g.get("vram_used_mb", 0)
                    total = g.get("vram_total_mb", 0)
                    free = g.get("vram_free_mb", 0)
                    pct = round(used / total * 100) if total else 0
                    print(f"  GPU:       {g.get('name', '?')} — {used}MB/{total}MB ({pct}% used, {free}MB free)")
            except Exception:
                print("  GPU:       unavailable")

            # Loaded model
            try:
                r = httpx.get(f"{base_url}/v1/models", timeout=5.0)
                models_data = r.json().get("data", [])
                loaded = [m.get("id", "?") for m in models_data] if models_data else ["none"]
                print(f"  Model:     {', '.join(loaded)}")
            except Exception:
                print("  Model:     unavailable (LocalAI not reachable)")

            # Routing config
            auto_route = config.get("backends", {}).get("local", {}).get("auto_route", False)
            fleet_route = config.get("cluster", {}).get("auto_route", False)
            print(f"  Routing:   model={'ON' if auto_route else 'OFF'}, fleet={'ON' if fleet_route else 'OFF'}")

            # Offload stats
            try:
                from aicp.core.metrics import offload_report
                r = offload_report(100)
                if r["total_tasks"] > 0:
                    goal_icon = "✓ GOAL MET" if r["goal_met"] else f"→ {80 - r['offload_pct']:.0f}% to go"
                    print(f"  Offload:   {r['offload_pct']}% local ({r['local_tasks']}L/{r['claude_tasks']}C) {goal_icon}")
                    print(f"  Activity:  {r['today']} today / {r['this_week']} this week")
                else:
                    print("  Offload:   no history yet")
            except Exception:
                print("  Offload:   unavailable")

            print()
        except Exception as e:
            print(f"[error] Status check failed: {e}", file=sys.stderr)
        return None

    if cmd == "/route":
        if not arg:
            print("[error] Usage: /route <prompt>", file=sys.stderr)
            return None
        try:
            from aicp.core.router import classify_task_with_reason, recommend_model

            # Build mock backends dict for routing check
            mock_backends = {}
            if backend:
                mock_backends["local"] = backend
            # Check if claude is configured
            try:
                from aicp.backends.claude_code import ClaudeCodeBackend
                claude_cfg = config.get("backends", {}).get("claude", {})
                claude = ClaudeCodeBackend(
                    model=claude_cfg.get("model", "opus"),
                    max_turns=claude_cfg.get("max_turns", 10),
                    timeout=claude_cfg.get("timeout", 300),
                )
                mock_backends["claude"] = claude
            except Exception:
                pass

            backend_choice, reason = classify_task_with_reason(arg, mode, mock_backends, config)
            model_choice = recommend_model(arg, config) or "(default)"

            print(f"\n  Prompt:   {arg[:80]}{'...' if len(arg) > 80 else ''}")
            print(f"  Backend:  {backend_choice}  ({reason})")
            print(f"  Model:    {model_choice}")
            print(f"  Mode:     {mode.value}")
            print()
        except Exception as e:
            print(f"[error] Route check failed: {e}", file=sys.stderr)
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

    if cmd == "/transcribe-detail":
        if not backend:
            print("[error] Transcription requires a LocalAI backend.", file=sys.stderr)
            return None
        parts = arg.split(None, 1) if arg else []
        if not parts:
            print("[error] Usage: /transcribe-detail <audio-path> [language]", file=sys.stderr)
            return None
        audio_path = Path(parts[0])
        language = parts[1].strip() if len(parts) > 1 else ""
        if not audio_path.exists():
            print(f"[error] Audio file not found: {audio_path}", file=sys.stderr)
            return None
        try:
            whisper_model = local_cfg.get("whisper_model", "whisper-1")
            result = backend.transcribe_detailed(
                audio_path, model=whisper_model, language=language,
                timestamp_granularities=["word", "segment"],
            )
            text = result.get("text", "").strip()
            lang = result.get("language", "?")
            duration = result.get("duration", 0)
            print(f"\n  Language: {lang}  Duration: {duration:.1f}s")
            print(f"  Text: {text}\n")
            # Show segments if available
            segments = result.get("segments", [])
            if segments:
                print(f"  Segments ({len(segments)}):")
                for s in segments[:20]:
                    start = s.get("start", 0)
                    end = s.get("end", 0)
                    stxt = s.get("text", "").strip()
                    print(f"    [{start:.1f}s-{end:.1f}s] {stxt}")
                if len(segments) > 20:
                    print(f"    ... and {len(segments) - 20} more")
            # Show words if available
            words = result.get("words", [])
            if words:
                print(f"\n  Words ({len(words)}):")
                shown = words[:30]
                for w in shown:
                    ws = w.get("start", 0)
                    we = w.get("end", 0)
                    wt = w.get("word", "")
                    print(f"    [{ws:.2f}s-{we:.2f}s] {wt}")
                if len(words) > 30:
                    print(f"    ... and {len(words) - 30} more")
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

    if cmd == "/tts":
        if not backend:
            print("[error] TTS requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /tts [voice] [speed] <text>", file=sys.stderr)
            print("  Example: /tts Hello world", file=sys.stderr)
            print("  Example: /tts en-us-amy-low 1.0 Hello world", file=sys.stderr)
            return None
        # Parse optional voice and speed prefix
        parts = arg.split(None, 2)
        voice = ""
        speed = 1.0
        text = arg
        # Heuristic: if first token looks like a voice name (contains '-') and
        # there are more tokens, treat it as voice
        if len(parts) >= 2 and "-" in parts[0]:
            voice = parts[0]
            # Check if second token is a float (speed)
            try:
                speed = float(parts[1])
                text = parts[2] if len(parts) > 2 else ""
            except ValueError:
                text = " ".join(parts[1:])
        try:
            if not text:
                print("[error] No text to speak.", file=sys.stderr)
                return None
            out = Path("/tmp/aicp_tts_output.wav")
            backend.tts(text, out, voice=voice, speed=speed)
            info = f"voice={voice or '(default)'}, speed={speed}"
            size = out.stat().st_size
            print(f"  [TTS saved to {out}] ({size:,} bytes, {info})")
        except Exception as e:
            print(f"[error] TTS failed: {e}", file=sys.stderr)
        return None

    if cmd == "/voices":
        if not backend:
            print("[error] Voices requires a LocalAI backend.", file=sys.stderr)
            return None
        try:
            voices = backend.tts_voices()
            if voices:
                print(f"\n  Available voices ({len(voices)}):")
                for v in voices:
                    print(f"    • {v}")
            else:
                print("  No voice list available (backend may not expose this).")
        except Exception as e:
            print(f"[error] Voices query failed: {e}", file=sys.stderr)
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
            print("  Add --stream for streaming output.", file=sys.stderr)
            return None
        # Check for --stream flag
        stream_flag = False
        clean_arg = arg
        if clean_arg.startswith("--stream "):
            stream_flag = True
            clean_arg = clean_arg[len("--stream "):].strip()
        elif clean_arg.endswith(" --stream"):
            stream_flag = True
            clean_arg = clean_arg[:-(len(" --stream"))].strip()
        try:
            if stream_flag:
                print("\nai> ", end="", flush=True)
                full = ""
                for chunk in backend.execute_with_tools_stream(clean_arg, mode, project_path):
                    print(chunk, end="", flush=True)
                    full += chunk
                print("\n")
                messages.append({"role": "user", "content": f"[tools-stream] {clean_arg}"})
                messages.append({"role": "assistant", "content": full})
            else:
                result = backend.execute_with_native_tools(clean_arg, mode, project_path)
                print(f"\nai> {result}\n")
                messages.append({"role": "user", "content": f"[tools] {clean_arg}"})
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
            # Stream by default in interactive mode
            print("\nai> ", end="", flush=True)
            full = []
            for chunk in backend.complete_stream(arg):
                print(chunk, end="", flush=True)
                full.append(chunk)
            print("\n")
            result = "".join(full)
            messages.append({"role": "user", "content": f"[complete] {arg}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"\n[error] Completion failed: {e}", file=sys.stderr)
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

    if cmd == "/detokenize":
        if not backend:
            print("[error] Detokenize requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /detokenize <id1> <id2> ...", file=sys.stderr)
            return None
        try:
            token_ids = [int(t) for t in arg.split()]
            text = backend.detokenize(token_ids)
            print(f"  Text ({len(token_ids)} tokens): {text}")
        except ValueError:
            print("[error] Token IDs must be integers.", file=sys.stderr)
        except Exception as e:
            print(f"[error] Detokenize failed: {e}", file=sys.stderr)
        return None

    if cmd == "/token-count":
        if not backend:
            print("[error] Token count requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /token-count <text>", file=sys.stderr)
            return None
        try:
            count = backend.token_count(arg)
            print(f"  Token count: {count}")
        except Exception as e:
            print(f"[error] Token count failed: {e}", file=sys.stderr)
        return None

    if cmd == "/vad":
        if not backend:
            print("[error] VAD commands require a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /vad <audio_path>", file=sys.stderr)
            return None
        try:
            segments = backend.vad(Path(arg.strip()))
            if segments:
                for seg in segments:
                    start = seg.get("start", "?")
                    end = seg.get("end", "?")
                    text = seg.get("text", "")
                    print(f"  [{start:.1f}s - {end:.1f}s] {text}")
            else:
                print("  No voice segments detected.")
        except Exception as e:
            print(f"[error] VAD failed: {e}", file=sys.stderr)
        return None

    if cmd == "/detect":
        if not backend:
            print("[error] Detection commands require a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /detect <image_path>", file=sys.stderr)
            return None
        try:
            detections = backend.detect(Path(arg.strip()))
            if detections:
                for det in detections:
                    label = det.get("label", "unknown")
                    conf = det.get("confidence", 0)
                    print(f"  - {label} ({conf:.1%})")
            else:
                print("  No objects detected.")
        except Exception as e:
            print(f"[error] Detection failed: {e}", file=sys.stderr)
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

    if cmd == "/metrics":
        if not backend:
            print("[error] Metrics require a LocalAI backend.", file=sys.stderr)
            return None
        try:
            import json as _json
            status = backend.metrics()
            lai = status.get("localai", {})
            if not lai.get("available"):
                print(f"  LocalAI not reachable", file=sys.stderr)
                return None
            print(f"  Goroutines:  {lai.get('goroutines', '?')}")
            mem = lai.get("memory_alloc_mb")
            if mem is not None:
                print(f"  Memory:      {mem} MiB allocated / {lai.get('memory_sys_mb', '?')} MiB sys")
            models = lai.get("models", [])
            if models:
                print(f"  Models:      {', '.join(models)}")
            api_calls = lai.get("api_calls", {})
            if api_calls:
                print("  API calls:")
                for method in sorted(api_calls):
                    s = api_calls[method]
                    print(f"    {method}: {s.get('count', 0)} calls, avg {s.get('avg_ms', 0)} ms")
            gpu = status.get("gpu", {})
            if gpu.get("available"):
                used = gpu.get("memory_used_mb", 0)
                total = gpu.get("memory_total_mb", 0)
                print(f"  GPU:         {gpu.get('name', '?')} — {used}/{total} MiB, {gpu.get('utilization_pct', '?')}% util, {gpu.get('temperature_c', '?')}°C")
        except Exception as e:
            print(f"[error] Metrics failed: {e}", file=sys.stderr)
        return None

    if cmd == "/batch":
        if not backend:
            print("[error] Batch requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /batch <prompt1> | <prompt2> | ...", file=sys.stderr)
            print("  Run multiple prompts concurrently (pipe-separated).", file=sys.stderr)
            return None
        prompts = [p.strip() for p in arg.split("|") if p.strip()]
        if len(prompts) < 2:
            print("[error] Provide at least 2 prompts separated by |", file=sys.stderr)
            return None
        try:
            print(f"\n  Running {len(prompts)} prompts concurrently...\n")
            results = backend.execute_batch(prompts, mode, project_path)
            for r in results:
                idx = r.get("index", "?")
                prompt = r.get("prompt", "")[:60]
                dur = r.get("duration_ms", 0)
                if r.get("error"):
                    print(f"  [{idx+1}] ERROR ({dur} ms): {r['error']}")
                else:
                    resp = r.get("response", "")
                    print(f"  [{idx+1}] ({dur} ms) {prompt}")
                    print(f"  ai> {resp}\n")
                    messages.append({"role": "user", "content": f"[batch] {prompt}"})
                    messages.append({"role": "assistant", "content": resp})
        except Exception as e:
            print(f"[error] Batch failed: {e}", file=sys.stderr)
        return None

    if cmd == "/infill":
        if not backend:
            print("[error] Infill requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg or "|" not in arg:
            print("[error] Usage: /infill <prefix> | <suffix>", file=sys.stderr)
            print("  Example: /infill def fibonacci(n): | print(fibonacci(10))", file=sys.stderr)
            return None
        parts = arg.split("|", 1)
        prefix = parts[0].strip()
        suffix = parts[1].strip()
        try:
            result = backend.infill(prefix, suffix)
            print(f"\n  {prefix}[bold]{result}[/]{suffix}\n" if False else
                  f"\n  {prefix}\033[1m{result}\033[0m{suffix}\n")
            messages.append({"role": "user", "content": f"[infill] {prefix}⟨…⟩{suffix}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Infill failed: {e}", file=sys.stderr)
        return None

    if cmd == "/embed-image":
        if not backend:
            print("[error] Image embedding requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /embed-image <image_path>", file=sys.stderr)
            return None
        try:
            from pathlib import Path as _Path
            vec = backend.embed_image(_Path(arg.strip()))
            print(f"  Dimensions: {len(vec)}")
            print(f"  First 5:    {vec[:5]}")
            print(f"  Norm:       {sum(x**2 for x in vec)**0.5:.4f}")
        except Exception as e:
            print(f"[error] Image embedding failed: {e}", file=sys.stderr)
        return None

    if cmd == "/lora":
        if not backend:
            print("[error] LoRA commands require a LocalAI backend.", file=sys.stderr)
            return None
        parts = arg.split(None, 2) if arg else []
        subcmd = parts[0] if parts else ""

        if subcmd == "load" and len(parts) >= 3:
            model_name = parts[1]
            adapter_path = parts[2]
            try:
                result = backend.lora_load(model_name, adapter_path)
                print(f"  LoRA adapter loaded: {adapter_path} → {model_name}")
            except Exception as e:
                print(f"[error] LoRA load failed: {e}", file=sys.stderr)
            return None

        if subcmd == "list":
            try:
                models = backend.lora_list()
                if models:
                    for m in models:
                        name = m.get("name", "?")
                        adapter = m.get("lora_adapter", m.get("config", {}).get("lora_adapter", "?"))
                        print(f"  {name} → {adapter}")
                else:
                    print("  No models with LoRA adapters found.")
            except Exception as e:
                print(f"[error] LoRA list failed: {e}", file=sys.stderr)
            return None

        print("[error] Usage: /lora load <model> <adapter_path> | /lora list", file=sys.stderr)
        return None

    if cmd == "/config":
        if not backend:
            print("[error] Config commands require a LocalAI backend.", file=sys.stderr)
            return None
        parts = arg.split(None, 2) if arg else []

        if parts and parts[0] == "set":
            if len(parts) < 3:
                print("[error] Usage: /config set <key> <value>", file=sys.stderr)
                print("  Keys: context_size, gpu_layers, threads, batch_size, f16, mmap", file=sys.stderr)
                return None
            key, raw_val = parts[1], parts[2]
            valid_keys = {"context_size", "gpu_layers", "threads", "batch_size", "f16", "mmap"}
            if key not in valid_keys:
                print(f"[error] Unknown config key '{key}'. Valid: {', '.join(sorted(valid_keys))}", file=sys.stderr)
                return None
            # Parse value
            if key in ("f16", "mmap"):
                val = raw_val.lower() in ("true", "1", "yes")
            else:
                try:
                    val = int(raw_val)
                except ValueError:
                    print(f"[error] '{key}' must be an integer.", file=sys.stderr)
                    return None
            try:
                result = backend.model_config_update(**{key: val})
                print(f"  Config updated: {key} = {val}")
            except Exception as e:
                print(f"[error] Config update failed: {e}", file=sys.stderr)
            return None

        # /config [model_name] — read config
        model_name = parts[0] if parts else None
        try:
            cfg = backend.model_config(model_name)
            # Display key fields
            display_keys = [
                "context_size", "gpu_layers", "threads", "batch_size",
                "f16", "mmap", "backend", "name",
            ]
            print("  Model configuration:")
            for k in display_keys:
                if k in cfg:
                    print(f"    {k}: {cfg[k]}")
            # Show any extra keys not in the display list
            extra = {k: v for k, v in cfg.items() if k not in display_keys and not k.startswith("_")}
            if extra:
                for k, v in sorted(extra.items()):
                    val_str = str(v)
                    if len(val_str) > 80:
                        val_str = val_str[:77] + "..."
                    print(f"    {k}: {val_str}")
        except Exception as e:
            print(f"[error] Config read failed: {e}", file=sys.stderr)
        return None

    if cmd == "/json":
        if not backend:
            print("[error] JSON mode requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /json <prompt>", file=sys.stderr)
            print("  Example: /json List the 3 largest planets as {name, diameter_km}", file=sys.stderr)
            return None
        try:
            result = backend.execute_json(arg, mode, project_path)
            print(f"\n{json.dumps(result, indent=2)}\n")
            messages.append({"role": "user", "content": f"[JSON mode] {arg}"})
            messages.append({"role": "assistant", "content": json.dumps(result)})
        except Exception as e:
            print(f"[error] JSON mode failed: {e}", file=sys.stderr)
        return None

    if cmd == "/seed":
        if not backend:
            print("[error] Seed command requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg or arg.strip().lower() in ("clear", "none", "random"):
            backend.seed = None
            print("  Seed cleared (random inference).")
            return None
        try:
            backend.seed = int(arg.strip())
            print(f"  Seed set to {backend.seed} (reproducible inference).")
        except ValueError:
            print("[error] Seed must be an integer or 'clear'.", file=sys.stderr)
        return None

    if cmd == "/logprobs":
        if not backend:
            print("[error] Logprobs requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /logprobs <prompt>", file=sys.stderr)
            return None
        try:
            result = backend.execute_logprobs(arg, mode, project_path)
            print(f"\n  {result['text']}\n")
            print(f"  Tokens: {len(result['tokens'])}  |  Avg logprob: {result['avg_logprob']}")
            # Show top tokens with their logprobs
            for entry in result["logprobs"][:20]:
                token = entry.get("token", "")
                lp = entry.get("logprob", 0.0)
                top_alts = entry.get("top_logprobs", [])
                alt_str = ""
                if top_alts:
                    alts = [f"{a.get('token', '?')}={a.get('logprob', 0):.3f}" for a in top_alts[:3]]
                    alt_str = f"  alternatives: {', '.join(alts)}"
                print(f"    {repr(token):>15} → {lp:>8.3f}{alt_str}")
            if len(result["logprobs"]) > 20:
                print(f"    ... ({len(result['logprobs']) - 20} more tokens)")
            messages.append({"role": "user", "content": f"[Logprobs] {arg}"})
            messages.append({"role": "assistant", "content": result["text"]})
        except Exception as e:
            print(f"[error] Logprobs failed: {e}", file=sys.stderr)
        return None

    if cmd == "/bestof":
        if not backend:
            print("[error] Best-of-N requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /bestof [N] <prompt>", file=sys.stderr)
            print("  Example: /bestof 5 Write a haiku about coding", file=sys.stderr)
            return None
        # Parse optional leading integer
        parts = arg.split(None, 1)
        try:
            n = int(parts[0])
            prompt_text = parts[1] if len(parts) > 1 else ""
        except ValueError:
            n = 3
            prompt_text = arg
        if not prompt_text:
            print("[error] Usage: /bestof [N] <prompt>", file=sys.stderr)
            return None
        try:
            results = backend.execute_n(prompt_text, mode, project_path, n=n)
            print(f"\n  Generated {len(results)} completions:\n")
            for r in results:
                idx = r["index"] + 1
                text = r["text"]
                # Truncate long responses for display
                display = text[:200] + "..." if len(text) > 200 else text
                print(f"  [{idx}] {display}\n")
            # Use first result as the conversation response
            messages.append({"role": "user", "content": f"[Best-of-{n}] {prompt_text}"})
            messages.append({"role": "assistant", "content": results[0]["text"]})
        except Exception as e:
            print(f"[error] Best-of-N failed: {e}", file=sys.stderr)
        return None

    if cmd == "/chat-image":
        if not backend:
            print("[error] Chat-image requires a LocalAI backend.", file=sys.stderr)
            return None
        parts = arg.split(None, 1) if arg else []
        if len(parts) < 2:
            print("[error] Usage: /chat-image <image_path> <prompt>", file=sys.stderr)
            print("  Images are added to conversation history for multi-turn visual chat.", file=sys.stderr)
            return None
        img_path = Path(parts[0])
        prompt_text = parts[1]
        if not img_path.exists():
            print(f"[error] Image not found: {img_path}", file=sys.stderr)
            return None
        try:
            suffix = img_path.suffix.lower()
            mime_map = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            }
            mime = mime_map.get(suffix, "image/png")
            image_b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
            # Build multimodal message with {img:0} placeholder
            chat_messages = list(messages) + [
                {"role": "user", "content": f"{{img:0}} {prompt_text}"},
            ]
            images = [{"data": image_b64, "mime": mime}]
            result = backend.execute_multimodal(chat_messages, images, mode, project_path)
            print(f"\nai> {result}\n")
            messages.append({"role": "user", "content": f"[Image: {img_path.name}] {prompt_text}"})
            messages.append({"role": "assistant", "content": result})
        except Exception as e:
            print(f"[error] Chat-image failed: {e}", file=sys.stderr)
        return None

    if cmd == "/embed-typed":
        if not backend:
            print("[error] Typed embeddings require a LocalAI backend.", file=sys.stderr)
            return None
        parts = arg.split(None, 1) if arg else []
        if len(parts) < 2:
            print("[error] Usage: /embed-typed <query|document> <text>", file=sys.stderr)
            print("  Short: /embed-typed q <text> or /embed-typed d <text>", file=sys.stderr)
            return None
        type_arg = parts[0].lower()
        text = parts[1]
        type_map = {"q": "query", "query": "query", "d": "document", "document": "document", "doc": "document"}
        embed_type = type_map.get(type_arg)
        if not embed_type:
            print(f"[error] Unknown type '{type_arg}'. Use: query (q) or document (d)", file=sys.stderr)
            return None
        try:
            vec = backend.embed_typed(text, embed_type=embed_type)
            print(f"  Type: {embed_type}")
            print(f"  Dimensions: {len(vec)}")
            print(f"  First 5: {vec[:5]}")
        except Exception as e:
            print(f"[error] Typed embedding failed: {e}", file=sys.stderr)
        return None

    if cmd == "/warmup":
        if not backend:
            print("[error] Warmup requires a LocalAI backend.", file=sys.stderr)
            return None
        model_name = arg.strip() if arg else None
        try:
            print(f"  Warming up {model_name or backend.model}...")
            result = backend.model_warmup(model_name)
            if result.get("already_loaded"):
                print(f"  Already loaded: {result['model']}")
            elif result.get("loaded"):
                print(f"  Loaded: {result['model']} ({result['duration_ms']}ms)")
            else:
                print(f"  Failed to load: {result.get('error', 'unknown')}", file=sys.stderr)
        except Exception as e:
            print(f"[error] Warmup failed: {e}", file=sys.stderr)
        return None

    if cmd == "/loaded":
        if not backend:
            print("[error] Loaded command requires a LocalAI backend.", file=sys.stderr)
            return None
        try:
            models = backend.models_loaded()
            if models:
                print("  Loaded models:")
                for m in models:
                    print(f"    - {m}")
            else:
                print("  No models currently loaded.")
        except Exception as e:
            print(f"[error] Failed to list loaded models: {e}", file=sys.stderr)
        return None

    if cmd == "/complete-lp":
        if not backend:
            print("[error] Complete-lp requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /complete-lp <text to complete>", file=sys.stderr)
            return None
        try:
            result = backend.complete_logprobs(arg)
            print(f"\n  {result['text']}\n")
            print(f"  Tokens: {len(result['tokens'])}  |  Avg logprob: {result['avg_logprob']}")
            for i, (tok, lp) in enumerate(zip(result["tokens"][:20], result["token_logprobs"][:20])):
                lp_val = lp if lp is not None else 0.0
                print(f"    {repr(tok):>15} → {lp_val:>8.3f}")
            if len(result["tokens"]) > 20:
                print(f"    ... ({len(result['tokens']) - 20} more tokens)")
        except Exception as e:
            print(f"[error] Complete-lp failed: {e}", file=sys.stderr)
        return None

    if cmd == "/complete-n":
        if not backend:
            print("[error] Complete-n requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg:
            print("[error] Usage: /complete-n [N] <text to complete>", file=sys.stderr)
            return None
        parts = arg.split(None, 1)
        try:
            n = int(parts[0])
            prompt_text = parts[1] if len(parts) > 1 else ""
        except ValueError:
            n = 3
            prompt_text = arg
        if not prompt_text:
            print("[error] Usage: /complete-n [N] <text to complete>", file=sys.stderr)
            return None
        try:
            results = backend.complete_n(prompt_text, n=n)
            print(f"\n  Generated {len(results)} completions:\n")
            for r in results:
                idx = r["index"] + 1
                text = r["text"]
                display = text[:200] + "..." if len(text) > 200 else text
                print(f"  [{idx}] {display}\n")
        except Exception as e:
            print(f"[error] Complete-n failed: {e}", file=sys.stderr)
        return None

    if cmd == "/similarity":
        if not backend:
            print("[error] Similarity requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg or "|" not in arg:
            print("[error] Usage: /similarity <text1> | <text2>", file=sys.stderr)
            return None
        parts = arg.split("|", 1)
        text1, text2 = parts[0].strip(), parts[1].strip()
        if not text1 or not text2:
            print("[error] Both texts are required.", file=sys.stderr)
            return None
        try:
            vec1 = backend.embed(text1)
            vec2 = backend.embed(text2)
            score = backend.cosine_similarity(vec1, vec2)
            print(f"  Cosine similarity: {score:.4f}")
            print(f"  Dimensions: {len(vec1)}")
        except Exception as e:
            print(f"[error] Similarity failed: {e}", file=sys.stderr)
        return None

    if cmd == "/neighbors":
        if not backend:
            print("[error] Neighbors requires a LocalAI backend.", file=sys.stderr)
            return None
        if not arg or "|" not in arg:
            print("[error] Usage: /neighbors <query> | <doc1> | <doc2> | ...", file=sys.stderr)
            return None
        parts = [p.strip() for p in arg.split("|")]
        query = parts[0]
        docs = [p for p in parts[1:] if p]
        if not query or not docs:
            print("[error] Need a query and at least one document.", file=sys.stderr)
            return None
        try:
            results = backend.nearest_neighbors(query, docs)
            print(f"\n  Query: {query}\n")
            for r in results:
                print(f"    {r['score']:.4f}  {r['text'][:80]}")
        except Exception as e:
            print(f"[error] Neighbors failed: {e}", file=sys.stderr)
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

        # Auto model selection: pick the best local model for this prompt
        turn_model = model
        if config.get("backends", {}).get("local", {}).get("auto_route", False):
            from aicp.core.router import recommend_model, intercept_operation, categorize_operation
            recommended = recommend_model(prompt)
            if recommended and recommended != model:
                turn_model = recommended
                print(f"  [auto-route → {turn_model}]", flush=True)

            # Complexity hint: show when prompt would benefit from Claude
            category = categorize_operation(prompt)
            if category == "complex":
                print("  [hint: complex task — consider `aicp --backend auto` for Claude routing]", flush=True)

            # Zero-token intercept: heartbeats, status checks bypass LLM
            intercepted = intercept_operation(prompt, config)
            if intercepted is not None:
                print(f"\n{intercepted}\n", flush=True)
                messages.append({"role": "user", "content": prompt})
                messages.append({"role": "assistant", "content": intercepted})
                try:
                    from aicp.core.history import save_task
                    save_task(
                        prompt=prompt, mode=mode.value, backend="local",
                        project=str(project_path), response=intercepted,
                        duration_seconds=0.0, model="intercept",
                        route="intercepted",
                    )
                except Exception:
                    pass
                continue

        messages.append({"role": "user", "content": prompt})

        _turn_start = __import__("time").perf_counter()
        try:
            if stream:
                content = _stream_turn(base_url, turn_model, messages, max_tokens)
            else:
                content = _blocking_turn(base_url, turn_model, messages, max_tokens)

            if content is None:
                messages.pop()
                continue

            messages.append({"role": "assistant", "content": content})

            # Record in history for offload tracking
            _turn_elapsed = __import__("time").perf_counter() - _turn_start
            try:
                from aicp.core.history import save_task
                save_task(
                    prompt=display_prompt,
                    mode=mode.value,
                    backend="local",
                    project=str(project_path),
                    response=content,
                    duration_seconds=_turn_elapsed,
                    model=turn_model,
                    route="interactive",
                )
            except Exception:
                pass  # Never block the chat loop

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
