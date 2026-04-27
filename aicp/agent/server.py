"""AICP agent daemon — lightweight HTTP server for remote task execution.

Run with: aicp-agent --port 9100 --token <shared-secret>
"""

from __future__ import annotations

import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.backends.localai import LocalAIBackend
from aicp.config.loader import get_backend_config, load_config
from aicp.core.controller import Controller, Task
from aicp.core.events import get_emitter
from aicp.core.gpu import detect_gpus
from aicp.core.models import list_models
from aicp.core.modes import Mode
from aicp.core.tasks import TaskType, get_task_manager


def _generate_away_summary(config: dict) -> str:
    """Generate a brief summary of recent work for agent restart context.

    Returns 1-3 sentences: what was being done + next step.
    Falls back to heuristic if no LLM is available.
    """
    try:
        from aicp.core.history import list_tasks
        tasks = list_tasks(count=10)
        if not tasks:
            return ""

        # Heuristic summary from recent tasks
        recent = tasks[:5]
        modes = [t.get("mode", "") for t in recent]
        errors = [t for t in recent if t.get("error")]

        summary_parts = []

        # What was being done
        if recent:
            last = recent[0]
            prompt_preview = (last.get("prompt") or "")[:100]
            summary_parts.append(f"Last task: {prompt_preview}")

        # Error context
        if errors:
            last_error = errors[0].get("error", "")[:100]
            summary_parts.append(f"Recent error: {last_error}")

        # Patterns
        mode_counts = {}
        for m in modes:
            mode_counts[m] = mode_counts.get(m, 0) + 1
        dominant_mode = max(mode_counts, key=mode_counts.get) if mode_counts else "think"
        summary_parts.append(f"Primary mode: {dominant_mode}")

        return " | ".join(summary_parts)
    except Exception as e:
        return f"(summary unavailable: {e})"


_AWAY_SUMMARY_PATH = Path(os.environ.get(
    "AICP_AWAY_SUMMARY", Path.home() / ".aicp" / "away_summary.txt"
))


def save_away_summary(summary: str) -> None:
    """Persist away summary to disk."""
    try:
        _AWAY_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AWAY_SUMMARY_PATH.write_text(summary)
    except OSError:
        pass


