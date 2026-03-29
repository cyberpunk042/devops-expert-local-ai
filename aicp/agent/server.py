"""AICP agent daemon — lightweight HTTP server for remote task execution.

Run with: aicp-agent --port 9100 --token <shared-secret>
"""

from __future__ import annotations

import json
import hashlib
import hmac
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

from aicp.backends.localai import LocalAIBackend
from aicp.backends.claude_code import ClaudeCodeBackend
from aicp.config.loader import load_config, get_backend_config
from aicp.core.controller import Controller, Task
from aicp.core.gpu import detect_gpus
from aicp.core.models import list_models
from aicp.core.modes import Mode


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the AICP agent daemon."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond_json(200, {"status": "ok"})
        elif self.path == "/status":
            self._handle_status()
        else:
            self._respond_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/task":
            self._handle_task()
        else:
            self._respond_json(404, {"error": "not found"})

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

            start = time.time()
            result = controller.run(task)
            elapsed = time.time() - start

            backend = controller.backends.get(backend_name)
            usage = getattr(backend, "last_usage", {}) if backend else {}

            self._respond_json(200, {
                "result": result,
                "duration_seconds": round(elapsed, 2),
                "usage": usage,
            })

        except ValueError as e:
            self._respond_json(400, {"error": str(e)})
        except Exception as e:
            self._respond_json(500, {"error": str(e)})

    def _check_auth(self) -> bool:
        """Validate shared-secret auth token."""
        expected = self.server.auth_token  # type: ignore
        if not expected:
            return True  # no auth configured
        provided = self.headers.get("Authorization", "").replace("Bearer ", "")
        return hmac.compare_digest(provided, expected)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _respond_json(self, status: int, data: Dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_agent(port: int = 9100, token: str = "", config_path: Optional[Path] = None) -> None:
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

    print(f"AICP agent listening on port {port}")
    if token:
        print("Auth: token required")
    else:
        print("Auth: NONE (use --token for production)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
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
