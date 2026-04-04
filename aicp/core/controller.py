"""Main controller — routes tasks to backends with mode enforcement.

Features:
  - Mode enforcement (think/edit/act)
  - Multi-backend failover (local → fleet → openrouter → claude)
  - Auto-escalation on low-quality responses (E-M49)
  - Response caching with TTL (E-M50)
  - Token budget enforcement (E-M51)
"""

from __future__ import annotations

import hashlib
import json
import logging
import socket
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from aicp.core.modes import Mode
from aicp.backends.base import Backend
from aicp.core.cluster import (
    check_cluster,
    execute_remote,
    find_best_node,
    load_cluster_config,
)
from aicp.core.history import save_task
from aicp.core.router import intercept_operation, score_response_quality
from aicp.guardrails.checks import run_preflight_checks

logger = logging.getLogger("aicp")


# ---------------------------------------------------------------------------
# Response cache (E-M50)
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    response: str
    timestamp: float
    backend: str
    quality: float


class ResponseCache:
    """Simple in-memory cache for LLM responses.

    Cache key is hash(prompt + mode + backend). TTL-based expiry.
    Helps avoid redundant inference for identical repeated requests.
    """

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 256) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, _CacheEntry] = {}

    @staticmethod
    def _key(prompt: str, mode: str, backend: str) -> str:
        raw = f"{prompt}|{mode}|{backend}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, prompt: str, mode: str, backend: str) -> Optional[str]:
        key = self._key(prompt, mode, backend)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.ttl:
            del self._store[key]
            return None
        return entry.response

    def put(
        self, prompt: str, mode: str, backend: str,
        response: str, quality: float = 0.5,
    ) -> None:
        # Evict oldest if full
        if len(self._store) >= self.max_entries:
            oldest_key = min(self._store, key=lambda k: self._store[k].timestamp)
            del self._store[oldest_key]
        key = self._key(prompt, mode, backend)
        self._store[key] = _CacheEntry(
            response=response,
            timestamp=time.time(),
            backend=backend,
            quality=quality,
        )

    @property
    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()


@dataclass
class Task:
    """A unit of work to send to a backend."""

    prompt: str
    mode: Mode
    project_path: Path
    backend_name: str = "local"


def _local_ips() -> Set[str]:
    """Return a set of IP addresses belonging to this machine."""
    ips = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        ips.add(hostname.lower())
        for info in socket.getaddrinfo(hostname, None):
            ips.add(info[4][0])
    except OSError:
        pass
    return ips


