"""LocalAI observability — scrape metrics, parse Prometheus, query status.

Provides live metrics from the running LocalAI instance without
requiring an external Prometheus/Grafana stack.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import httpx


def scrape_prometheus(base_url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Scrape and parse LocalAI's /metrics endpoint.

    Returns a dict with key metrics extracted from Prometheus text format.
    """
    try:
        resp = httpx.get(f"{base_url}/metrics", timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "available": False}
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {"error": str(e), "available": False}

    text = resp.text
    return {
        "available": True,
        "go_goroutines": _parse_gauge(text, "go_goroutines"),
        "go_memstats_alloc_bytes": _parse_gauge(text, "go_memstats_alloc_bytes"),
        "go_memstats_sys_bytes": _parse_gauge(text, "go_memstats_sys_bytes"),
        "api_calls": _parse_api_call_histogram(text),
    }


def get_loaded_models(base_url: str, timeout: float = 3.0) -> List[str]:
    """Return list of model IDs from /v1/models."""
    try:
        resp = httpx.get(f"{base_url}/v1/models", timeout=timeout)
        if resp.status_code == 200:
            return [m.get("id", "?") for m in resp.json().get("data", [])]
    except Exception:
        pass
    return []


def get_system_info(base_url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Query LocalAI's /system endpoint for runtime info.

    Returns loaded models (in GPU memory) and installed backends.
    """
    try:
        resp = httpx.get(f"{base_url}/system", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            loaded = [m.get("id", "?") for m in data.get("loaded_models", [])]
            backends = data.get("backends", [])
            return {
                "available": True,
                "loaded_models": loaded,
                "backends": backends,
            }
    except Exception:
        pass
    return {"available": False, "loaded_models": [], "backends": []}


def get_backends_detail(base_url: str, timeout: float = 3.0) -> List[Dict[str, Any]]:
    """Query LocalAI's /backends/ endpoint for installed backend details."""
    try:
        resp = httpx.get(f"{base_url}/backends/", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "name": b.get("Name", "?"),
                    "is_meta": b.get("IsMeta", False),
                    "alias": b.get("Metadata", {}).get("alias", ""),
                }
                for b in data
                if not b.get("IsMeta", False)
            ]
    except Exception:
        pass
    return []


