"""Tests for the AICP agent server HTTP handler."""

import io
import json
from unittest.mock import MagicMock, patch

from aicp.agent.server import AgentHandler, load_away_summary, save_away_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(
    method: str = "GET",
    path: str = "/health",
    body: dict | None = None,
    auth_token: str = "",
    headers: dict | None = None,
    controller: MagicMock | None = None,
    warming: bool = False,
) -> tuple[AgentHandler, io.BytesIO]:
    """Create an AgentHandler with mocked request/response IO."""
    body_bytes = json.dumps(body).encode() if body else b""

    # rfile contains just the body (headers are already parsed by BaseHTTPRequestHandler)
    rfile = io.BytesIO(body_bytes)
    wfile = io.BytesIO()

    # Mock the server object
    server = MagicMock()
    server.auth_token = auth_token
    server._warming = warming
    server._warming_model = "qwen3-8b" if warming else ""
    if controller is None:
        controller = MagicMock()
        controller.backends = {}
    server.controller = controller

    # Create handler without triggering __init__ (which calls handle())
    handler = AgentHandler.__new__(AgentHandler)
    handler.server = server
    handler.rfile = rfile
    handler.wfile = wfile
    handler.path = path
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.close_connection = True

    # Build headers as http.client.HTTPMessage
    from email.message import Message
    msg = Message()
    msg["Content-Length"] = str(len(body_bytes))
    msg["Content-Type"] = "application/json"
    if headers:
        for k, v in headers.items():
            msg[k] = v
    handler.headers = msg

    return handler, wfile


def _parse_response(wfile: io.BytesIO) -> tuple[int, dict]:
    """Parse status code and JSON body from raw HTTP response."""
    raw = wfile.getvalue().decode(errors="replace")
    # Extract status code from first line
    first_line = raw.split("\r\n")[0]
    # Format: "HTTP/1.1 200 OK"  or just status code if send_response wrote it
    parts = first_line.split()
    if len(parts) >= 2:
        status = int(parts[1])
    else:
        status = 0

    # Extract JSON body (after double CRLF)
    if "\r\n\r\n" in raw:
        body_str = raw.split("\r\n\r\n", 1)[1]
    else:
        body_str = "{}"

    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        body = {}

    return status, body


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:

    def test_health_ok(self):
        backend = MagicMock()
        backend.is_available.return_value = True
        controller = MagicMock()
        controller.backends = {"local": backend}

        handler, wfile = _make_handler(path="/health", controller=controller)
        handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["status"] == "ok"
        assert body["backends"]["local"] is True

    def test_health_degraded(self):
        backend = MagicMock()
        backend.is_available.return_value = False
        controller = MagicMock()
        controller.backends = {"local": backend}

        handler, wfile = _make_handler(path="/health", controller=controller)
        handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["status"] == "degraded"

    def test_health_warming(self):
        handler, wfile = _make_handler(path="/health", warming=True)
        handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["status"] == "warming"


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


class TestStatus:

    @patch("aicp.agent.server.list_models", return_value=[])
    @patch("aicp.agent.server.detect_gpus", return_value=[])
    def test_status_returns_info(self, mock_gpus, mock_models):
        handler, wfile = _make_handler(path="/status")
        handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert "gpus" in body
        assert "models" in body
        assert "backends" in body


# ---------------------------------------------------------------------------
# Task endpoint
# ---------------------------------------------------------------------------


class TestTask:

    def test_task_requires_auth(self):
        handler, wfile = _make_handler(
            method="POST", path="/task",
            body={"prompt": "test"},
            auth_token="secret123",
            # No Authorization header
        )
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 401
        assert "unauthorized" in body.get("error", "").lower()

    def test_task_accepts_valid_auth(self):
        controller = MagicMock()
        controller.run.return_value = "result"
        controller.backends = {"local": MagicMock(last_usage={})}

        handler, wfile = _make_handler(
            method="POST", path="/task",
            body={"prompt": "test", "mode": "think"},
            auth_token="secret123",
            headers={"Authorization": "Bearer secret123"},
            controller=controller,
        )
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["result"] == "result"

    def test_task_empty_prompt_returns_400(self):
        handler, wfile = _make_handler(
            method="POST", path="/task",
            body={"prompt": ""},
        )
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 400
        assert "missing prompt" in body.get("error", "").lower()

    def test_task_invalid_mode_returns_400(self):
        handler, wfile = _make_handler(
            method="POST", path="/task",
            body={"prompt": "test", "mode": "invalid_mode"},
        )
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 400
        assert "invalid mode" in body.get("error", "").lower()

    def test_task_controller_error_returns_500(self):
        controller = MagicMock()
        controller.run.side_effect = RuntimeError("backend crashed")
        controller.backends = {}

        handler, wfile = _make_handler(
            method="POST", path="/task",
            body={"prompt": "test", "mode": "think"},
            controller=controller,
        )
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 500
        assert "crashed" in body.get("error", "")


# ---------------------------------------------------------------------------
# Away summary
# ---------------------------------------------------------------------------


class TestAwaySummary:

    def test_away_summary_returns_saved(self):
        with patch("aicp.agent.server.load_away_summary", return_value="Last session context"):
            handler, wfile = _make_handler(path="/away-summary")
            handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["summary"] == "Last session context"


# ---------------------------------------------------------------------------
# Tasks list
# ---------------------------------------------------------------------------


class TestTasksList:

    def test_tasks_returns_list(self):
        mock_mgr = MagicMock()
        mock_mgr.list_tasks.return_value = []
        mock_mgr.active_count = 0
        mock_mgr.total_count = 0

        with patch("aicp.agent.server.get_task_manager", return_value=mock_mgr):
            handler, wfile = _make_handler(path="/tasks")
            handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 200
        assert body["tasks"] == []
        assert body["active"] == 0


# ---------------------------------------------------------------------------
# Unknown routes
# ---------------------------------------------------------------------------


class TestUnknownRoutes:

    def test_unknown_get_returns_404(self):
        handler, wfile = _make_handler(path="/unknown")
        handler.do_GET()

        status, body = _parse_response(wfile)
        assert status == 404

    def test_unknown_post_returns_404(self):
        handler, wfile = _make_handler(method="POST", path="/unknown")
        handler.do_POST()

        status, body = _parse_response(wfile)
        assert status == 404


# ---------------------------------------------------------------------------
# Away summary persistence
# ---------------------------------------------------------------------------


class TestAwaySummaryPersistence:

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "away.txt"
        with patch("aicp.agent.server._AWAY_SUMMARY_PATH", path):
            save_away_summary("test summary")
            result = load_away_summary()
        assert result == "test summary"

    def test_load_empty_when_no_file(self, tmp_path):
        path = tmp_path / "nonexistent.txt"
        with patch("aicp.agent.server._AWAY_SUMMARY_PATH", path):
            result = load_away_summary()
        assert result == ""