def load_away_summary() -> str:
    """Load the last away summary from disk."""
    try:
        if _AWAY_SUMMARY_PATH.exists():
            return _AWAY_SUMMARY_PATH.read_text().strip()
    except OSError:
        pass
    return ""


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the AICP agent daemon."""

    def do_GET(self) -> None:
        if self.path == "/health" or self.path.startswith("/health?"):
            self._handle_health()
        elif self.path == "/status":
            self._handle_status()
        elif self.path == "/away-summary":
            self._handle_away_summary()
        elif self.path == "/tasks" or self.path.startswith("/tasks?"):
            self._handle_tasks()
        else:
            self._respond_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/task":
            self._handle_task()
        else:
            self._respond_json(404, {"error": "not found"})

    def _handle_health(self) -> None:
        """Return health status including backend availability and warmup state."""
        warming = getattr(self.server, "_warming", False)
        warming_model = getattr(self.server, "_warming_model", "")

        if warming:
            self._respond_json(200, {
                "status": "warming",
                "model": warming_model,
                "backends": {},
            })
            return

        # Check backend availability (cached by controller's circuit breakers)
        backend_status = {}
        controller = getattr(self.server, "controller", None)
        if controller:
            for name, backend in controller.backends.items():
                try:
                    backend_status[name] = backend.is_available()
                except Exception:
                    backend_status[name] = False

        all_ok = all(backend_status.values()) if backend_status else True
        self._respond_json(200, {
            "status": "ok" if all_ok else "degraded",
            "backends": backend_status,
            "warming": False,
        })

    def _handle_status(self) -> None:
        """Return node status: GPUs, models, availability."""
        gpus = detect_gpus()
        models = list_models()

        gpu_info = []
        for g in gpus:
            gpu_info.append({
                "index": g.index, "name": g.name,
                "vram_total_mb": g.vram_total_mb, "vram_free_mb": g.vram_free_mb,
            })

        model_info = [{"name": m.name, "size_mb": m.gguf_size_mb} for m in models]

        self._respond_json(200, {
            "gpus": gpu_info,
            "models": model_info,
            "backends": ["local", "claude"],
        })

    def _handle_task(self) -> None:
        """Execute a task and return the result."""
        if not self._check_auth():
            self._respond_json(401, {"error": "unauthorized"})
            return

        try:
            body = self._read_body()
            prompt = body.get("prompt", "")
            mode_str = body.get("mode", "think")
            backend_name = body.get("backend", "local")
            project = body.get("project", ".")
            is_remote = body.get("remote", False)

            if not prompt:
                self._respond_json(400, {"error": "missing prompt"})
                return

            try:
                mode = Mode(mode_str)
            except ValueError:
                self._respond_json(400, {"error": f"invalid mode: {mode_str}"})
                return

            controller = self.server.controller  # type: ignore

            # If this task came from another fleet node, disable auto_route
            # to prevent recursive routing loops
            if is_remote:
                controller._fleet_checked = True
                controller._fleet_nodes = []

            task = Task(
                prompt=prompt,
                mode=mode,
                project_path=Path(project).resolve(),
                backend_name=backend_name,
            )

            # Register task in lifecycle manager
            mgr = get_task_manager()
            task_state = mgr.register(
                prompt=prompt,
                task_type=TaskType.INFERENCE,
                mode=mode_str,
                backend=backend_name,
                project=project,
            )
            mgr.start(task_state.id)

            start = time.time()
            try:
                result = controller.run(task)
                elapsed = time.time() - start
                mgr.complete(task_state.id, result[:200])
            except Exception as run_err:
                elapsed = time.time() - start
                mgr.fail(task_state.id, str(run_err))
                raise

            backend = controller.backends.get(backend_name)
            usage = getattr(backend, "last_usage", {}) if backend else {}

            # Emit progress event
            get_emitter().emit("task_complete", {
                "task_id": task_state.id,
                "duration": round(elapsed, 2),
                "backend": backend_name,
                "tokens": usage.get("total_tokens", 0),
            })

            self._respond_json(200, {
                "result": result,
                "task_id": task_state.id,
                "duration_seconds": round(elapsed, 2),
                "usage": usage,
            })

        except ValueError as e:
            self._respond_json(400, {"error": str(e)})
        except Exception as e:
            self._respond_json(500, {"error": str(e)})

    def _handle_away_summary(self) -> None:
        """Return the away summary for agent restart context."""
        summary = load_away_summary()
        self._respond_json(200, {"summary": summary})

    def _handle_tasks(self) -> None:
        """Return task list from the task manager."""
        mgr = get_task_manager()
        tasks = mgr.list_tasks(limit=20)
        self._respond_json(200, {
            "tasks": [t.to_dict() for t in tasks],
            "active": mgr.active_count,
            "total": mgr.total_count,
        })

    def _check_auth(self) -> bool:
        """Validate shared-secret auth token."""
        expected = self.server.auth_token  # type: ignore
        if not expected:
            return True  # no auth configured
        provided = self.headers.get("Authorization", "").replace("Bearer ", "")
        return hmac.compare_digest(provided, expected)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _respond_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_agent(port: int = 9100, token: str = "", config_path: Path | None = None) -> None:
    """Start the AICP agent daemon."""
    config = load_config(config_path) if config_path else load_config()

    local_cfg = get_backend_config(config, "local")
    claude_cfg = get_backend_config(config, "claude")

    backends = {
        "local": LocalAIBackend(
            base_url=local_cfg.get("base_url", "http://localhost:8090"),
            model=local_cfg.get("model", "default"),
            api_key=local_cfg.get("api_key", ""),
            temperature=local_cfg.get("temperature"),
            top_p=local_cfg.get("top_p"),
            top_k=local_cfg.get("top_k"),
            repeat_penalty=local_cfg.get("repeat_penalty"),
            embedding_model=local_cfg.get("embedding_model", ""),
            code_model=local_cfg.get("code_model", ""),
            vision_model=local_cfg.get("vision_model", ""),
            auto_route=local_cfg.get("auto_route", False),
        ),
        "claude": ClaudeCodeBackend(
            model=claude_cfg.get("model", "opus"),
            max_turns=claude_cfg.get("max_turns", 10),
            timeout=claude_cfg.get("timeout", 300),
        ),
    }

    controller = Controller(backends, config=config)

    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    server.controller = controller  # type: ignore
    server.auth_token = token  # type: ignore
    server._warming = False  # type: ignore
    server._warming_model = ""  # type: ignore

    print(f"AICP agent listening on port {port}")
    if token:
        print("Auth: token required")
    else:
        print("Auth: NONE (use --token for production)")

    # Startup model pre-warming (Stage 4 Phase 2)
    warmup_cfg = config.get("warmup", {})
    if warmup_cfg.get("enabled", False):
        warmup_models = warmup_cfg.get("models", [])
        warmup_timeout = warmup_cfg.get("timeout", 120)
        local_backend = backends.get("local")

        if warmup_models and local_backend and hasattr(local_backend, "model_warmup"):
            import threading

            def _do_warmup():
                server._warming = True  # type: ignore
                per_model_timeout = warmup_timeout / max(len(warmup_models), 1)
                for model_name in warmup_models:
                    server._warming_model = model_name  # type: ignore
                    print(f"Warming up model: {model_name}...")
                    try:
                        result = local_backend.model_warmup(
                            model_name=model_name,
                            timeout=per_model_timeout,
                        )
                        if result.get("loaded"):
                            dur = result.get("duration_ms", 0)
                            already = " (already loaded)" if result.get("already_loaded") else ""
                            print(f"  {model_name}: warm in {dur}ms{already}")
                        else:
                            print(f"  {model_name}: WARNING — {result.get('error', 'unknown')}")
                    except Exception as e:
                        print(f"  {model_name}: WARNING — warmup failed: {e}")
                server._warming = False  # type: ignore
                server._warming_model = ""  # type: ignore
                print("Warmup complete. Ready for requests.")

            warmup_thread = threading.Thread(target=_do_warmup, daemon=True)
            warmup_thread.start()

    # Load away summary from previous session
    away = load_away_summary()
    if away:
        print(f"Previous session: {away[:120]}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        # Generate away summary before exit
        summary = _generate_away_summary(config)
        if summary:
            save_away_summary(summary)
            print(f"Away summary saved: {summary[:100]}")
        server.server_close()


def _cli_main() -> None:
    """Entry point for aicp-agent CLI."""
    import argparse
    import os
    parser = argparse.ArgumentParser(prog="aicp-agent", description="AICP agent daemon")
    parser.add_argument("--port", "-p", type=int, default=9100, help="Port (default: 9100)")
    parser.add_argument("--token", "-t", default="", help="Auth token")
    parser.add_argument("--config", type=Path, default=None, help="Config file")
    args = parser.parse_args()
    # CLI --token takes precedence, then env var, then empty (no auth)
    token = args.token or os.environ.get("AICP_AGENT_SECRET", "")
    run_agent(port=args.port, token=token, config_path=args.config)
