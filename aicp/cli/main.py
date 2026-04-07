"""AICP command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from aicp import __version__
from aicp.backends.base import Backend
from aicp.cli.display import (
    console, print_check_header, print_error, print_history_entry,
    print_response, print_status, print_warning, spinner,
)
from aicp.config.loader import load_config, validate_config, get_backend_config
from aicp.core.history import list_tasks, get_task
from aicp.core.modes import Mode
from aicp.core.controller import Controller, Task
from aicp.backends.localai import LocalAIBackend
from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.backends.openrouter import OpenRouterBackend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicp",
        description="AI Control Platform — orchestrate AI backends under your control.",
    )
    parser.add_argument("prompt", nargs="?", help="Task prompt")
    parser.add_argument(
        "--mode", "-m",
        choices=["think", "edit", "act"],
        default=os.environ.get("AICP_DEFAULT_MODE", "think"),
        help="Permission mode (default: think, env: AICP_DEFAULT_MODE)",
    )
    parser.add_argument(
        "--backend", "-b",
        choices=["local", "claude", "auto"],
        default=os.environ.get("AICP_DEFAULT_BACKEND", "local"),
        help="AI backend (default: local, auto=smart routing, env: AICP_DEFAULT_BACKEND)",
    )
    parser.add_argument(
        "--project", "-d",
        type=Path,
        default=Path(os.environ.get("AICP_PROJECT_PATH", ".")),
        help="Project directory (default: cwd, env: AICP_PROJECT_PATH)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file path (default: config/default.yaml)",
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help="Configuration profile (e.g. default, fast, offline). See: aicp --profile-cmd list",
    )
    parser.add_argument(
        "--profile-cmd",
        metavar="CMD",
        help="Profile commands: list, show <name>, diff <a> <b>, validate, use <name>",
    )
    parser.add_argument(
        "--profile-arg",
        metavar="ARG",
        help="Second argument for --profile-cmd (e.g. second profile name for diff)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check config validity and backend availability, then exit",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        const=20,
        type=int,
        metavar="N",
        help="Show recent task history (default: last 20)",
    )
    parser.add_argument(
        "--replay",
        metavar="ID",
        help="Replay full output from a previous task by ID",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregated task metrics (tokens, cost, latency)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Live dashboard: GPU status, LocalAI, metrics (Ctrl+C to exit)",
    )
    parser.add_argument(
        "--auto-config",
        action="store_true",
        help="Auto-detect GPUs and generate optimal model configs",
    )
    parser.add_argument(
        "--models",
        nargs="?",
        const="list",
        metavar="COMMAND",
        help="Model management: list, gallery, install, job, unload, monitor, info, download, activate, benchmark",
    )
    parser.add_argument(
        "--models-arg",
        metavar="NAME",
        help="Model name for --models info",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start interactive chat session (LocalAI only)",
    )
    parser.add_argument(
        "--continue-session", "-c",
        action="store_true",
        help="Continue most recent Claude Code session in this directory",
    )
    parser.add_argument(
        "--resume", "-r",
        metavar="SESSION",
        help="Resume a Claude Code session by name or ID",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream response in real-time (Claude Code only)",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        help="Effort level for Claude Code (default: derived from mode)",
    )
    parser.add_argument(
        "--schema",
        metavar="FILE",
        help="JSON Schema file for structured output (Claude Code only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Force JSON output from LocalAI (response_format: json_object)",
    )
    parser.add_argument(
        "--tools",
        action="store_true",
        help="Enable function calling with built-in tools (file_read, grep, shell)",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Use raw text completion (/v1/completions) instead of chat — no chat template overhead",
    )
    parser.add_argument(
        "--sound",
        metavar="PROMPT",
        help="Generate sound/music from a text description (e.g. 'a gentle piano melody')",
    )
    parser.add_argument(
        "--agent",
        nargs="?",
        const="9100",
        metavar="PORT",
        help="Start AICP agent daemon (default port: 9100)",
    )
    parser.add_argument(
        "--agent-token",
        metavar="TOKEN",
        help="Auth token for agent daemon",
    )
    parser.add_argument(
        "--approval",
        action="store_true",
        help="Semi-auto: generate plan first, execute on approval",
    )
    parser.add_argument(
        "--pipeline",
        metavar="FILE",
        type=Path,
        help="Run a multi-step pipeline from a YAML file",
    )
    # Control plane
    parser.add_argument(
        "--control",
        nargs="?",
        const="overview",
        metavar="PROJECT",
        help="Control plane: overview (default) or deep dive into a project",
    )
    # Skill system
    parser.add_argument(
        "--skill",
        metavar="CMD",
        help="Skill commands: list, run <name>, create <name>, export <name>",
    )
    parser.add_argument(
        "--skill-name",
        metavar="NAME",
        help="Skill name (for run, create, export)",
    )
    parser.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Skill parameter (repeatable: --param name=foo --param desc=bar)",
    )
    # Project management
    parser.add_argument(
        "--project-cmd",
        metavar="CMD",
        help="Project commands: register, list, status, plan, assess",
    )
    parser.add_argument(
        "--project-name",
        metavar="NAME",
        help="Project name (for register)",
    )
    parser.add_argument(
        "--project-desc",
        metavar="DESC",
        help="Project description (for register)",
    )
    # Session continuity (LocalAI single-shot conversation history)
    parser.add_argument(
        "--session",
        metavar="NAME",
        help="Named conversation session: persist history across single-shot calls (LocalAI only)",
    )
    parser.add_argument(
        "--session-list",
        action="store_true",
        help="List all saved conversation sessions",
    )
    parser.add_argument(
        "--session-delete",
        metavar="NAME",
        help="Delete a saved conversation session",
    )
    # Router debug
    parser.add_argument(
        "--router-debug",
        action="store_true",
        help="Show routing decision breakdown (why a backend was chosen)",
    )
    # Knowledge base / RAG
    parser.add_argument(
        "--kb",
        metavar="CMD",
        help="Knowledge base: add <file/dir>, search <query>, list, status, delete <source>",
    )
    parser.add_argument(
        "--kb-arg",
        metavar="ARG",
        help="Argument for --kb command (file path, query, or source name)",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Augment prompt with RAG context from the knowledge base",
    )
    parser.add_argument(
        "--vision",
        metavar="IMAGE",
        help="Send an image to the vision model (path to image file)",
    )
    # Audio
    parser.add_argument(
        "--transcribe",
        metavar="AUDIO",
        help="Transcribe an audio file (wav, mp3, ogg, flac) using whisper",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Speak the LLM response using TTS (generates WAV file)",
    )
    parser.add_argument(
        "--speak-output",
        metavar="FILE",
        help="Output path for --speak (default: /tmp/aicp_tts.wav)",
    )
    # Voice pipeline
    parser.add_argument(
        "--voice-pipeline",
        metavar="AUDIO",
        help="Voice pipeline: audio in → transcribe → LLM → TTS → audio out",
    )
    parser.add_argument(
        "--voice-output",
        metavar="FILE",
        help="Output path for --voice-pipeline (default: /tmp/aicp_voice_response.wav)",
    )
    # Image generation
    parser.add_argument(
        "--imagine",
        metavar="PROMPT",
        help="Generate an image from a text prompt using Stable Diffusion",
    )
    parser.add_argument(
        "--imagine-output",
        metavar="FILE",
        help="Output path for --imagine (default: /tmp/aicp_imagine.png)",
    )
    parser.add_argument(
        "--imagine-size",
        metavar="WxH",
        default="512x512",
        help="Image size for --imagine (default: 512x512)",
    )
    # Grammar-constrained generation
    parser.add_argument(
        "--grammar",
        metavar="GRAMMAR",
        help="GBNF grammar to constrain output format (e.g. 'root ::= (\"yes\" | \"no\")')",
    )
    parser.add_argument(
        "--grammar-file",
        metavar="FILE",
        type=Path,
        help="Load GBNF grammar from a file",
    )
    # MCP server
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Start AICP as an MCP server (stdio transport, for Claude Code integration)",
    )
    # Observability
    parser.add_argument(
        "--observe",
        action="store_true",
        help="Show live system status: GPU, LocalAI metrics, model info",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Run a quick benchmark: measure TTFT, tokens/sec, latency",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate all AICP features: config, models, endpoints, tools",
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Show all AICP capabilities: endpoints, tools, slash commands, models",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Show live Prometheus metrics, GPU status, and API call stats",
    )
    parser.add_argument(
        "--offload",
        action="store_true",
        help="Show LocalAI offload dashboard — progress toward 80%% Claude reduction",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show system status (GPU, model, routing, offload progress)",
    )
    parser.add_argument("--version", "-v", action="version", version=f"aicp {__version__}")
    return parser


def _build_backends(config: Dict) -> Dict[str, Backend]:
    """Instantiate backends from config."""
    local_cfg = get_backend_config(config, "local")
    claude_cfg = get_backend_config(config, "claude")
    timeouts_cfg = config.get("timeouts", {})
    return {
        "local": LocalAIBackend(
            base_url=local_cfg.get("base_url", "http://localhost:8090"),
            model=local_cfg.get("model", "default"),
            max_tokens=local_cfg.get("max_tokens", 2048),
            api_key=local_cfg.get("api_key", ""),
            temperature=local_cfg.get("temperature"),
            top_p=local_cfg.get("top_p"),
            top_k=local_cfg.get("top_k"),
            repeat_penalty=local_cfg.get("repeat_penalty"),
            embedding_model=local_cfg.get("embedding_model", ""),
            code_model=local_cfg.get("code_model", ""),
            vision_model=local_cfg.get("vision_model", ""),
            auto_route=local_cfg.get("auto_route", False),
            cache_prompt=local_cfg.get("cache_prompt", True),
            # Specialized model overrides
            reranker_model=local_cfg.get("reranker_model", ""),
            image_model=local_cfg.get("image_model", ""),
            sound_model=local_cfg.get("sound_model", ""),
            whisper_model=local_cfg.get("whisper_model", ""),
            tts_model=local_cfg.get("tts_model", ""),
            # Advanced sampling
            mirostat=local_cfg.get("mirostat"),
            mirostat_tau=local_cfg.get("mirostat_tau"),
            mirostat_eta=local_cfg.get("mirostat_eta"),
            typical_p=local_cfg.get("typical_p"),
            frequency_penalty=local_cfg.get("frequency_penalty"),
            presence_penalty=local_cfg.get("presence_penalty"),
            mode_profiles=local_cfg.get("mode_profiles"),
            # Timeouts and retries (profile-configurable)
            request_timeout=timeouts_cfg.get("request"),
            cold_start_timeout=timeouts_cfg.get("cold_start"),
            cold_start_interval=timeouts_cfg.get("cold_start_interval"),
            max_retries=timeouts_cfg.get("retries"),
        ),
        "claude": ClaudeCodeBackend(
            model=claude_cfg.get("model", "opus"),
            max_turns=claude_cfg.get("max_turns", 10),
            max_budget_usd=claude_cfg.get("max_budget_usd"),
            timeout=claude_cfg.get("timeout", 300),
        ),
    }

    # OpenRouter: optional middle-tier backend (needs OPENROUTER_API_KEY)
    import os
    or_cfg = get_backend_config(config, "openrouter")
    or_key = os.environ.get("OPENROUTER_API_KEY", or_cfg.get("api_key", ""))
    if or_key:
        backends["openrouter"] = OpenRouterBackend(
            api_key=or_key,
            model=or_cfg.get("model", ""),
            free_model=or_cfg.get("free_model", ""),
            max_tokens=or_cfg.get("max_tokens", 4096),
            timeout=or_cfg.get("timeout", 120),
            free_only=or_cfg.get("free_only", False),
        )

    return backends


def _run_profile_cmd(cmd: str, profile_name: Optional[str], profile_arg: Optional[str]) -> int:
    """Handle --profile-cmd subcommands."""
    from aicp.core.profiles import (
        PROFILES_DIR,
        diff_profiles,
        get_active_profile,
        list_profiles,
        load_profile,
        resolve_profile,
        validate_profile,
    )

    if cmd == "list":
        profiles = list_profiles()
        active = profile_name or get_active_profile()
        if not profiles:
            print("No profiles found in", PROFILES_DIR)
            return 1
        print(f"{'Name':<20} {'Description':<50} {'Active'}")
        print("-" * 78)
        for p in profiles:
            marker = " *" if p["name"] == active else ""
            print(f"{p['name']:<20} {p['description']:<50}{marker}")
        if active:
            print(f"\nActive profile: {active}")
        return 0

    if cmd == "show":
        name = profile_name or profile_arg or get_active_profile() or "default"
        try:
            import yaml
            overlay = resolve_profile(name)
            print(f"# Resolved profile: {name}")
            print(yaml.dump(overlay, default_flow_style=False, sort_keys=False))
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return 1
        return 0

    if cmd == "diff":
        name_a = profile_name or "default"
        name_b = profile_arg or "fast"
        try:
            diffs = diff_profiles(name_a, name_b)
            if not diffs:
                print(f"Profiles '{name_a}' and '{name_b}' are identical.")
                return 0
            print(f"{'Section':<20} {name_a:<30} {name_b}")
            print("-" * 78)
            for key, sides in diffs.items():
                a_val = str(sides["a"])[:28] if sides["a"] is not None else "(not set)"
                b_val = str(sides["b"])[:28] if sides["b"] is not None else "(not set)"
                print(f"{key:<20} {a_val:<30} {b_val}")
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return 1
        return 0

    if cmd == "validate":
        profiles = list_profiles()
        if not profiles:
            print("No profiles found.")
            return 1
        all_valid = True
        for p in profiles:
            try:
                profile = load_profile(p["name"])
                errors = validate_profile(profile)
                # Also check merged config
                config = load_config(profile=p["name"])
                config_errors = validate_config(config)
                if errors or config_errors:
                    print(f"  FAIL  {p['name']}: {errors + config_errors}")
                    all_valid = False
                else:
                    print(f"  OK    {p['name']}")
            except Exception as e:
                print(f"  FAIL  {p['name']}: {e}")
                all_valid = False
        return 0 if all_valid else 1

    if cmd == "use":
        name = profile_name or profile_arg
        if not name:
            print_error("Usage: aicp --profile-cmd use --profile <name>")
            return 1
        # Validate profile exists and is valid
        try:
            load_profile(name)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return 1
        # Resolve profile to get docker settings
        try:
            overlay = resolve_profile(name)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return 1

        # Map docker profile settings to .env variables
        docker_cfg = overlay.get("docker", {})
        env_updates = {"AICP_PROFILE": name}
        if "context_size" in docker_cfg:
            env_updates["CONTEXT_SIZE"] = str(docker_cfg["context_size"])
        if "threads" in docker_cfg:
            env_updates["THREADS"] = str(docker_cfg["threads"])
        if "parallel_slots" in docker_cfg:
            env_updates["LLAMACPP_PARALLEL"] = str(docker_cfg["parallel_slots"])
        if "mem_limit" in docker_cfg:
            env_updates["DOCKER_MEM_LIMIT"] = str(docker_cfg["mem_limit"])

        # Update .env file (preserve existing lines, update/add profile vars)
        env_path = Path(__file__).parent.parent.parent / ".env"
        lines = []
        written_keys: set = set()
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    key = line.strip().split("=", 1)[0] if "=" in line and not line.strip().startswith("#") else None
                    if key and key in env_updates:
                        lines.append(f"{key}={env_updates[key]}\n")
                        written_keys.add(key)
                    else:
                        lines.append(line)
        # Append any new keys not already in .env
        for key, val in env_updates.items():
            if key not in written_keys:
                lines.append(f"{key}={val}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)

        print(f"Active profile set to: {name}")
        if docker_cfg:
            docker_changes = {k: v for k, v in env_updates.items() if k != "AICP_PROFILE"}
            if docker_changes:
                print(f"Docker env updated: {', '.join(f'{k}={v}' for k, v in docker_changes.items())}")
                print("Run 'docker compose restart localai' to apply Docker changes.")
        return 0

    print_error(f"Unknown profile command: {cmd}")
    print("Available: list, show, diff, validate, use")
    return 1


def _run_check(config: Dict, backends: Dict[str, Backend]) -> int:
    """Validate config and check backend availability."""
    from aicp.core.gpu import detect_gpus

    print_check_header()

    errors = validate_config(config)
    if errors:
        console.print("  Config: [bold red]INVALID[/]")
        for err in errors:
            console.print(f"    - {err}")
        return 1
    else:
        console.print("  Config: [bold green]OK[/]")

    # GPU status
    gpus = detect_gpus()
    console.print()
    if gpus:
        for g in gpus:
            pct = g.vram_used_mb / g.vram_total_mb * 100 if g.vram_total_mb > 0 else 0
            color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
            console.print(
                f"  [bold]GPU {g.index}[/] {g.name}: "
                f"[{color}]{g.vram_free_mb}/{g.vram_total_mb} MiB free[/] "
                f"(driver {g.driver_version})"
            )

        # Verify GPU passthrough to Docker (required for LocalAI to use GPU)
        import subprocess as _sp
        try:
            result = _sp.run(
                ["docker", "run", "--rm", "--gpus", "all",
                 "ubuntu:22.04", "nvidia-smi", "-L"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                console.print("  [bold]Docker GPU passthrough:[/] [green]OK[/]")
            else:
                console.print(
                    "  [bold]Docker GPU passthrough:[/] [yellow]FAIL[/] "
                    "— LocalAI will run on CPU"
                )
                console.print(
                    "  [dim]Fix: install NVIDIA Container Toolkit — "
                    "see SETUP.md prerequisites[/]"
                )
                all_ok = False
        except (_sp.TimeoutExpired, FileNotFoundError):
            console.print("  [bold]Docker GPU passthrough:[/] [dim]skipped (Docker not available)[/]")
        except Exception:
            pass
    else:
        console.print("  [yellow]No GPUs detected[/]")

    console.print()
    all_ok = True
    for name, backend in backends.items():
        detail = backend.status_detail()
        ok = backend.is_available()
        print_status(name, detail, ok)
        if not ok:
            all_ok = False

    # Health & readiness probes
    local_backend = backends.get("local")
    if local_backend and isinstance(local_backend, LocalAIBackend):
        health = local_backend.health_check()
        ready = local_backend.is_ready()
        if health.get("healthy"):
            console.print(f"  Health:  [green]healthy[/]")
        else:
            err = health.get("error", "unhealthy")
            console.print(f"  Health:  [red]{err}[/]")
        if ready:
            console.print(f"  Ready:   [green]ready[/]")
        else:
            console.print(f"  Ready:   [yellow]not ready (model may be loading)[/]")

    # Warn if configured LocalAI model is not actually loaded
    if local_backend and local_backend.is_available():
        try:
            import httpx as _httpx
            resp = _httpx.get(f"{local_backend.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                loaded = [m.get("id", "") for m in resp.json().get("data", [])]
                if loaded and local_backend.model not in loaded:
                    console.print(
                        f"\n  [yellow]WARNING: configured model '{local_backend.model}' "
                        f"not found in LocalAI. Loaded: {', '.join(loaded)}[/]"
                    )
                    console.print("  [dim]Place a .gguf file in models/ matching the model name.[/]")
                elif not loaded:
                    console.print(
                        "\n  [yellow]WARNING: LocalAI is running but has no models loaded.[/]"
                    )
                    console.print("  [dim]Download a .gguf model into models/ then restart with: make local-down && make local-up[/]")
        except Exception:
            pass

    # Cluster nodes
    from aicp.core.cluster import load_cluster_config, check_cluster
    from aicp.core.controller import _local_ips
    nodes = load_cluster_config(config)
    if nodes:
        console.print()
        console.print("  [bold]Cluster nodes:[/]")
        local_ips = _local_ips()
        check_cluster(nodes)
        for n in nodes:
            is_self = n.host in local_ips or n.name.lower() == __import__("socket").gethostname().lower()
            if n.online:
                status = "[green]ONLINE[/]"
            elif is_self:
                status = "[yellow]LOCAL[/] [dim](agent daemon not running)[/]"
            else:
                status = "[red]OFFLINE[/]"
            gpu_info = ""
            if n.gpus:
                total_free = sum(g.get("vram_free_mb", 0) for g in n.gpus)
                gpu_info = f", {len(n.gpus)} GPUs, {total_free} MiB free"
            model_names = ", ".join(m.get("name", "?") for m in n.models) if n.models else "none"
            console.print(f"    {status} {n.name} ({n.host}:{n.port}{gpu_info}, models: {model_names})")
            if not n.online and not is_self:
                all_ok = False

    # Routing config
    cluster_cfg = config.get("cluster", {})
    local_cfg = config.get("backends", {}).get("local", {})
    console.print()
    console.print("  [bold]Routing:[/]")
    fleet_route = cluster_cfg.get("auto_route", False)
    model_route = local_cfg.get("auto_route", False)
    console.print(f"    Fleet auto-route:  {'[green]ON[/]' if fleet_route else '[dim]OFF[/]'}")
    console.print(f"    Model auto-route:  {'[green]ON[/]' if model_route else '[dim]OFF[/]'}")
    if fleet_route:
        console.print("    Failover chain:    local → fleet peer → openrouter → Claude")
    if model_route:
        console.print("    Model selection:   qwen3-4b (fleet) / qwen3-8b (code) / qwen3-8b-fast (simple)")

    # KB collection check
    if local_backend and local_backend.is_available():
        try:
            import httpx as _httpx
            kb_resp = _httpx.get(
                f"{local_backend.base_url}/api/agents/collections/aicp-kb/entries",
                timeout=3.0,
            )
            if kb_resp.status_code == 200:
                entry_count = kb_resp.json().get("count", 0)
                if entry_count > 0:
                    console.print(f"    KB collection:     [green]{entry_count} entries[/] (aicp-kb)")
                else:
                    console.print("    KB collection:     [yellow]EMPTY[/] — run: make kb-sync")
            else:
                console.print("    KB collection:     [yellow]NOT FOUND[/] — run: make kb-sync")
        except Exception:
            pass

    # Offload summary (if history exists)
    try:
        from aicp.core.metrics import offload_report
        r = offload_report(500)
        if r["total_tasks"] > 0:
            console.print()
            console.print("  [bold]Offload:[/]")
            pct = r["offload_pct"]
            color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
            console.print(f"    [{color}]{pct}% offloaded[/] ({r['local_tasks']} local / {r['claude_tasks']} claude)")
            console.print(f"    Target: 80% — {'[green]GOAL MET[/]' if r['goal_met'] else '[yellow]in progress[/]'}")
    except Exception:
        pass

    console.print()
    if all_ok:
        console.print("  [bold green]All systems ready.[/]")
    else:
        console.print("  [yellow]Some backends or nodes are unavailable.[/]")

    return 0


def _run_self_test() -> int:
    """Validate all AICP features against a live LocalAI instance."""
    import httpx as _httpx

    local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
    console.print("[bold]AICP Self-Test[/]\n")
    passed = 0
    failed = 0
    skipped = 0

    def _probe(label: str, fn) -> None:
        nonlocal passed, failed, skipped
        try:
            result = fn()
            if result is None:
                console.print(f"  [yellow]SKIP[/]  {label}")
                skipped += 1
            else:
                console.print(f"  [green]PASS[/]  {label}")
                passed += 1
        except Exception as exc:
            console.print(f"  [red]FAIL[/]  {label}: {exc}")
            failed += 1

    _st_backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")

    # 1a. Health check
    def _check_health():
        h = _st_backend.health_check()
        if not h.get("healthy"):
            raise RuntimeError(h.get("error", "unhealthy"))
        return True
    _probe("Health check (/healthz)", _check_health)

    # 1b. Readiness check
    def _check_ready():
        if not _st_backend.is_ready():
            raise RuntimeError("not ready")
        return True
    _probe("Readiness check (/readyz)", _check_ready)

    # 1c. API reachable
    def _check_api():
        resp = _httpx.get(f"{local_url}/v1/models", timeout=5.0)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        if not models:
            raise RuntimeError("no models loaded")
        return models
    _probe("LocalAI API reachable", _check_api)

    # 2. Chat completions
    def _check_chat():
        resp = _httpx.post(f"{local_url}/v1/chat/completions", json={
            "model": "hermes", "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 8,
        }, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    _probe("Chat completions (/v1/chat/completions)", _check_chat)

    # 3. Raw completions
    def _check_completions():
        resp = _httpx.post(f"{local_url}/v1/completions", json={
            "model": "hermes", "prompt": "Hello", "max_tokens": 8,
        }, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["text"]
    _probe("Raw completions (/v1/completions)", _check_completions)

    # 4. Embeddings
    def _check_embed():
        resp = _httpx.post(f"{local_url}/v1/embeddings", json={
            "model": "nomic-embed", "input": "test",
        }, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()["data"][0]["embedding"]
        if len(data) < 10:
            raise RuntimeError(f"embedding too short: {len(data)}")
        return len(data)
    _probe("Embeddings (/v1/embeddings)", _check_embed)

    # 5. Tokenize
    def _check_tokenize():
        resp = _httpx.post(f"{local_url}/v1/tokenize", json={
            "model": "hermes", "content": "Hello world",
        }, timeout=10.0)
        resp.raise_for_status()
        tokens = resp.json().get("tokens", [])
        if not tokens:
            raise RuntimeError("empty token list")
        return len(tokens)
    _probe("Tokenization (/v1/tokenize)", _check_tokenize)

    # 6. Edits
    def _check_edits():
        resp = _httpx.post(f"{local_url}/v1/edits", json={
            "model": "hermes", "input": "Ths is a tset",
            "instruction": "Fix spelling", "max_tokens": 32,
        }, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["text"]
    _probe("Text edits (/v1/edits)", _check_edits)

    # 7. Models list
    def _check_models():
        resp = _httpx.get(f"{local_url}/v1/models", timeout=5.0)
        resp.raise_for_status()
        return len(resp.json().get("data", []))
    _probe("Model listing (/v1/models)", _check_models)

    # 8. Model gallery
    def _check_gallery():
        resp = _httpx.get(f"{local_url}/models/available", timeout=10.0)
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            raise RuntimeError("unexpected response format")
        return len(items)
    _probe("Model gallery (/models/available)", _check_gallery)

    # 9. Backend monitor
    def _check_monitor():
        resp = _httpx.post(f"{local_url}/backend/monitor", json={
            "model": "hermes",
        }, timeout=10.0)
        if resp.status_code == 404:
            return None  # skip — older LocalAI
        resp.raise_for_status()
        return resp.json()
    _probe("Backend monitor (/backend/monitor)", _check_monitor)

    # 10. Stores API
    def _check_stores():
        # Set a test vector, then delete it
        test_key = [[0.1] * 32]
        test_val = ["__aicp_self_test__"]
        resp = _httpx.post(f"{local_url}/stores/set", json={
            "store": "__selftest__", "keys": test_key, "values": test_val,
        }, timeout=10.0)
        if resp.status_code == 404:
            return None  # stores not available
        resp.raise_for_status()
        # Clean up
        _httpx.post(f"{local_url}/stores/delete", json={
            "store": "__selftest__", "keys": test_key,
        }, timeout=5.0)
        return True
    _probe("Stores API (/stores/*)", _check_stores)

    # 11. P2P (optional — skip if not enabled)
    def _check_p2p():
        resp = _httpx.get(f"{local_url}/api/p2p/stats", timeout=5.0)
        if resp.status_code in (404, 501):
            return None  # P2P not enabled
        resp.raise_for_status()
        return resp.json()
    _probe("P2P cluster (/api/p2p/stats)", _check_p2p)

    # 12. Reranking
    def _check_rerank():
        resp = _httpx.post(f"{local_url}/v1/reranking", json={
            "model": "bge-reranker-v2-m3",
            "query": "test query",
            "documents": ["doc one", "doc two"],
            "top_n": 2,
        }, timeout=30.0)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    _probe("Reranking (/v1/reranking)", _check_rerank)

    # 13. Backends list
    def _check_backends_list():
        bl = _st_backend.backends_list()
        if not bl:
            return None  # endpoint may not exist
        return len(bl)
    _probe("Backends list (/api/backends)", _check_backends_list)

    # 14. Feature detection
    def _check_features():
        srv = _st_backend.server_config()
        return srv.get("features", []) or True
    _probe("Feature detection (server_config)", _check_features)

    # 17. VAD endpoint
    def _check_vad():
        resp = _httpx.post(f"{local_url}/v1/audio/vad", data={}, timeout=5.0)
        if resp.status_code == 404:
            return None
        return True
    _probe("Voice activity detection (/v1/audio/vad)", _check_vad)

    # 18. Object detection endpoint
    def _check_detection():
        resp = _httpx.post(f"{local_url}/v1/detection", data={}, timeout=5.0)
        if resp.status_code == 404:
            return None
        return True
    _probe("Object detection (/v1/detection)", _check_detection)

    # 19. Config completeness
    def _check_config():
        from aicp.config.loader import load_config
        cfg = load_config()
        local_cfg = cfg.get("backends", {}).get("local", {})
        required = ["base_url", "model", "embedding_model", "code_model",
                     "vision_model", "whisper_model", "tts_model", "image_model",
                     "reranker_model", "sound_model"]
        missing = [k for k in required if not local_cfg.get(k)]
        if missing:
            raise RuntimeError(f"missing config keys: {', '.join(missing)}")
        return len(required)
    _probe("Config completeness (all model keys)", _check_config)

    # 20. Python imports (all modules)
    def _check_imports():
        import importlib
        modules = [
            "aicp.backends.localai", "aicp.backends.claude_code",
            "aicp.core.tools", "aicp.core.stores", "aicp.core.modes",
            "aicp.core.context", "aicp.core.history", "aicp.core.observability",
            "aicp.guardrails.checks", "aicp.config.loader",
            "aicp.mcp.server", "aicp.cli.interactive",
        ]
        for mod in modules:
            importlib.import_module(mod)
        return len(modules)
    _probe("Python module imports", _check_imports)

    # 21. MCP tool count (count aicp_* functions in server module)
    def _check_mcp_tools():
        import aicp.mcp.server as srv
        tool_fns = [n for n in dir(srv) if n.startswith("aicp_") and callable(getattr(srv, n))]
        count = len(tool_fns)
        if count < 30:
            raise RuntimeError(f"expected ≥30 MCP tools, found {count}")
        return count
    _probe(f"MCP tool registry (≥30 tools)", _check_mcp_tools)

    # 22. Fleet routing
    def _check_fleet_routing():
        from aicp.core.router import classify_task_with_reason, recommend_model
        from aicp.core.modes import Mode as _Mode

        # Use a minimal mock to avoid HTTP calls in the probe
        class _MockBe:
            def is_available(self):
                return True
        backend_name, reason = classify_task_with_reason(
            "heartbeat", _Mode.THINK, {"local": _MockBe()}, {}
        )
        if backend_name != "local":
            raise RuntimeError(f"heartbeat should route to local, got {backend_name}")
        model = recommend_model("heartbeat")
        if model != "hermes-3b":
            raise RuntimeError(f"heartbeat should use hermes-3b, got {model}")
        return f"backend={backend_name}, model={model}"
    _probe("Fleet routing (classify + model selection)", _check_fleet_routing)

    # 23. Fleet node connectivity
    def _check_fleet_nodes():
        from aicp.core.cluster import load_fleet_config, check_cluster
        nodes = load_fleet_config()
        if not nodes:
            return None  # no fleet configured
        nodes = check_cluster(nodes)
        online = sum(1 for n in nodes if n.online)
        return f"{online}/{len(nodes)} online"
    _probe("Fleet nodes (connectivity)", _check_fleet_nodes)

    # 24. Offload metrics
    def _check_offload():
        from aicp.core.metrics import offload_report
        r = offload_report(100)
        if r["total_tasks"] == 0:
            return None  # no history yet
        return f"{r['offload_pct']}% offloaded ({r['local_tasks']}L/{r['claude_tasks']}C)"
    _probe("Offload metrics (history)", _check_offload)

    # Summary
    console.print()
    total = passed + failed + skipped
    console.print(f"[bold]Results:[/] {passed}/{total} passed", end="")
    if skipped:
        console.print(f", {skipped} skipped", end="")
    if failed:
        console.print(f", [red]{failed} failed[/]")
    else:
        console.print()
    console.print()

    return 1 if failed else 0


def _run_capabilities() -> int:
    """Show all AICP capabilities."""
    from rich.table import Table
    from rich.panel import Panel

    console.print("[bold]AICP Capabilities Report[/]\n")

    # ── LocalAI Endpoints ────────────────────────────────────────────────
    endpoints = [
        ("POST", "/v1/chat/completions", "Chat (+ streaming, tools, grammar, JSON)"),
        ("POST", "/v1/completions", "Raw text completion (+ streaming)"),
        ("POST", "/v1/embeddings", "Text embeddings (single + batch)"),
        ("POST", "/v1/audio/transcriptions", "Speech-to-text (Whisper)"),
        ("POST", "/v1/audio/speech", "Text-to-speech (Piper)"),
        ("POST", "/v1/audio/vad", "Voice activity detection"),
        ("POST", "/v1/sound-generation", "Sound/music generation"),
        ("POST", "/v1/images/generations", "Image generation (Stable Diffusion)"),
        ("POST", "/v1/edits", "Text editing by instruction"),
        ("POST", "/v1/tokenize", "Tokenization (single + batch)"),
        ("POST", "/v1/reranking", "Cross-encoder reranking"),
        ("POST", "/v1/detection", "Object detection"),
        ("GET",  "/v1/models", "Model listing"),
        ("GET",  "/models/available", "Model gallery"),
        ("POST", "/models/apply", "Model install"),
        ("GET",  "/models/jobs/{uuid}", "Job tracking"),
        ("POST", "/api/models/delete", "Model delete"),
        ("POST", "/backend/shutdown", "Unload model from GPU"),
        ("POST", "/backend/monitor", "Backend state + memory"),
        ("GET",  "/api/backends", "List installed backends"),
        ("POST", "/api/backends/apply", "Install backend"),
        ("POST", "/api/backends/delete", "Delete backend"),
        ("POST", "/stores/set", "Vector store set"),
        ("POST", "/stores/get", "Vector store get"),
        ("POST", "/stores/find", "Vector store search"),
        ("POST", "/stores/delete", "Vector store delete"),
        ("GET",  "/api/p2p/stats", "P2P cluster stats"),
        ("GET",  "/api/p2p/workers", "P2P worker list"),
        ("GET",  "/healthz", "Health check"),
        ("GET",  "/readyz", "Readiness check"),
    ]

    t = Table(title="LocalAI Endpoints", show_header=True)
    t.add_column("Method", style="cyan", width=6)
    t.add_column("Endpoint", style="bold")
    t.add_column("Description")
    for method, path, desc in endpoints:
        t.add_row(method, path, desc)
    console.print(t)
    console.print(f"\n  [bold]{len(endpoints)}[/] endpoints integrated\n")

    # ── MCP Tools ────────────────────────────────────────────────────────
    try:
        import aicp.mcp.server as srv
        tool_fns = sorted(n for n in dir(srv) if n.startswith("aicp_") and callable(getattr(srv, n)))
        console.print(f"[bold]MCP Tools[/] ({len(tool_fns)} tools)")
        for fn_name in tool_fns:
            doc = getattr(srv, fn_name).__doc__ or ""
            first_line = doc.strip().split("\n")[0] if doc else ""
            console.print(f"  [cyan]{fn_name}[/]  {first_line}")
        console.print()
    except Exception:
        console.print("  [yellow]Could not load MCP tools[/]\n")

    # ── Slash Commands ───────────────────────────────────────────────────
    from aicp.cli.interactive import _SLASH_HELP
    console.print("[bold]Interactive Slash Commands[/]")
    for line in _SLASH_HELP.strip().split("\n"):
        if line.strip().startswith("/"):
            console.print(f"  [cyan]{line.strip()}[/]")
    # Count them
    cmd_count = sum(1 for l in _SLASH_HELP.split("\n") if l.strip().startswith("/"))
    console.print(f"\n  [bold]{cmd_count}[/] slash commands\n")

    # ── LLM-Callable Tools ───────────────────────────────────────────────
    try:
        from aicp.core.tools import ALL_TOOLS
        console.print(f"[bold]LLM-Callable Tools[/] ({len(ALL_TOOLS)} tools)")
        for tool in ALL_TOOLS:
            name = tool.get("function", {}).get("name", "?")
            desc = tool.get("function", {}).get("description", "")
            short = desc.split(".")[0] if desc else ""
            console.print(f"  [cyan]{name}[/]  {short}")
        console.print()
    except Exception:
        console.print("  [yellow]Could not load LLM tools[/]\n")

    # ── Execution Modes ──────────────────────────────────────────────────
    console.print("[bold]Execution Modes[/]")
    console.print("  [cyan]think[/]  Read, analyze, plan. No writes.")
    console.print("  [cyan]edit[/]   Modify files in controlled scope.")
    console.print("  [cyan]act[/]    Run commands, workflows, tools.")
    console.print()

    # ── Mode Sampling Profiles ───────────────────────────────────────────
    console.print("[bold]Mode Sampling Defaults[/]")
    for mode_name, params in LocalAIBackend._MODE_SAMPLING.items():
        console.print(f"  [cyan]{mode_name}[/]  {params}")
    console.print()

    # ── Models Configured ────────────────────────────────────────────────
    try:
        cfg = load_config()
        local_cfg = get_backend_config(cfg, "local")
        model_keys = [
            "model", "embedding_model", "code_model", "vision_model",
            "whisper_model", "tts_model", "image_model", "reranker_model",
            "sound_model",
        ]
        console.print("[bold]Configured Models[/]")
        for key in model_keys:
            val = local_cfg.get(key, "[dim]not set[/]")
            console.print(f"  {key}: [cyan]{val}[/]")
        console.print()
    except Exception:
        pass

    # ── Fleet & Routing ───────────────────────────────────────────────
    console.print("[bold]Fleet & Routing[/]")
    console.print("  [cyan]Fleet auto-route[/]     Route tasks to best fleet node by VRAM/availability")
    console.print("  [cyan]Model auto-route[/]     Pick best local model per prompt (3B/7B/code)")
    console.print("  [cyan]Failover chain[/]       local → fleet peer → Claude (graceful degradation)")
    console.print("  [cyan]Anti-loop[/]            Remote tasks flagged to prevent recursive routing")
    console.print("  [cyan]Offload dashboard[/]    Track LocalAI vs Claude usage (80% goal)")
    console.print("  [cyan]Route history[/]        Every task records where it ran")
    console.print()
    console.print("  Commands:")
    console.print("    [cyan]make offload[/]         Show offload dashboard")
    console.print("    [cyan]/fleet[/]               Fleet node status (interactive)")
    console.print("    [cyan]/fleet-run <p>[/]       Execute on best fleet node")
    console.print("    [cyan]/fleet-route[/]         Show routing decision")
    console.print("    [cyan]/offload[/]             Offload metrics (interactive)")
    console.print()

    return 0


def _run_metrics() -> int:
    """Show live Prometheus metrics from LocalAI."""
    from rich.table import Table

    local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
    backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
    status = backend.metrics()

    console.print("[bold]AICP Live Metrics[/]\n")

    # ── LocalAI status ──────────────────────────────────────────────────
    lai = status.get("localai", {})
    if not lai.get("available"):
        console.print(f"  [red]LocalAI not reachable at {local_url}[/]")
        return 1

    console.print(f"  URL:         {lai.get('url', local_url)}")
    console.print(f"  Goroutines:  {lai.get('goroutines', '?')}")
    mem_alloc = lai.get("memory_alloc_mb")
    mem_sys = lai.get("memory_sys_mb")
    if mem_alloc is not None:
        console.print(f"  Memory:      {mem_alloc} MiB allocated / {mem_sys} MiB system")

    # Models
    models = lai.get("models", [])
    loaded = lai.get("loaded_models", [])
    if models:
        console.print(f"  Models:      {', '.join(models)}")
    if loaded:
        console.print(f"  GPU loaded:  {', '.join(loaded)}")

    # Backends
    backends = lai.get("backends", [])
    if backends:
        console.print(f"  Backends:    {', '.join(backends[:10])}")

    console.print()

    # ── API call stats ──────────────────────────────────────────────────
    api_calls = lai.get("api_calls", {})
    if api_calls:
        t = Table(title="API Call Stats (from /metrics)", show_header=True)
        t.add_column("Method", style="cyan")
        t.add_column("Count", justify="right")
        t.add_column("Total ms", justify="right")
        t.add_column("Avg ms", justify="right")
        for method in sorted(api_calls.keys()):
            stats = api_calls[method]
            t.add_row(
                method,
                str(stats.get("count", 0)),
                str(stats.get("total_ms", 0)),
                str(stats.get("avg_ms", 0)),
            )
        console.print(t)
        console.print()

    # ── GPU status ──────────────────────────────────────────────────────
    gpu = status.get("gpu", {})
    if gpu.get("available"):
        console.print("[bold]GPU[/]")
        console.print(f"  {gpu.get('name', '?')}")
        used = gpu.get("memory_used_mb", 0)
        total = gpu.get("memory_total_mb", 0)
        pct = gpu.get("memory_used_pct", 0)
        color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
        console.print(f"  VRAM:  [{color}]{used}/{total} MiB ({pct}%)[/]")
        console.print(f"  GPU:   {gpu.get('utilization_pct', '?')}% utilization")
        console.print(f"  Temp:  {gpu.get('temperature_c', '?')}°C")
        console.print()
    else:
        console.print(f"  [yellow]GPU: {gpu.get('error', 'not available')}[/]\n")

    return 0


def _run_stats() -> int:
    """Show aggregated metrics with per-backend breakdown."""
    from aicp.core.metrics import aggregate
    from rich.table import Table
    from rich.panel import Panel

    m = aggregate(1000)

    if m["total_tasks"] == 0:
        console.print("[dim]No history yet.[/]")
        return 0

    # Summary row
    summary = Table(title="AICP Metrics — Summary", show_header=True, expand=False)
    summary.add_column("Metric", style="bold")
    summary.add_column("All", justify="right")
    summary.add_row("Tasks today", str(m["today"]))
    summary.add_row("Tasks this week", str(m["this_week"]))
    summary.add_row("Tasks total", str(m["total_tasks"]))
    summary.add_row("Avg latency", f"{m['avg_duration']:.1f}s")
    summary.add_row("Error rate", f"{m['error_rate']:.1f}%")
    summary.add_row("Prompt tokens", f"{m['total_prompt_tokens']:,}")
    summary.add_row("Completion tokens", f"{m['total_completion_tokens']:,}")
    summary.add_row("Total tokens", f"{m['total_tokens']:,}")
    summary.add_row("Est. cost", f"${m['total_cost_usd']:.4f}")
    console.print(summary)

    # Per-backend comparison table
    by_backend = m.get("by_backend", {})
    if len(by_backend) > 0:
        console.print()
        bt = Table(title="Per-Backend Breakdown", show_header=True, expand=False)
        bt.add_column("Metric", style="bold")
        backend_names = list(by_backend.keys())
        for name in backend_names:
            color = "cyan" if name == "local" else "magenta"
            bt.add_column(f"[{color}]{name}[/]", justify="right")

        def _row(label: str, *vals: str) -> None:
            bt.add_row(label, *vals)

        _row("Tasks", *[str(by_backend[n]["tasks"]) for n in backend_names])
        _row(
            "Avg latency",
            *[f"{by_backend[n]['avg_duration']:.1f}s" for n in backend_names],
        )
        _row(
            "Error rate",
            *[f"{by_backend[n]['error_rate']:.1f}%" for n in backend_names],
        )
        _row(
            "Tokens",
            *[
                f"{by_backend[n]['prompt_tokens'] + by_backend[n]['completion_tokens']:,}"
                for n in backend_names
            ],
        )
        _row("Est. cost", *[f"${by_backend[n]['cost']:.4f}" for n in backend_names])
        console.print(bt)

    return 0


def _run_auto_config() -> int:
    """Auto-detect GPUs and generate optimal model configs."""
    from aicp.core.gpu import detect_gpus, calculate_optimal_config, estimate_model_vram_mb
    from aicp.core.models import list_models, MODELS_DIR
    from rich.table import Table

    gpus = detect_gpus()
    if not gpus:
        console.print("[yellow]No NVIDIA GPUs detected. Models will run on CPU.[/]")
    else:
        table = Table(title="Detected GPUs", show_header=True)
        table.add_column("GPU")
        table.add_column("VRAM Total", justify="right")
        table.add_column("VRAM Free", justify="right")
        table.add_column("Driver")
        for g in gpus:
            table.add_row(
                f"[bold]{g.index}[/] {g.name}",
                f"{g.vram_total_mb} MiB",
                f"[green]{g.vram_free_mb} MiB[/]",
                g.driver_version,
            )
        console.print(table)
        console.print()

    models = list_models()
    if not models:
        console.print("[dim]No models found in models/ directory.[/]")
        return 0

    for m in models:
        gguf_path = MODELS_DIR / m.gguf_file
        if not gguf_path.exists():
            console.print(f"[yellow]{m.name}: GGUF file not found ({m.gguf_file})[/]")
            continue

        est_vram = estimate_model_vram_mb(gguf_path)
        optimal = calculate_optimal_config(gguf_path, gpus)

        console.print(f"[bold]{m.name}[/] ({m.gguf_file}, {m.gguf_size_mb} MiB, est. VRAM: {est_vram} MiB)")
        console.print(f"  Current:  gpu_layers={m.gpu_layers}, context_size={m.context_size}")
        console.print(f"  Optimal:  gpu_layers={optimal['gpu_layers']}, context_size={optimal['context_size']}, threads={optimal['threads']}")

        if "tensor_split" in optimal:
            console.print(f"  Multi-GPU: tensor_split={optimal['tensor_split']}, main_gpu={optimal['main_gpu']}")

        if optimal["gpu_layers"] != m.gpu_layers or optimal["context_size"] != m.context_size:
            console.print("  [yellow]Config differs from optimal.[/] Update? ", end="")
            try:
                answer = input("[y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print()
                continue
            if answer == "y":
                _apply_optimal_config(m.config_path, optimal)
                console.print("  [green]Updated.[/] Restart LocalAI to apply: make local-up")
        else:
            console.print("  [green]Already optimal.[/]")
        console.print()

    return 0


def _apply_optimal_config(config_path: Path, optimal: dict) -> None:
    """Update a model YAML with optimal settings."""
    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    cfg["gpu_layers"] = optimal["gpu_layers"]
    cfg["context_size"] = optimal["context_size"]
    cfg["threads"] = optimal["threads"]

    if "tensor_split" in optimal:
        if "parameters" not in cfg:
            cfg["parameters"] = {}
        cfg["parameters"]["tensor_split"] = optimal["tensor_split"]
        cfg["parameters"]["main_gpu"] = optimal["main_gpu"]

    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def _run_models(command: str, model_name: str = None) -> int:
    """Model management commands."""
    from aicp.core.models import (
        list_models, get_model_config, download_model, activate_model,
        benchmark_model,
    )
    from rich.table import Table
    from rich.progress import Progress

    if command == "list":
        models = list_models()
        if not models:
            console.print("[dim]No models found.[/]")
            return 0

        table = Table(title="Local Models", show_header=True)
        table.add_column("Name", style="bold")
        table.add_column("File")
        table.add_column("Size", justify="right")
        table.add_column("Backend")
        table.add_column("GPU Layers", justify="right")
        table.add_column("Context", justify="right")

        for m in models:
            table.add_row(
                m.name, m.gguf_file, f"{m.gguf_size_mb} MiB",
                m.backend, str(m.gpu_layers), str(m.context_size),
            )
        console.print(table)
        return 0

    elif command == "info" and model_name:
        cfg = get_model_config(model_name)
        if cfg is None:
            print_error(f"Model not found: {model_name}")
            return 1
        import yaml
        console.print(f"[bold]{model_name}[/] configuration:")
        console.print(yaml.dump(cfg, default_flow_style=False))
        return 0

    elif command == "download" and model_name:
        console.print(f"Downloading: {model_name}")
        try:
            with Progress(console=console) as progress:
                task_id = progress.add_task("Downloading...", total=None)

                def on_progress(downloaded, total):
                    if total:
                        progress.update(task_id, completed=downloaded, total=total)

                path = download_model(model_name, progress_callback=on_progress)
            console.print(f"[green]Downloaded:[/] {path}")
            console.print("Config generated. Restart LocalAI to load: [bold]make local-up[/]")
            return 0
        except FileExistsError as e:
            print_error(str(e))
            return 1
        except Exception as e:
            print_error(f"Download failed: {e}")
            return 1

    elif command == "activate" and model_name:
        try:
            from aicp.config.loader import load_config
            config = load_config()
            activate_model(model_name, config)
            console.print(f"[green]Active model set to:[/] {model_name}")
            console.print("Restart LocalAI to apply: [bold]make local-up[/]")
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    elif command == "benchmark" and model_name:
        console.print(f"Benchmarking [bold]{model_name}[/]...")
        try:
            result = benchmark_model(model_name)
            table = Table(title=f"Benchmark: {model_name}", show_header=False)
            table.add_column("Metric", style="bold")
            table.add_column("Value", justify="right")
            table.add_row("Latency", f"{result['latency_seconds']:.2f}s")
            table.add_row("Prompt tokens", str(result["prompt_tokens"]))
            table.add_row("Completion tokens", str(result["completion_tokens"]))
            table.add_row("Tokens/sec", f"{result['tokens_per_second']:.1f}")
            table.add_row("Preview", result["response_preview"])
            console.print(table)
            return 0
        except Exception as e:
            print_error(f"Benchmark failed: {e}")
            return 1

    elif command == "gallery":
        # List models from LocalAI gallery API
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        try:
            backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            available = backend.models_available()
        except Exception as e:
            print_error(f"Gallery unavailable: {e}")
            return 1

        if not available:
            console.print("[dim]No models in gallery.[/]")
            return 0

        # Filter by search term if provided
        if model_name:
            available = [m for m in available if model_name.lower() in m["name"].lower()
                         or model_name.lower() in m.get("description", "").lower()]

        table = Table(title="LocalAI Model Gallery", show_header=True)
        table.add_column("Name", style="bold")
        table.add_column("Installed", justify="center")
        table.add_column("Tags")
        table.add_column("Description", max_width=50)

        for m in available[:50]:  # cap display at 50
            installed = "[green]✓[/]" if m["installed"] else "[dim]–[/]"
            tags = ", ".join(m.get("tags", [])[:3])
            desc = (m.get("description", "") or "")[:50]
            table.add_row(m["name"], installed, tags, desc)

        console.print(table)
        if len(available) > 50:
            console.print(f"[dim]  ... and {len(available) - 50} more. Use --models-arg to filter.[/]")
        return 0

    elif command == "install" and model_name:
        # Install model from gallery via /models/apply
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        try:
            backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            result = backend.model_apply(model_name)
            job_uuid = result.get("uuid", "")
            console.print(f"[green]Installation started:[/] {model_name}")
            console.print(f"  Job UUID: {job_uuid}")
            console.print(f"  Track:    aicp --models job --models-arg {job_uuid}")
            return 0
        except Exception as e:
            print_error(f"Install failed: {e}")
            return 1

    elif command == "job" and model_name:
        # Check model download job status
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        try:
            backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            status = backend.model_job_status(model_name)

            if status.get("error"):
                print_error(f"Job failed: {status['error']}")
                return 1

            if status.get("processed"):
                console.print(f"[green]Download complete.[/]")
            else:
                progress = status.get("progress", 0)
                file_size = status.get("file_size", "?")
                downloaded = status.get("downloaded_size", "?")
                console.print(f"  Progress: {progress:.1f}%  ({downloaded} / {file_size})")
                console.print(f"  Status:   {status.get('message', 'downloading')}")
            return 0
        except Exception as e:
            print_error(f"Job status failed: {e}")
            return 1

    elif command == "unload" and model_name:
        # Unload model from GPU memory
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        try:
            backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            success = backend.model_shutdown(model_name)
            if success:
                console.print(f"[green]Unloaded:[/] {model_name}")
            else:
                print_error(f"Failed to unload: {model_name}")
                return 1
            return 0
        except Exception as e:
            print_error(f"Unload failed: {e}")
            return 1

    elif command == "monitor" and model_name:
        # Check model status and memory usage
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        try:
            backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            info = backend.model_monitor(model_name)
            state_map = {0: "uninitialized", 1: "busy", 2: "ready", -1: "error"}
            state = info.get("state", -1)
            state_label = state_map.get(state, f"unknown ({state})")
            state_color = {0: "dim", 1: "yellow", 2: "green", -1: "red"}.get(state, "dim")

            console.print(f"  Model:  [bold]{model_name}[/]")
            console.print(f"  State:  [{state_color}]{state_label}[/{state_color}]")

            memory = info.get("memory", {})
            if memory:
                total_mb = memory.get("total", 0) / 1024 / 1024
                breakdown = memory.get("breakdown", {})
                weights_mb = breakdown.get("weights", 0) / 1024 / 1024
                kv_mb = breakdown.get("kv_cache", 0) / 1024 / 1024
                console.print(f"  Memory: {total_mb:.0f} MiB total (weights: {weights_mb:.0f}, KV: {kv_mb:.0f})")
            return 0
        except Exception as e:
            print_error(f"Monitor failed: {e}")
            return 1

    else:
        print_error(
            "Usage: --models list|gallery|install|job|unload|monitor|info|download|activate|benchmark --models-arg <name>"
        )
        return 1


def _run_project_cmd(cmd: str, project_path: Path, name: str = None, desc: str = None) -> int:
    """Handle project management commands."""
    from aicp.core.projects import (
        register_project, list_projects, load_project_state,
        unregister_project,
    )
    from rich.table import Table

    if cmd == "register":
        entry = register_project(project_path, name=name, description=desc or "")
        console.print(f"[green]Registered:[/] {entry['name']} at {entry['path']}")
        return 0

    elif cmd == "unregister":
        if unregister_project(project_path):
            console.print(f"[yellow]Unregistered:[/] {project_path}")
        else:
            print_error("Project not found in registry.")
        return 0

    elif cmd == "list":
        projects = list_projects()
        if not projects:
            console.print("[dim]No projects registered. Use --project-cmd register[/]")
            return 0

        table = Table(title="AICP Projects", show_header=True)
        table.add_column("Name", style="bold")
        table.add_column("Path")
        table.add_column("Phase")
        table.add_column("Milestones")
        table.add_column("Last Session")

        for p in projects:
            path = Path(p["path"])
            state = load_project_state(path)
            phase = state.get("phase", "?") if state else "?"
            milestones = state.get("milestones", []) if state else []
            done = sum(1 for m in milestones if m.get("status") == "done")
            total = len(milestones)
            ms_str = f"{done}/{total}" if total else "-"
            last = ""
            if state and state.get("last_session"):
                last = state["last_session"].get("timestamp", "")[:10]
            table.add_row(p["name"], str(path), phase, ms_str, last)

        console.print(table)
        return 0

    elif cmd == "status":
        state = load_project_state(project_path)
        if state is None:
            print_error("No project state found. Register first with --project-cmd register")
            return 1

        console.print(f"[bold]{state.get('name', '?')}[/]")
        console.print(f"  Phase: [cyan]{state.get('phase', '?')}[/]")
        console.print(f"  Description: {state.get('description', '')}")
        console.print(f"  Created: {state.get('created', '?')}")

        last = state.get("last_session")
        if last:
            console.print(f"  Last session: {last.get('timestamp', '')[:19]}")
            if last.get("summary"):
                console.print(f"  Summary: {last['summary']}")

        milestones = state.get("milestones", [])
        if milestones:
            console.print(f"\n  [bold]Milestones:[/]")
            for m in milestones:
                status = m.get("status", "pending")
                color = "green" if status == "done" else "yellow" if status == "in_progress" else "dim"
                console.print(f"    [{color}]{status:12s}[/] {m['name']}")

        decisions = state.get("decisions", [])
        if decisions:
            console.print(f"\n  [bold]Recent decisions:[/]")
            for d in decisions[-5:]:
                console.print(f"    {d.get('timestamp', '')[:10]} {d['decision']}")

        return 0

    # Commands that need a backend are handled separately
    elif cmd in ("create", "plan", "assess"):
        print_error(f"'{cmd}' needs backends. Use after config load (handled in main).")
        return 1

    else:
        print_error(f"Unknown project command: {cmd}")
        print_error("Available: register, unregister, list, status, create, plan, assess")
        return 1


def _run_skill(
    cmd: str, project_path: Path, skill_name: str = None,
    params: List[str] = None, backends: Dict = None, config: Dict = None,
) -> int:
    """Handle skill commands."""
    from aicp.core.skills import (
        discover_skills, get_skill, resolve_params, apply_params,
        create_skill, generate_claude_command, _global_skills_dir, _project_skills_dir,
    )
    from aicp.core.pipeline import run_pipeline
    from rich.table import Table

    if cmd == "list":
        skills = discover_skills(project_path)
        if not skills:
            console.print("[dim]No skills found. Create one with --skill create --skill-name <name>[/]")
            return 0

        table = Table(title="Available Skills", show_header=True)
        table.add_column("Name", style="bold")
        table.add_column("Source")
        table.add_column("Description")
        table.add_column("Params")

        for s in skills:
            param_str = ", ".join(p.name for p in s.parameters) if s.parameters else "-"
            table.add_row(s.name, s.source, s.description[:60], param_str)
        console.print(table)
        return 0

    elif cmd == "run" and skill_name:
        skill = get_skill(skill_name, project_path)
        if not skill:
            print_error(f"Skill not found: {skill_name}")
            return 1

        if not skill.steps:
            print_error(f"Skill '{skill_name}' has no steps (may be a Claude Code command).")
            console.print(f"  Use in Claude Code: [bold]/{skill_name}[/]")
            return 1

        # Parse --param key=value
        provided = {}
        for p in (params or []):
            if "=" in p:
                k, v = p.split("=", 1)
                provided[k] = v

        try:
            resolved = resolve_params(skill, provided)
        except ValueError as e:
            print_error(str(e))
            return 1

        steps = apply_params(skill.steps, resolved)

        console.print(f"Running skill [bold]{skill_name}[/] ({len(steps)} steps)")
        if backends is None:
            print_error("No backends available. Provide config.")
            return 1

        results = run_pipeline(steps, backends, project_path, config)
        for r in results:
            status = "[green]OK[/]" if not r.get("error") else "[red]ERR[/]"
            console.print(f"  {status} Step {r['step_index'] + 1}: {r['mode']}/{r['backend']}")
            if r.get("error"):
                print_error(r["error"])
            elif r.get("result"):
                print_response(r["result"])
        return 0 if all(not r.get("error") for r in results) else 1

    elif cmd == "create" and skill_name:
        console.print(f"Creating skill: [bold]{skill_name}[/]")
        console.print("Where to save?")
        console.print("  1. Global (~/.aicp/skills/)")
        console.print("  2. Project (.aicp/skills/)")
        try:
            choice = input("Choice [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 1

        target = _global_skills_dir() if choice == "1" else _project_skills_dir(project_path)

        console.print("Enter description: ", end="")
        desc = input().strip()

        # Create a simple template
        steps = [
            {"prompt": f"TODO: implement {skill_name}", "mode": "think", "backend": "auto"},
        ]
        path = create_skill(skill_name, desc, [], steps, target)
        console.print(f"[green]Created:[/] {path}")
        console.print("Edit the YAML to add parameters and steps.")
        return 0

    elif cmd == "export" and skill_name:
        skill = get_skill(skill_name, project_path)
        if not skill:
            print_error(f"Skill not found: {skill_name}")
            return 1
        path = generate_claude_command(skill, project_path)
        console.print(f"[green]Exported to Claude Code command:[/] {path}")
        console.print(f"  Use in Claude Code: [bold]/{skill_name}[/]")
        return 0

    else:
        print_error("Usage: --skill list | --skill run|create|export --skill-name <name>")
        return 1


def _run_history(count: int) -> int:
    """Show recent task history."""
    records = list_tasks(count)
    if not records:
        console.print("[dim]No history yet.[/]")
        return 0

    for r in records:
        print_history_entry(
            status="ERR" if r.get("error") else "OK",
            timestamp=r.get("timestamp", "?")[:19],
            mode=r.get("mode", "?"),
            backend=r.get("backend", "?"),
            duration=r.get("duration_seconds", 0),
            prompt=r.get("prompt", ""),
            record_id=r.get("id", "?"),
        )

    return 0


def _run_replay(record_id: str) -> int:
    """Replay a previous task's full output."""
    record = get_task(record_id)
    if record is None:
        print_error(f"Task not found: {record_id}")
        return 1

    console.print(f"[bold]--- Task: {record.get('id', '?')} ---[/]")
    console.print(f"  Time:     {record.get('timestamp', '?')}")
    console.print(f"  Mode:     [cyan]{record.get('mode', '?')}[/]")
    console.print(f"  Backend:  [magenta]{record.get('backend', '?')}[/]")
    console.print(f"  Project:  {record.get('project', '?')}")
    console.print(f"  Duration: {record.get('duration_seconds', 0):.1f}s")
    console.print(f"  Prompt:   {record.get('prompt', '')}")
    console.print()

    error = record.get("error")
    if error:
        print_error(error)
    else:
        print_response(record.get("response", ""))

    return 0


