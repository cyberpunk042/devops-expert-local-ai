"""AICP agent client — sends tasks to remote AICP nodes."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class AgentClient:
    """Client for communicating with a remote AICP agent daemon."""

    def __init__(self, host: str, port: int, token: str = "") -> None:
        self.base_url = f"http://{host}:{port}"
        self.token = token

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def health(self) -> bool:
        """Check if the remote agent is healthy."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return r.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError,
                httpx.RemoteProtocolError, OSError):
            return False

    def status(self) -> Optional[Dict[str, Any]]:
        """Get remote node status (GPUs, models, backends)."""
        try:
            r = httpx.get(f"{self.base_url}/status", timeout=5.0)
            if r.status_code == 200:
                return r.json()
            return None
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError,
                httpx.RemoteProtocolError, OSError):
            return None

    def execute_task(
        self,
        prompt: str,
        mode: str = "think",
        backend: str = "local",
        project: str = ".",
    ) -> Dict[str, Any]:
        """Send a task to the remote agent. Returns result dict."""
        r = httpx.post(
            f"{self.base_url}/task",
            json={
                "prompt": prompt,
                "mode": mode,
                "backend": backend,
                "project": project,
                "remote": True,
            },
            headers=self._headers(),
            timeout=300.0,
        )
        r.raise_for_status()
        return r.json()

    def __repr__(self) -> str:
        return f"AgentClient({self.base_url})"