class Controller:
    """Orchestrates backend selection, mode enforcement, and task execution.

    Features:
      - KB context injection (navigator queries LocalAI Collections)
      - Prometheus metrics (per-backend request/token/cost tracking)
      - Response caching (skip inference for repeated prompts)
      - Quality-based auto-escalation (LocalAI garbage → retry with Claude)
      - Token budget tracking (warn/block when budget exhausted)
    """

    def __init__(
        self,
        backends: Dict[str, Backend],
        config: Dict[str, Any] = None,
        metrics_collector=None,
    ) -> None:
        self.backends = backends
        self.config = config or {}
        self._fleet_checked = False
        self._fleet_nodes: list = []
        self.last_route: Optional[str] = None
        # Response cache (E-M50)
        cache_cfg = self.config.get("cache", {})
        self._cache = ResponseCache(
            ttl_seconds=cache_cfg.get("ttl_seconds", 300.0),
            max_entries=cache_cfg.get("max_entries", 256),
        )
        self.cache_enabled = cache_cfg.get("enabled", True)
        # Quality threshold for auto-escalation (E-M49)
        self.quality_threshold = self.config.get("quality_threshold", 0.25)
        # Token budget (E-M51)
        budget_cfg = self.config.get("budget", {})
        self.budget_limit = budget_cfg.get("max_tokens_per_session", 0)  # 0 = unlimited
        self.tokens_used = 0
        # Prometheus metrics collector
        self._metrics = metrics_collector
        # Knowledge map navigator (queries LocalAI Collections)
        self._navigator = None
        if self.config.get("rag", {}).get("enabled", False):
            try:
                from aicp.core.navigator import Navigator
                self._navigator = Navigator(Path("."), config=self.config)
            except Exception:
                pass

    def _check_fleet(self) -> None:
        """Load and health-check fleet nodes (cached per controller lifetime)."""
        if self._fleet_checked:
            return
        self._fleet_checked = True
        nodes = load_cluster_config(self.config)
        if nodes:
            self._fleet_nodes = check_cluster(nodes)
            online = [n for n in self._fleet_nodes if n.online]
            logger.info("Fleet: %d nodes loaded, %d online", len(nodes), len(online))

    def _try_fleet_route(self, task: Task) -> Optional[str]:
        """Attempt to route the task to the best fleet node.

        Returns the response string if routed remotely, None if we should
        execute locally.
        """
        cluster_cfg = self.config.get("cluster", {})
        if not cluster_cfg.get("auto_route", False):
            return None

        self._check_fleet()
        if not self._fleet_nodes:
            return None

        best = find_best_node(self._fleet_nodes, model_name=None)
        if best is None:
            logger.warning("Fleet: no online nodes, falling back to local")
            return None

        # If best node is this machine, execute locally
        if best.host in _local_ips() or best.name.lower() == socket.gethostname().lower():
            self.last_route = f"local ({best.name})"
            return None

        # Route to remote node
        logger.info("Fleet: routing to %s (%s:%d)", best.name, best.host, best.port)
        self.last_route = f"fleet:{best.name} ({best.host})"

        result_dict = execute_remote(
            best,
            prompt=task.prompt,
            mode=task.mode.value,
            backend=task.backend_name,
            project=str(task.project_path),
        )
        return result_dict.get("response", result_dict.get("result", str(result_dict)))

    def _try_fleet_failover(self, task: Task) -> Optional[str]:
        """Try to execute on any available fleet peer (failover).

        Called when the local backend has failed. Tries each online remote
        node in order of free VRAM.
        """
        cluster_cfg = self.config.get("cluster", {})
        if not cluster_cfg.get("auto_route", False):
            return None

        self._check_fleet()
        local_ips = _local_ips()
        hostname = socket.gethostname().lower()

        # Get all online remote nodes
        remote_nodes = [
            n for n in self._fleet_nodes
            if n.online and n.host not in local_ips and n.name.lower() != hostname
        ]
        if not remote_nodes:
            return None

        for node in remote_nodes:
            try:
                logger.info("Failover: trying %s (%s:%d)", node.name, node.host, node.port)
                result_dict = execute_remote(
                    node,
                    prompt=task.prompt,
                    mode=task.mode.value,
                    backend=task.backend_name,
                    project=str(task.project_path),
                )
                self.last_route = f"failover:fleet:{node.name} ({node.host})"
                return result_dict.get("response", result_dict.get("result", str(result_dict)))
            except Exception as e:
                logger.warning("Failover: %s failed: %s", node.name, e)
                continue

        return None

    def _try_quality_escalation(self, task: Task, result: str) -> Optional[str]:
        """Check response quality; escalate to a better backend if too low.

        Only escalates from local → openrouter → claude. Never re-escalates
        on the same tier or downward. Returns improved result or None.
        """
        quality = score_response_quality(result, task.prompt)
        if quality >= self.quality_threshold:
            return None

        logger.warning(
            "Low quality response (%.2f < %.2f) from %s — escalating",
            quality, self.quality_threshold, task.backend_name,
        )

        # Escalation chain based on current backend
        escalation_order = []
        if task.backend_name == "local":
            or_backend = self.backends.get("openrouter")
            if or_backend:
                escalation_order.append(("openrouter", or_backend))
            claude_backend = self.backends.get("claude")
            if claude_backend:
                escalation_order.append(("claude", claude_backend))
        elif task.backend_name == "openrouter":
            claude_backend = self.backends.get("claude")
            if claude_backend:
                escalation_order.append(("claude", claude_backend))

        for name, backend in escalation_order:
            try:
                logger.info("Quality escalation: trying %s", name)
                if self._metrics:
                    self._metrics.record_escalation(task.backend_name)
                better = backend.execute(task.prompt, task.mode, task.project_path)
                better_quality = score_response_quality(better, task.prompt)
                if better_quality > quality:
                    self.last_route = f"escalated:{name} (quality {quality:.2f}→{better_quality:.2f})"
                    return better
            except Exception as e:
                logger.warning("Quality escalation to %s failed: %s", name, e)
                continue

        return None

    def run(self, task: Task) -> str:
        """Run a task through the selected backend with mode enforcement."""
        issues = run_preflight_checks(
            task.project_path, task.mode, task.backend_name, self.config
        )

        errors = [i for i in issues if not i.startswith("WARNING:")]
        warnings = [i for i in issues if i.startswith("WARNING:")]

        if errors:
            raise ValueError("\n".join(errors))

        for warning in warnings:
            print(warning, file=sys.stderr)

        # Budget enforcement (E-M51)
        if self.budget_limit > 0 and self.tokens_used >= self.budget_limit:
            raise ValueError(
                f"Token budget exhausted ({self.tokens_used}/{self.budget_limit}). "
                "Increase budget or start a new session."
            )

        # Cache check (E-M50)
        if self.cache_enabled:
            cached = self._cache.get(task.prompt, task.mode.value, task.backend_name)
            if cached is not None:
                self.last_route = "cache"
                logger.info("Cache hit (0 tokens)")
                if self._metrics:
                    self._metrics.record_cache_hit(task.backend_name)
                return cached

        start = datetime.utcnow()

        logger.info(json.dumps({
            "event": "task_start",
            "mode": task.mode.value,
            "backend": task.backend_name,
            "project": str(task.project_path),
            "timestamp": start.isoformat(),
        }))

        error = None
        result = ""
        failover_enabled = self.config.get("cluster", {}).get("auto_route", False)

        try:
            # Zero-token intercept: heartbeats, status checks bypass LLM
            intercepted = intercept_operation(task.prompt, self.config)
            if intercepted is not None:
                self.last_route = "intercepted"
                result = intercepted
                logger.info("Intercepted operation (0 tokens): %s", result[:80])
            # Try fleet routing (if auto_route is enabled)
            elif (fleet_result := self._try_fleet_route(task)) is not None:
                result = fleet_result
            else:
                # KB context injection for local backend
                effective_prompt = task.prompt
                if self._navigator and task.backend_name == "local":
                    try:
                        augmented = self._navigator.assemble_context(
                            task.prompt, task.mode,
                            model=getattr(self.backends.get("local"), "model", ""),
                        )
                        if augmented != task.prompt:
                            effective_prompt = augmented
                            logger.info("Navigator injected KB context (%d → %d chars)",
                                        len(task.prompt), len(augmented))
                    except Exception:
                        pass

                # Execute
                self.last_route = "local"
                backend = self.backends.get(task.backend_name)
                if backend is None:
                    raise ValueError(f"Unknown backend: {task.backend_name}")

                try:
                    result = backend.execute(effective_prompt, task.mode, task.project_path)

                    # Auto-escalation on low quality (E-M49)
                    if task.backend_name in ("local", "openrouter"):
                        better = self._try_quality_escalation(task, result)
                        if better is not None:
                            result = better

                except Exception as local_err:
                    if not failover_enabled:
                        raise

                    # Failover chain: local → fleet peer → openrouter → claude
                    logger.warning("Local backend failed: %s — trying failover", local_err)

                    # Step 1: try fleet peers
                    peer_result = self._try_fleet_failover(task)
                    if peer_result is not None:
                        result = peer_result
                    else:
                        # Step 2: try OpenRouter (free middle tier)
                        openrouter = self.backends.get("openrouter")
                        if openrouter and task.backend_name != "openrouter":
                            try:
                                logger.info("Failover: trying OpenRouter")
                                self.last_route = "failover:openrouter"
                                result = openrouter.execute(
                                    task.prompt, task.mode, task.project_path
                                )
                            except Exception as or_err:
                                logger.warning("Failover: OpenRouter failed: %s", or_err)
                                result = None
                        else:
                            result = None

                        # Step 3: try Claude (if OpenRouter also failed)
                        if result is None:
                            claude = self.backends.get("claude")
                            if claude and task.backend_name != "claude":
                                try:
                                    logger.info("Failover: escalating to Claude")
                                    self.last_route = "failover:claude"
                                    result = claude.execute(
                                        task.prompt, task.mode, task.project_path
                                    )
                                except Exception as claude_err:
                                    logger.error("Failover: Claude also failed: %s", claude_err)
                                    raise local_err from None
                            else:
                                raise local_err from None

        except Exception as e:
            error = str(e)
            raise
        finally:
            elapsed = (datetime.utcnow() - start).total_seconds()

            # Collect usage metadata from backend (populated by execute())
            backend_obj = self.backends.get(task.backend_name)
            usage = getattr(backend_obj, "last_usage", {}) if backend_obj else {}

            logger.info(json.dumps({
                "event": "task_complete",
                "mode": task.mode.value,
                "backend": task.backend_name,
                "route": self.last_route,
                "duration_seconds": elapsed,
                "response_length": len(result or ""),
                "tokens": usage,
                "timestamp": datetime.utcnow().isoformat(),
            }))
            # Track token budget (E-M51)
            total_tokens = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
            self.tokens_used += total_tokens

            # Prometheus metrics
            if self._metrics:
                quality = score_response_quality(result or "", task.prompt) if result else 0.0
                self._metrics.record_request(
                    backend=task.backend_name,
                    model=usage.get("model", ""),
                    quality=quality,
                    total_tokens=total_tokens,
                    cost_usd=usage.get("estimated_cost_usd") or 0.0,
                    latency_ms=elapsed * 1000,
                    prompt_tokens=usage.get("prompt_tokens") or 0,
                    completion_tokens=usage.get("completion_tokens") or 0,
                    route=self.last_route or "",
                    error=bool(error),
                )

            save_task(
                prompt=task.prompt,
                mode=task.mode.value,
                backend=task.backend_name,
                project=str(task.project_path),
                response=result or "",
                duration_seconds=elapsed,
                error=error,
                model=usage.get("model"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                estimated_cost_usd=usage.get("estimated_cost_usd"),
                route=self.last_route,
            )

        # Cache successful responses (E-M50)
        if self.cache_enabled and result and not error:
            quality = score_response_quality(result, task.prompt)
            self._cache.put(task.prompt, task.mode.value, task.backend_name, result, quality)

        return result