def _run_kb(
    command: str,
    arg: Optional[str],
    project_path: Path,
    config: Dict,
    backends: Dict[str, Backend],
) -> int:
    """Handle --kb commands for knowledge base management."""
    from aicp.config.loader import get_rag_config
    from aicp.core.rag import RAGPipeline, VectorStore, build_rag_pipeline

    rag_cfg = get_rag_config(config)
    db_path_str = rag_cfg["db_path"]
    db_path = Path(db_path_str) if Path(db_path_str).is_absolute() else project_path / db_path_str

    # For commands that need the embedding backend
    local_backend = backends.get("local")

    if command == "status":
        vs = VectorStore(db_path)
        info = vs.stats(rag_cfg["store_name"])
        vs.close()
        console.print(f"[bold]Knowledge Base Status[/]")
        console.print(f"  Store:    {info['store']}")
        console.print(f"  Sources:  {info['total_sources']}")
        console.print(f"  Chunks:   {info['total_chunks']}")
        console.print(f"  DB path:  {db_path}")
        console.print(f"  RAG enabled: {'[green]yes[/]' if rag_cfg['enabled'] else '[dim]no[/]'}")
        return 0

    if command == "list":
        vs = VectorStore(db_path)
        sources = vs.list_sources(rag_cfg["store_name"])
        vs.close()
        if not sources:
            console.print("[dim]Knowledge base is empty. Add files with: aicp --kb add --kb-arg <path>[/]")
            return 0
        from rich.table import Table
        t = Table(title="Knowledge Base Sources", show_header=True)
        t.add_column("Source", style="bold")
        t.add_column("Chunks", justify="right")
        for s in sources:
            t.add_row(s["source"], str(s["chunks"]))
        console.print(t)
        return 0

    if command == "add":
        if not arg:
            print_error("Usage: aicp --kb add --kb-arg <file-or-directory>")
            return 1
        if not local_backend:
            print_error("KB add requires the local backend (for embeddings)")
            return 1

        pipeline = build_rag_pipeline(
            backend=local_backend,
            db_path=db_path,
            store_name=rag_cfg["store_name"],
            chunk_size=rag_cfg["chunk_size"],
            chunk_overlap=rag_cfg["chunk_overlap"],
            top_k=rag_cfg["top_k"],
            threshold=rag_cfg["threshold"],
        )

        target = Path(arg)
        if not target.is_absolute():
            target = project_path / target

        if not target.exists():
            print_error(f"Path not found: {target}")
            return 1

        files: List[Path] = []
        if target.is_file():
            files = [target]
        else:
            # Ingest all text files in the directory
            for ext in ("*.py", "*.md", "*.txt", "*.yaml", "*.yml", "*.json", "*.toml", "*.rst", "*.sh"):
                files.extend(target.rglob(ext))
            # Filter out hidden dirs and common excludes
            files = [
                f for f in files
                if not any(p.startswith(".") for p in f.relative_to(target).parts[:-1])
                and "__pycache__" not in str(f)
                and "node_modules" not in str(f)
            ]

        if not files:
            print_error(f"No ingestible files found in {target}")
            return 1

        total_chunks = 0
        with spinner(f"Ingesting {len(files)} file(s)..."):
            for f in sorted(files):
                try:
                    n = pipeline.ingest_file(f)
                    total_chunks += n
                except Exception as e:
                    print_warning(f"Skipped {f.name}: {e}")

        console.print(f"[green]Ingested {len(files)} file(s), {total_chunks} chunks into KB[/]")
        return 0

    if command == "search":
        if not arg:
            print_error("Usage: aicp --kb search --kb-arg <query>")
            return 1
        if not local_backend:
            print_error("KB search requires the local backend (for embeddings)")
            return 1

        from aicp.core.kb import KnowledgeBase
        kb = KnowledgeBase(local_backend, config)

        with spinner("Searching knowledge base (with reranking)..."):
            results = kb.search(arg, top_k=rag_cfg["top_k"])

        if not results:
            console.print("[dim]No relevant results found.[/]")
            return 0

        for i, r in enumerate(results, 1):
            source = Path(r["source"]).name if "/" in r["source"] else r["source"]
            console.print(f"\n[bold cyan]#{i}[/] [dim](score: {r['score']:.3f})[/] [yellow]{source}[/]")
            preview = r["text"][:200].replace("\n", " ")
            if len(r["text"]) > 200:
                preview += "..."
            console.print(f"  {preview}")

        return 0

    if command == "delete":
        if not arg:
            print_error("Usage: aicp --kb delete --kb-arg <source>")
            return 1
        vs = VectorStore(db_path)
        count = vs.delete_source(rag_cfg["store_name"], arg)
        vs.close()
        if count > 0:
            console.print(f"[green]Deleted {count} chunks from source: {arg}[/]")
        else:
            print_warning(f"No chunks found for source: {arg}")
        return 0

    print_error(f"Unknown KB command: {command}. Use: add, search, list, status, delete")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --control (no config needed)
    if args.control is not None:
        from aicp.cli.control import run_control
        project_name = None if args.control == "overview" else args.control
        return run_control(project_name)

    # --project-cmd (register/list/status don't need config)
    if args.project_cmd and args.project_cmd not in ("create", "plan", "assess"):
        return _run_project_cmd(
            args.project_cmd, args.project.resolve(),
            name=args.project_name, desc=args.project_desc,
        )

    # --agent mode (start daemon, no config needed beyond default)
    if args.agent is not None:
        from aicp.agent.server import run_agent
        run_agent(port=int(args.agent), token=args.agent_token or "")
        return 0

    # --auto-config (no config needed)
    if args.auto_config:
        return _run_auto_config()

    # --models (no config needed)
    if args.models is not None:
        return _run_models(args.models, args.models_arg)

    # --stats mode (no config needed)
    if args.stats:
        return _run_stats()

    # --history mode (no config needed)
    if args.history is not None:
        return _run_history(args.history)

    # --replay mode (no config needed)
    if args.replay:
        return _run_replay(args.replay)

    # --session-list (no config needed)
    if args.session_list:
        from aicp.core.session import list_sessions
        from rich.table import Table
        sessions = list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions. Use --session NAME to start one.[/]")
            return 0
        t = Table(title="Saved Sessions", show_header=True)
        t.add_column("Name", style="bold")
        t.add_column("Turns", justify="right")
        t.add_column("Last Updated", style="dim")
        for s in sessions:
            t.add_row(s["name"], str(s["turns"]), s["updated"][:19])
        console.print(t)
        return 0

    # --session-delete (no config needed)
    if args.session_delete:
        from aicp.core.session import delete_session
        if delete_session(args.session_delete):
            console.print(f"[green]Deleted session:[/] {args.session_delete}")
        else:
            print_error(f"Session not found: {args.session_delete}")
        return 0

    # --observe: live system status (no config needed)
    if getattr(args, "observe", False):
        from aicp.core.observability import get_system_status
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        status = get_system_status(local_url)

        lai = status["localai"]
        gpu = status["gpu"]

        console.print("[bold]System Status[/]\n")

        # Health probes
        _obs_backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
        health = _obs_backend.health_check()
        ready = _obs_backend.is_ready()
        h_tag = "[green]healthy[/]" if health.get("healthy") else f"[red]{health.get('error', 'unhealthy')}[/]"
        r_tag = "[green]ready[/]" if ready else "[yellow]not ready[/]"
        console.print(f"  Health:      {h_tag}")
        console.print(f"  Readiness:   {r_tag}")
        console.print()

        # LocalAI
        if lai["available"]:
            console.print(f"  LocalAI:     [green]ONLINE[/] ({lai['url']})")
            console.print(f"  Models:      {', '.join(lai['models']) or 'none'}")
            loaded = lai.get("loaded_models", [])
            if loaded:
                console.print(f"  GPU active:  [bold green]{', '.join(loaded)}[/]")
            else:
                console.print(f"  GPU active:  [dim]none (model loads on first request)[/]")
            backends = lai.get("backends", [])
            if backends:
                console.print(f"  Backends:    {', '.join(backends)}")
            if lai.get("goroutines"):
                console.print(f"  Goroutines:  {int(lai['goroutines'])}")
            if lai.get("memory_alloc_mb"):
                console.print(f"  Memory:      {lai['memory_alloc_mb']} MiB allocated")
            for method, stats in lai.get("api_calls", {}).items():
                if stats.get("count", 0) > 0:
                    console.print(f"  API {method}:    {stats['count']} calls, avg {stats['avg_ms']:.0f}ms")
        else:
            console.print(f"  LocalAI:     [red]OFFLINE[/]")

        # GPU
        console.print()
        if gpu.get("available"):
            console.print(f"  GPU:         {gpu['name']}")
            console.print(f"  VRAM:        {gpu['memory_used_mb']}/{gpu['memory_total_mb']} MiB ({gpu['memory_used_pct']:.0f}%)")
            console.print(f"  Utilization: {gpu['utilization_pct']}%")
            console.print(f"  Temperature: {gpu['temperature_c']}°C")
        else:
            console.print(f"  GPU:         [dim]{gpu.get('error', 'unavailable')}[/]")

        # P2P cluster
        try:
            p2p_backend = LocalAIBackend(base_url=local_url, model="hermes", max_tokens=256, api_key="")
            p2p = p2p_backend.p2p_stats()
            if p2p.get("enabled"):
                console.print()
                console.print(f"  P2P:         [green]ENABLED[/]")
                for k, v in p2p.items():
                    if k not in ("enabled", "error"):
                        console.print(f"  {k}:  {v}")
            # Silently skip if P2P not enabled
        except Exception:
            pass

        # Feature detection
        try:
            srv_cfg = _obs_backend.server_config()
            features = srv_cfg.get("features", [])
            if features:
                console.print()
                console.print(f"  Features:    {', '.join(features)}")
        except Exception:
            pass

        return 0

    # --self-test: validate all features (no config needed)
    if getattr(args, "self_test", False):
        return _run_self_test()

    # --capabilities: show all integrated features
    if getattr(args, "capabilities", False):
        return _run_capabilities()

    # --metrics: live Prometheus metrics
    if getattr(args, "metrics", False):
        return _run_metrics()

    # --offload: LocalAI offload dashboard
    if getattr(args, "offload", False):
        from aicp.core.metrics import offload_report
        r = offload_report()
        if r["total_tasks"] == 0:
            print("No task history yet. Run some tasks first.")
            return 0
        bar_len = 30
        filled = int(r["offload_pct"] / 100 * bar_len)
        bar = "#" * filled + "-" * (bar_len - filled)
        bar_list = list(bar)
        target_pos = int(80 / 100 * bar_len)
        if target_pos < bar_len:
            bar_list[target_pos] = "|"
        bar_str = "".join(bar_list)
        goal = "GOAL MET" if r["goal_met"] else "in progress"
        print(f"\nLocalAI Offload Dashboard ({goal})")
        print(f"[{bar_str}] {r['offload_pct']}% offloaded (target: 80%)")
        print(f"")
        fleet_info = f" ({r['fleet_tasks']} fleet-routed)" if r.get('fleet_tasks') else ""
        failover_info = f" ({r['failover_tasks']} failovers)" if r.get('failover_tasks') else ""
        print(f"Tasks:    {r['local_tasks']} local / {r['claude_tasks']} claude / {r['total_tasks']} total{fleet_info}{failover_info}")
        print(f"Tokens:   {r['local_tokens']:,} local / {r['claude_tokens']:,} claude ({r['token_savings_pct']}% local)")
        print(f"Speed:    {r['avg_local_duration']}s avg local / {r['avg_claude_duration']}s avg claude")
        print(f"Cost:     ${r['claude_cost_usd']:.4f} spent on Claude")
        print(f"Saved:    ~${r['estimated_savings_usd']:.4f} by using LocalAI")
        print(f"Activity: {r['today']} today / {r['this_week']} this week")
        return 0

    # --status: system status (GPU, model, routing, offload)
    if getattr(args, "status", False):
        import httpx
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        console.print("[bold]AICP System Status[/]\n")

        # GPU
        try:
            from aicp.core.gpu import detect_gpus
            gpus = detect_gpus()
            for g in gpus:
                used = g.get("vram_used_mb", 0)
                total = g.get("vram_total_mb", 0)
                free = g.get("vram_free_mb", 0)
                pct = round(used / total * 100) if total else 0
                console.print(f"  [cyan]GPU[/]       {g.get('name', '?')} — {used}MB/{total}MB ({pct}% used, {free}MB free)")
        except Exception:
            console.print("  [cyan]GPU[/]       [dim]unavailable[/]")

        # Loaded models
        try:
            r = httpx.get(f"{local_url}/v1/models", timeout=5.0)
            models_data = r.json().get("data", [])
            loaded = [m.get("id", "?") for m in models_data] if models_data else []
            if loaded:
                console.print(f"  [cyan]Models[/]    {', '.join(loaded)}")
            else:
                console.print("  [cyan]Models[/]    [dim]none loaded[/]")
        except Exception:
            console.print("  [cyan]Models[/]    [dim]LocalAI not reachable[/]")

        # Routing config
        auto_route = config.get("backends", {}).get("local", {}).get("auto_route", False)
        fleet_route = config.get("cluster", {}).get("auto_route", False)
        console.print(f"  [cyan]Routing[/]   model={'[green]ON[/]' if auto_route else '[dim]OFF[/]'}, fleet={'[green]ON[/]' if fleet_route else '[dim]OFF[/]'}")

        # Fleet nodes
        try:
            from aicp.core.cluster import load_fleet_config, check_cluster
            from aicp.core.controller import _local_ips
            import socket as _sock
            nodes = load_fleet_config()
            if nodes:
                local_ips = _local_ips()
                nodes = check_cluster(nodes)
                for n in nodes:
                    is_self = n.host in local_ips or n.name.lower() == _sock.gethostname().lower()
                    if n.online:
                        status = "[green]online[/]"
                    elif is_self:
                        status = "[yellow]local[/] [dim](no agent daemon)[/]"
                    else:
                        status = "[red]offline[/]"
                    console.print(f"  [cyan]Fleet[/]     {n.name} ({n.host}:{n.port}) — {status}")
            else:
                console.print("  [cyan]Fleet[/]     [dim]not configured[/]")
        except Exception:
            console.print("  [cyan]Fleet[/]     [dim]unavailable[/]")

        # Offload stats
        try:
            from aicp.core.metrics import offload_report
            rpt = offload_report(100)
            if rpt["total_tasks"] > 0:
                goal_icon = "[green]GOAL MET[/]" if rpt["goal_met"] else f"[yellow]{80 - rpt['offload_pct']:.0f}% to go[/]"
                console.print(f"  [cyan]Offload[/]   {rpt['offload_pct']}% ({rpt['local_tasks']}L/{rpt['claude_tasks']}C) {goal_icon}")
                console.print(f"  [cyan]Activity[/]  {rpt['today']} today / {rpt['this_week']} this week")
            else:
                console.print("  [cyan]Offload[/]   [dim]no history yet[/]")
        except Exception:
            console.print("  [cyan]Offload[/]   [dim]unavailable[/]")

        console.print()
        return 0

    # --bench: quick performance benchmark (no config needed)
    if getattr(args, "bench", False):
        from aicp.core.observability import (
            measure_request, measure_embedding, measure_rerank, measure_grammar,
        )
        local_url = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8090")
        console.print("[bold]AICP Performance Benchmark[/]\n")

        # ── Chat (streaming, 3 runs) ──
        console.print("[cyan]Chat (hermes, streaming)[/]")
        for run in range(3):
            label = "cold" if run == 0 else f"warm"
            with spinner(f"Run {run + 1}/3 ({label})..."):
                result = measure_request(local_url, model="hermes")
            if result.get("error"):
                print_error(f"  {result['error']}")
                break
            console.print(
                f"  Run {run + 1}: "
                f"total={result['total_ms']:.0f}ms  "
                f"TTFT={result.get('ttft_ms', '?')}ms  "
                f"gen={result['generation_ms']:.0f}ms  "
                f"tok/s={result['tokens_per_sec']}"
            )

        # ── Grammar-constrained ──
        console.print("\n[cyan]Grammar-constrained (yes/no)[/]")
        with spinner("Running grammar bench..."):
            result = measure_grammar(local_url)
        if result.get("error"):
            print_error(f"  {result['error']}")
        else:
            console.print(
                f"  total={result['total_ms']:.0f}ms  "
                f"response=\"{result['response']}\""
            )

        # ── Embedding ──
        console.print("\n[cyan]Embedding (nomic-embed)[/]")
        with spinner("Running embedding bench..."):
            result = measure_embedding(local_url)
        if result.get("error"):
            print_error(f"  {result['error']}")
        else:
            console.print(
                f"  total={result['total_ms']:.0f}ms  "
                f"dim={result['dimensions']}  "
                f"chars={result['chars']}"
            )

        # ── Reranking ──
        console.print("\n[cyan]Reranking (bge-reranker-v2-m3)[/]")
        with spinner("Running rerank bench..."):
            result = measure_rerank(local_url)
        if result.get("error"):
            print_error(f"  {result['error']}")
        else:
            console.print(
                f"  total={result['total_ms']:.0f}ms  "
                f"docs={result['documents']}  "
                f"results={result['results']}"
            )

        return 0

    # --profile-cmd: profile management (runs before config load)
    if getattr(args, "profile_cmd", None):
        return _run_profile_cmd(args.profile_cmd, args.profile, getattr(args, "profile_arg", None))

    # Load config (with optional profile overlay)
    try:
        project_path = args.project.resolve() if hasattr(args, "project") and args.project else None
        profile_name = getattr(args, "profile", None)
        config = (
            load_config(args.config, project_path=project_path, profile=profile_name)
            if args.config
            else load_config(project_path=project_path, profile=profile_name)
        )
    except (FileNotFoundError, ValueError) as e:
        print_error(f"Config: {e}")
        return 1

    backends = _build_backends(config)

    # --kb commands (knowledge base / RAG management)
    if args.kb:
        return _run_kb(args.kb, args.kb_arg, args.project.resolve(), config, backends)

    # --skill commands
    if args.skill:
        return _run_skill(
            args.skill, args.project.resolve(),
            skill_name=args.skill_name, params=args.param,
            backends=backends, config=config,
        )

    # Project commands that need backends (create, plan, assess)
    if args.project_cmd in ("create", "plan", "assess"):
        from aicp.cli.project_ops import create_project, plan_project, assess_project
        from aicp.core.router import classify_task
        # Pick best available backend
        backend_name = classify_task("project analysis", Mode.THINK, backends, config)
        backend = backends[backend_name]
        try:
            if args.project_cmd == "create":
                create_project(
                    name=args.project_name or "new-project",
                    parent_dir=args.project.resolve(),
                    backend=backend,
                    idea=args.project_desc or "",
                )
            elif args.project_cmd == "plan":
                plan_project(args.project.resolve(), backend)
            elif args.project_cmd == "assess":
                assess_project(args.project.resolve(), backend)
            return 0
        except (ValueError, FileExistsError) as e:
            print_error(str(e))
            return 1

    # --check mode
    if args.check:
        return _run_check(config, backends)

    # --dashboard mode
    if args.dashboard:
        from aicp.cli.dashboard import run_dashboard
        local_cfg = get_backend_config(config, "local")
        return run_dashboard(local_cfg.get("base_url", "http://localhost:8090"))

    # --interactive mode (LocalAI REPL)
    if args.interactive:
        from aicp.cli.interactive import run_interactive
        local_cfg = get_backend_config(config, "local")
        return run_interactive(
            base_url=local_cfg.get("base_url", "http://localhost:8090"),
            model=local_cfg.get("model", "default"),
            mode=Mode(args.mode),
            project_path=args.project.resolve(),
            max_tokens=local_cfg.get("max_tokens", 2048),
            stream=args.stream,
            backend=backends.get("local"),
            config=config,
        )

    # --continue-session (resume Claude Code session)
    if args.continue_session:
        import subprocess as sp
        cmd = ["claude", "-c"]
        if args.prompt:
            cmd.extend(["-p", args.prompt])
        try:
            result = sp.run(cmd, cwd=str(args.project.resolve()))
            return result.returncode
        except FileNotFoundError:
            print_error("claude CLI not found on PATH.")
            return 1

    # --resume (resume named Claude Code session)
    if args.resume:
        import subprocess as sp
        cmd = ["claude", "-r", args.resume]
        if args.prompt:
            cmd.extend(["-p", args.prompt])
        try:
            result = sp.run(cmd, cwd=str(args.project.resolve()))
            return result.returncode
        except FileNotFoundError:
            print_error("claude CLI not found on PATH.")
            return 1

    # --pipeline mode
    if args.pipeline:
        from aicp.core.pipeline import load_pipeline, run_pipeline
        try:
            pipeline_data = load_pipeline(args.pipeline)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return 1
        results = run_pipeline(pipeline_data, backends, args.project.resolve(), config)
        for r in results:
            status = "[green]OK[/]" if not r.get("error") else "[red]ERR[/]"
            agent_tag = f" [{r['agent']}]" if r.get("agent") else ""
            console.print(f"  {status} Step {r['step_index'] + 1}: {r['mode']}/{r['backend']}{agent_tag}")
            if r.get("error"):
                print_error(r["error"])
            elif r.get("result"):
                print_response(r["result"])
        return 0 if all(not r["error"] for r in results) else 1

    # --mcp: start MCP server (stdio transport)
    if getattr(args, "mcp", False):
        from aicp.mcp.server import run_stdio
        run_stdio()
        return 0

    # Normal mode: need a prompt (unless --transcribe, --vision, or --imagine which can work standalone)
    if (not args.prompt
            and not getattr(args, "transcribe", None)
            and not getattr(args, "vision", None)
            and not getattr(args, "imagine", None)
            and not getattr(args, "voice_pipeline", None)):
        parser.print_help()
        return 1

    # Resolve auto backend
    actual_backend = args.backend
    if args.backend == "auto":
        from aicp.core.router import classify_task_with_reason
        actual_backend, reason = classify_task_with_reason(
            args.prompt, Mode(args.mode), backends, config
        )
        console.print(f"  [dim]Auto-routed to {actual_backend} ({reason})[/]", highlight=False)

    # --router-debug: show routing decision table
    if args.router_debug:
        from aicp.core.router import classify_task_with_reason, _COMPLEX_KEYWORDS, _SIMPLE_KEYWORDS
        from rich.table import Table as _Table
        debug_backend, debug_reason = classify_task_with_reason(
            args.prompt, Mode(args.mode), backends, config
        )
        dt = _Table(title="Router Debug", show_header=True, expand=False)
        dt.add_column("Factor", style="bold")
        dt.add_column("Value")
        dt.add_row("Mode", args.mode)
        dt.add_row("Prompt length", f"{len(args.prompt)} chars")
        complex_hits = _COMPLEX_KEYWORDS.findall(args.prompt)
        simple_hits = _SIMPLE_KEYWORDS.findall(args.prompt)
        dt.add_row("Complex keywords", ", ".join(complex_hits) if complex_hits else "[dim]none[/]")
        dt.add_row("Simple keywords", ", ".join(simple_hits) if simple_hits else "[dim]none[/]")
        dt.add_row("Local available", str(backends.get("local") and backends["local"].is_available()))
        dt.add_row("OpenRouter available", str(backends.get("openrouter") and backends["openrouter"].is_available()))
        dt.add_row("Claude available", str(backends.get("claude") and backends["claude"].is_available()))
        dt.add_row("Recommended", f"[cyan]{debug_backend}[/]")
        dt.add_row("Reason", debug_reason)
        if args.backend != "auto":
            dt.add_row("Overridden to", f"[magenta]{actual_backend}[/]")
        console.print(dt)

    # --stream mode: real-time output (both Claude and LocalAI)
    if args.stream:
        from rich.live import Live
        from rich.text import Text
        backend = backends[actual_backend]
        if not hasattr(backend, "execute_stream"):
            print_warning(f"Backend '{actual_backend}' does not support streaming. Running normally.")
        else:
            collected = []
            try:
                with Live(Text(""), console=console, refresh_per_second=4) as live:
                    for chunk in backend.execute_stream(
                        args.prompt, Mode(args.mode), args.project.resolve()
                    ):
                        collected.append(chunk)
                        live.update(Text("".join(collected)))
                full_result = "".join(collected)
                print_response(full_result)

                # Apply THINK-mode and secret-leak scans to streamed response too
                if actual_backend == "local" and args.mode == "think":
                    from aicp.guardrails.response import scan_think_mode
                    for warning in scan_think_mode(full_result, Mode(args.mode)):
                        print_warning(warning)
                from aicp.guardrails.response import scan_response_secrets
                for warning in scan_response_secrets(full_result):
                    print_warning(f"SECRET LEAK RISK: {warning}")

                return 0
            except Exception as e:
                print_error(str(e))
                return 1

    # --approval mode: plan first, then execute
    if args.approval:
        from aicp.core.approval import run_with_approval
        backend = backends.get(actual_backend)
        if not backend:
            print_error(f"Unknown backend: {actual_backend}")
            return 1
        try:
            result = run_with_approval(
                args.prompt, Mode(args.mode), args.project.resolve(), backend,
            )
            print_response(result)
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --rag: augment prompt with knowledge base context (with reranking)
    if getattr(args, "rag", False) and args.prompt:
        from aicp.config.loader import get_rag_config

        rag_cfg = get_rag_config(config)
        db_path_str = rag_cfg["db_path"]
        db_path = (
            Path(db_path_str) if Path(db_path_str).is_absolute()
            else args.project.resolve() / db_path_str
        )
        if db_path.exists():
            local_backend = backends.get("local")
            if local_backend:
                from aicp.core.kb import KnowledgeBase
                kb = KnowledgeBase(local_backend, config)
                args.prompt = kb.augment_prompt(
                    args.prompt, max_context_chars=rag_cfg["max_context_chars"],
                )

    # Auto-RAG: when rag.enabled is true, automatically augment prompts with KB context
    if not getattr(args, "rag", False) and args.prompt:
        from aicp.config.loader import get_rag_config
        rag_cfg = get_rag_config(config)
        if rag_cfg.get("enabled", False):
            db_path_str = rag_cfg["db_path"]
            db_path = (
                Path(db_path_str) if Path(db_path_str).is_absolute()
                else args.project.resolve() / db_path_str
            )
            if db_path.exists():
                local_backend = backends.get("local")
                if local_backend:
                    from aicp.core.kb import KnowledgeBase
                    kb = KnowledgeBase(local_backend, config)
                    if kb.stats().get("total_chunks", 0) > 0:
                        args.prompt = kb.augment_prompt(
                            args.prompt, max_context_chars=rag_cfg["max_context_chars"],
                        )

    # --json mode: force JSON output from LocalAI
    if getattr(args, "json", False) and actual_backend == "local":
        backend = backends["local"]
        try:
            with spinner("Asking local (JSON mode)..."):
                result = backend.execute_json(
                    args.prompt, Mode(args.mode), args.project.resolve(),
                )
            print_response(json.dumps(result, indent=2))
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --grammar / --grammar-file: GBNF-constrained generation
    grammar_str = getattr(args, "grammar", None)
    grammar_file = getattr(args, "grammar_file", None)
    if grammar_file and grammar_file.exists():
        grammar_str = grammar_file.read_text()
    if grammar_str and actual_backend == "local":
        backend = backends["local"]
        try:
            with spinner("Asking local (grammar-constrained)..."):
                result = backend.execute_grammar(
                    args.prompt, grammar_str, Mode(args.mode), args.project.resolve(),
                )
            print_response(result)
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --sound: generate sound/music from text description
    if getattr(args, "sound", None) and actual_backend == "local":
        backend = backends["local"]
        local_cfg = config.get("backends", {}).get("local", {})
        sound_model = local_cfg.get("sound_model", "transformers-musicgen")
        out = Path("/tmp/aicp_sound.wav")
        try:
            with spinner(f"Generating sound ({sound_model})..."):
                backend.generate_sound(args.sound, out, model=sound_model)
            console.print(f"[green]Sound saved to:[/] {out}")
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --complete: raw text completion (no chat template)
    if getattr(args, "complete", False) and actual_backend == "local" and args.prompt:
        backend = backends["local"]
        try:
            if getattr(args, "stream", False):
                for chunk in backend.complete_stream(args.prompt):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                sys.stdout.write("\n")
            else:
                with spinner("Completing text..."):
                    result = backend.complete(args.prompt)
                print_response(result)
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --tools mode: function calling with built-in tools
    if getattr(args, "tools", False) and actual_backend == "local":
        backend = backends["local"]
        try:
            with spinner("Asking local (with native function calling)..."):
                result = backend.execute_with_native_tools(
                    args.prompt, Mode(args.mode), args.project.resolve(),
                )
            print_response(result)
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --transcribe: audio-to-text via whisper
    if getattr(args, "transcribe", None) and actual_backend == "local":
        audio_path = Path(args.transcribe)
        if not audio_path.is_absolute():
            audio_path = args.project.resolve() / audio_path
        if not audio_path.exists():
            print_error(f"Audio file not found: {audio_path}")
            return 1

        backend = backends["local"]
        try:
            with spinner("Transcribing audio..."):
                result = backend.transcribe(audio_path)
            text = result.get("text", "").strip()
            if text:
                print_response(text)
                # If --speak is also set, pipe through LLM then TTS
                if not args.prompt:
                    return 0
                # If prompt is provided, use transcription as context
                args.prompt = f"Audio transcription: {text}\n\n{args.prompt}"
            else:
                print_warning("No speech detected in audio.")
                return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --voice-pipeline: full audio round-trip (transcribe → LLM → TTS)
    if getattr(args, "voice_pipeline", None) and actual_backend == "local":
        audio_input = Path(args.voice_pipeline)
        if not audio_input.is_absolute():
            audio_input = args.project.resolve() / audio_input
        if not audio_input.exists():
            print_error(f"Audio file not found: {audio_input}")
            return 1

        voice_output = (
            Path(args.voice_output) if getattr(args, "voice_output", None)
            else Path("/tmp/aicp_voice_response.wav")
        )
        local_cfg = get_backend_config(config, "local")
        backend = backends["local"]
        try:
            with spinner("Processing voice pipeline..."):
                result = backend.voice_pipeline(
                    audio_input, voice_output,
                    mode=Mode(args.mode),
                    project_path=args.project.resolve(),
                    whisper_model=local_cfg.get("whisper_model", "whisper-1"),
                    tts_model=local_cfg.get("tts_model", "piper-tts"),
                )
            console.print(f"  [dim]You said:[/] {result['transcription']}")
            print_response(result["response"])
            console.print(f"  [dim]Audio response saved to {result['audio_output']}[/]")
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --imagine: generate image from text prompt
    if getattr(args, "imagine", None) and actual_backend == "local":
        img_prompt = args.imagine
        img_size = getattr(args, "imagine_size", "512x512") or "512x512"
        img_output = Path(args.imagine_output) if getattr(args, "imagine_output", None) else Path("/tmp/aicp_imagine.png")
        img_model = get_backend_config(config, "local").get("image_model", "stablediffusion")

        backend = backends["local"]
        try:
            with spinner("Generating image..."):
                backend.generate_image(img_prompt, img_output, model=img_model, size=img_size)
            console.print(f"  [green]Image saved to {img_output}[/]")
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # --vision mode: send image to vision model
    if getattr(args, "vision", None) and actual_backend == "local":
        import base64
        image_path = Path(args.vision)
        if not image_path.is_absolute():
            image_path = args.project.resolve() / image_path
        if not image_path.exists():
            print_error(f"Image not found: {image_path}")
            return 1

        # Detect MIME type
        suffix = image_path.suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
        mime = mime_map.get(suffix, "image/png")

        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = args.prompt or "Describe this image in detail."

        backend = backends["local"]
        try:
            with spinner("Analyzing image with vision model..."):
                result = backend.execute_vision(
                    prompt, image_data, Mode(args.mode), args.project.resolve(),
                    image_mime=mime,
                )
            print_response(result)
            return 0
        except Exception as e:
            print_error(str(e))
            return 1

    # Build extra kwargs for Claude Code
    extra_kwargs = {}
    if actual_backend == "claude":
        if args.effort:
            extra_kwargs["effort"] = args.effort
        if args.schema:
            schema_path = Path(args.schema)
            if not schema_path.exists():
                print_error(f"Schema file not found: {args.schema}")
                return 1
            extra_kwargs["json_schema"] = schema_path.read_text()

    # --session: load conversation history for LocalAI single-shot continuity
    session_messages: List = []
    if args.session and actual_backend == "local":
        from aicp.core.session import load_session
        session_messages = load_session(args.session)
        turns = (len(session_messages) - 1) // 2 if session_messages else 0
        if turns > 0:
            console.print(f"  [dim]Session '{args.session}': {turns} previous turn(s) loaded[/]")
    elif args.session and actual_backend != "local":
        print_warning("--session is only supported with --backend local (LocalAI).")

    # Start metrics collector (optional — records to /metrics on :9101)
    _mc = None
    try:
        from aicp.core.prometheus import MetricsCollector, start_metrics_server
        _mc = MetricsCollector()
        start_metrics_server(_mc, port=9101)
    except Exception:
        pass

    controller = Controller(backends, config=config, metrics_collector=_mc)
    task = Task(
        prompt=args.prompt,
        mode=Mode(args.mode),
        project_path=args.project.resolve(),
        backend_name=actual_backend,
    )

    try:
        with spinner(f"Asking {actual_backend}..."):
            if extra_kwargs and actual_backend == "claude":
                backend = backends["claude"]
                result = backend.execute(
                    args.prompt, Mode(args.mode), args.project.resolve(),
                    **extra_kwargs,
                )
                from aicp.core.history import save_task
                usage = getattr(backend, "last_usage", {})
                save_task(
                    prompt=args.prompt, mode=args.mode, backend="claude",
                    project=str(args.project.resolve()), response=result,
                    duration_seconds=0, model=usage.get("model"),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    estimated_cost_usd=usage.get("estimated_cost_usd"),
                )
            elif session_messages and actual_backend == "local":
                # Session mode: inject history into the LocalAI request
                local_backend = backends["local"]
                system = local_backend._system_prompt(Mode(args.mode), args.project.resolve())
                # Rebuild messages: system + history + new user turn
                if not session_messages or session_messages[0].get("role") != "system":
                    messages = [{"role": "system", "content": system}] + session_messages
                else:
                    messages = list(session_messages)
                messages.append({"role": "user", "content": args.prompt})
                import httpx as _httpx
                resp = _httpx.post(
                    f"{local_backend.base_url}/v1/chat/completions",
                    json={"model": local_backend.model, "messages": messages,
                          "max_tokens": local_backend.max_tokens,
                          **local_backend.sampling_params_for_mode(Mode(args.mode))},
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                result = data["choices"][0]["message"]["content"]
                messages.append({"role": "assistant", "content": result})
                # Save updated session (strip system message — it's rebuilt each time)
                from aicp.core.session import save_session
                save_session(args.session, [m for m in messages if m["role"] != "system"])
                console.print(f"  [dim]Session '{args.session}' updated[/]")
            else:
                result = controller.run(task)
        if controller.last_route and controller.last_route.startswith("failover:"):
            console.print(f"  [yellow]⚠ Failover: {controller.last_route}[/]")
        elif controller.last_route and controller.last_route != "local":
            console.print(f"  [dim]Routed via: {controller.last_route}[/]")
        print_response(result)

        # Warn if a local model snuck commands/writes into a THINK-mode response
        if actual_backend == "local" and args.mode == "think":
            from aicp.guardrails.response import scan_think_mode
            for warning in scan_think_mode(result, Mode(args.mode)):
                print_warning(warning)

        # Warn if the response appears to contain leaked secrets (any mode/backend)
        from aicp.guardrails.response import scan_response_secrets
        for warning in scan_response_secrets(result):
            print_warning(f"SECRET LEAK RISK: {warning}")

        # --speak: convert LLM response to audio via TTS
        if getattr(args, "speak", False) and actual_backend == "local" and result:
            tts_output = Path(args.speak_output) if getattr(args, "speak_output", None) else Path("/tmp/aicp_tts.wav")
            try:
                with spinner("Generating speech..."):
                    backends["local"].speak(result, tts_output)
                console.print(f"  [dim]Audio saved to {tts_output}[/]")
            except Exception as e:
                print_warning(f"TTS failed: {e}")

        return 0
    except Exception as e:
        error_msg = str(e)
        print_error(error_msg)
        alt = "claude" if actual_backend == "local" else "local"
        alt_backend = backends.get(alt)
        if alt_backend and alt_backend.is_available():
            print_warning(f"Try with --backend {alt} instead?")
        return 1


if __name__ == "__main__":
    sys.exit(main())