def get_system_status(base_url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Build a comprehensive system status snapshot.

    Combines: model list, Prometheus metrics, system info, and GPU status.
    """
    models = get_loaded_models(base_url, timeout)
    prom = scrape_prometheus(base_url, timeout)
    gpu = get_gpu_status()
    sys_info = get_system_info(base_url, timeout)

    return {
        "localai": {
            "available": prom.get("available", False),
            "url": base_url,
            "models": models,
            "loaded_models": sys_info.get("loaded_models", []),
            "backends": sys_info.get("backends", []),
            "goroutines": prom.get("go_goroutines"),
            "memory_alloc_mb": _bytes_to_mb(prom.get("go_memstats_alloc_bytes")),
            "memory_sys_mb": _bytes_to_mb(prom.get("go_memstats_sys_bytes")),
            "api_calls": prom.get("api_calls", {}),
        },
        "gpu": gpu,
    }


def get_gpu_status() -> Dict[str, Any]:
    """Query nvidia-smi for GPU status."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {"available": False, "error": result.stderr.strip()}

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            return {
                "available": True,
                "name": parts[0],
                "memory_used_mb": int(parts[1]),
                "memory_total_mb": int(parts[2]),
                "memory_used_pct": round(int(parts[1]) / int(parts[2]) * 100, 1) if int(parts[2]) > 0 else 0,
                "utilization_pct": int(parts[3]),
                "temperature_c": int(parts[4]),
            }
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found"}
    except Exception as e:
        return {"available": False, "error": str(e)}
    return {"available": False, "error": "unexpected output"}


def measure_request(
    base_url: str,
    model: str = "hermes",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Send a minimal test request and measure latency breakdown.

    Returns timing for: total, time_to_first_token (if streaming), tokens/sec.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 5,
        "stream": True,
    }

    t0 = time.perf_counter()
    ttft = None
    tokens = 0
    full_response = ""

    try:
        with httpx.stream(
            "POST",
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=timeout,
        ) as resp:
            if resp.status_code >= 400:
                return {"error": f"HTTP {resp.status_code}", "total_ms": 0}

            for line in resp.iter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    if ttft is None:
                        ttft = (time.perf_counter() - t0) * 1000
                    try:
                        import json
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        chunk = delta.get("content", "")
                        if chunk:
                            tokens += 1
                            full_response += chunk
                    except Exception:
                        pass

        total_ms = (time.perf_counter() - t0) * 1000
        gen_ms = total_ms - (ttft or total_ms)

        return {
            "total_ms": round(total_ms, 1),
            "ttft_ms": round(ttft, 1) if ttft is not None else None,
            "generation_ms": round(gen_ms, 1),
            "tokens": tokens,
            "tokens_per_sec": round(tokens / (gen_ms / 1000), 1) if gen_ms > 0 else 0,
            "response": full_response.strip(),
        }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {"error": str(e), "total_ms": 0}


def measure_embedding(
    base_url: str,
    model: str = "nomic-embed",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Benchmark embedding generation speed."""
    text = "The quick brown fox jumps over the lazy dog. " * 10
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/v1/embeddings",
            json={"model": model, "input": text},
            timeout=timeout,
        )
        total_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}", "total_ms": 0}
        data = resp.json()
        dim = len(data["data"][0]["embedding"])
        return {
            "total_ms": round(total_ms, 1),
            "dimensions": dim,
            "chars": len(text),
        }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {"error": str(e), "total_ms": 0}


def measure_rerank(
    base_url: str,
    model: str = "bge-reranker-v2-m3",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Benchmark reranking speed."""
    docs = [
        "Python is a programming language used for web development.",
        "Machine learning is a subset of artificial intelligence.",
        "The weather today is sunny and warm.",
        "Docker containers provide isolated environments.",
        "Neural networks are inspired by biological neurons.",
    ]
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/v1/rerank",
            json={"model": model, "query": "What is AI?", "documents": docs},
            timeout=timeout,
        )
        total_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}", "total_ms": 0}
        data = resp.json()
        results = data.get("results", [])
        return {
            "total_ms": round(total_ms, 1),
            "documents": len(docs),
            "results": len(results),
        }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {"error": str(e), "total_ms": 0}


def measure_grammar(
    base_url: str,
    model: str = "hermes",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Benchmark grammar-constrained generation."""
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Is the sky blue?"}],
                "max_tokens": 5,
                "grammar": 'root ::= ("yes" | "no")',
            },
            timeout=timeout,
        )
        total_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}", "total_ms": 0}
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {
            "total_ms": round(total_ms, 1),
            "response": content.strip(),
        }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {"error": str(e), "total_ms": 0}


# ── Prometheus text format parsing ─────────────────────────────────────────


def _parse_gauge(text: str, metric_name: str) -> Optional[float]:
    """Extract a simple gauge value from Prometheus text."""
    pattern = rf"^{re.escape(metric_name)}\s+([\d.e+\-]+)"
    match = re.search(pattern, text, re.MULTILINE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def _parse_api_call_histogram(text: str) -> Dict[str, Any]:
    """Extract api_call histogram summary."""
    total_pattern = r'api_call_count\{.*?method="(\w+)".*?\}\s+([\d.e+\-]+)'
    sum_pattern = r'api_call_sum\{.*?method="(\w+)".*?\}\s+([\d.e+\-]+)'

    counts: Dict[str, float] = {}
    sums: Dict[str, float] = {}

    for match in re.finditer(total_pattern, text):
        method = match.group(1)
        counts[method] = counts.get(method, 0) + float(match.group(2))

    for match in re.finditer(sum_pattern, text):
        method = match.group(1)
        sums[method] = sums.get(method, 0) + float(match.group(2))

    result: Dict[str, Any] = {}
    for method in set(list(counts.keys()) + list(sums.keys())):
        c = counts.get(method, 0)
        s = sums.get(method, 0)
        result[method] = {
            "count": int(c),
            "total_ms": round(s, 1),
            "avg_ms": round(s / c, 1) if c > 0 else 0,
        }
    return result


def _bytes_to_mb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value / (1024 * 1024), 1)
