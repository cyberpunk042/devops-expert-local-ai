"""LocalAI backend — calls a local OpenAI-compatible API."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Iterator, List, Optional

import httpx

from aicp.backends.base import Backend
from aicp.core.context import build_project_context
from aicp.core.modes import Mode

# Keywords that suggest a code-focused task → route to code model
_CODE_KEYWORDS = re.compile(
    r"\b(refactor|implement|write\s+code|fix\s+bug|debug|function|class\s+\w|"
    r"def\s+\w|import\s+\w|syntax|compile|runtime\s+error|traceback|"
    r"pull\s+request|PR|commit|git\s+diff|code\s+review|unittest|pytest)\b",
    re.IGNORECASE,
)

# How long to wait for a model to finish loading on cold start
_COLD_START_TIMEOUT = 60.0   # seconds
_COLD_START_INTERVAL = 5.0   # seconds between polls


class LocalAIBackend(Backend):
    """Backend that talks to a LocalAI instance via OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8090",
        model: str = "default",
        max_tokens: int = 2048,
        api_key: str = "",
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        embedding_model: str = "",
        code_model: str = "",
        vision_model: str = "",
        auto_route: bool = False,
        cache_prompt: bool = True,
        # Specialized model overrides (use config value or built-in default)
        reranker_model: str = "",
        image_model: str = "",
        sound_model: str = "",
        whisper_model: str = "",
        tts_model: str = "",
        # Advanced sampling (llama.cpp)
        mirostat: Optional[int] = None,
        mirostat_tau: Optional[float] = None,
        mirostat_eta: Optional[float] = None,
        typical_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        # Mode-aware sampling profiles (overrides _MODE_SAMPLING defaults)
        mode_profiles: Optional[dict] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.embedding_model = embedding_model
        self.code_model = code_model
        self.vision_model = vision_model
        self.auto_route = auto_route
        self.cache_prompt = cache_prompt
        # Specialized models (fallback to sane defaults)
        self.reranker_model = reranker_model or "bge-reranker-v2-m3"
        self.image_model = image_model or "stablediffusion"
        self.sound_model = sound_model or "transformers-musicgen"
        self.whisper_model = whisper_model or "whisper-1"
        self.tts_model = tts_model or "piper-tts"
        # Advanced sampling
        self.mirostat = mirostat
        self.mirostat_tau = mirostat_tau
        self.mirostat_eta = mirostat_eta
        self.typical_p = typical_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        # Session-wide seed for reproducible inference (None = random)
        self.seed: Optional[int] = None
        # Mode profiles: deep-merge user config over built-in defaults
        if mode_profiles:
            merged = {}
            for mode_name in set(list(self._MODE_SAMPLING) + list(mode_profiles)):
                base = dict(self._MODE_SAMPLING.get(mode_name, {}))
                base.update(mode_profiles.get(mode_name, {}))
                merged[mode_name] = base
            self._MODE_SAMPLING = merged

    @property
    def name(self) -> str:
        return "local"

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False

    def status_detail(self) -> str:
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id", "?") for m in data.get("data", [])]
                model_list = ", ".join(models[:5]) if models else "no models loaded"
                return f"OK ({self.base_url}, models: {model_list})"
            return f"ERROR: HTTP {resp.status_code} from {self.base_url}/v1/models"
        except httpx.ConnectError:
            return f"UNAVAILABLE: cannot connect to {self.base_url}"
        except httpx.TimeoutException:
            return f"UNAVAILABLE: timeout connecting to {self.base_url}"
        except Exception as e:
            return f"UNAVAILABLE: {e}"

    def _headers(self) -> dict[str, str]:
        """Build request headers, including API key if configured."""
        h: dict[str, str] = {}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _sampling_params(self) -> dict:
        """Build optional sampling overrides for the request payload."""
        params: dict = {}
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        if self.repeat_penalty is not None:
            params["repeat_penalty"] = self.repeat_penalty
        if self.cache_prompt:
            params["cache_prompt"] = True
        # Advanced sampling (llama.cpp)
        if self.mirostat is not None:
            params["mirostat"] = self.mirostat
        if self.mirostat_tau is not None:
            params["mirostat_tau"] = self.mirostat_tau
        if self.mirostat_eta is not None:
            params["mirostat_eta"] = self.mirostat_eta
        if self.typical_p is not None:
            params["typical_p"] = self.typical_p
        if self.frequency_penalty is not None:
            params["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            params["presence_penalty"] = self.presence_penalty
        return params

    def _select_model(self, prompt: str) -> str:
        """Pick the best model for this prompt.

        Returns the model name to use. When auto_route is off (default),
        always returns self.model.
        """
        if not self.auto_route:
            return self.model
        if self.code_model and _CODE_KEYWORDS.search(prompt):
            return self.code_model
        return self.model

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses the configured embedding_model (falls back to self.model).
        """
        model = self.embedding_model or self.model
        payload = {"model": model, "input": text}
        resp = httpx.post(
            f"{self.base_url}/v1/embeddings",
            json=payload,
            headers=self._headers(),
            timeout=30.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding error ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        return data["data"][0]["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in one call."""
        model = self.embedding_model or self.model
        payload = {"model": model, "input": texts}
        resp = httpx.post(
            f"{self.base_url}/v1/embeddings",
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding error ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def embed_typed(
        self,
        text: str,
        embed_type: str = "query",
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate a typed embedding (query vs document) for asymmetric search.

        Many embedding models (e.g. nomic-embed, BGE, E5) produce different
        vectors for queries vs documents. This distinction improves retrieval
        accuracy in RAG pipelines.

        Args:
            text:       Text to embed.
            embed_type: "query" for search queries, "document" for indexed text.
            model:      Model override (default: embedding_model or self.model).

        Returns:
            Embedding vector as a list of floats.
        """
        if embed_type not in ("query", "document"):
            raise ValueError(f"embed_type must be 'query' or 'document', got '{embed_type}'")

        selected_model = model or self.embedding_model or self.model
        payload: dict = {
            "model": selected_model,
            "input": text,
            "type": embed_type,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        self.last_usage = {
            "embedding_typed": True,
            "type": embed_type,
            "model": selected_model,
        }
        return data["data"][0]["embedding"]

    def embed_typed_batch(
        self,
        texts: list[str],
        embed_type: str = "document",
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """Batch typed embeddings — typically for indexing documents.

        Args:
            texts:      List of texts to embed.
            embed_type: "query" or "document" (default: document for batch indexing).
            model:      Model override.

        Returns:
            List of embedding vectors.
        """
        if embed_type not in ("query", "document"):
            raise ValueError(f"embed_type must be 'query' or 'document', got '{embed_type}'")

        selected_model = model or self.embedding_model or self.model
        payload: dict = {
            "model": selected_model,
            "input": texts,
            "type": embed_type,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        self.last_usage = {
            "embedding_typed": True,
            "type": embed_type,
            "model": selected_model,
            "count": len(texts),
        }
        return [item["embedding"] for item in data["data"]]

    def embed_dims(
        self,
        text: str,
        dimensions: int,
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate a truncated embedding with a specific number of dimensions.

        Uses the ``dimensions`` parameter (Matryoshka embedding support) to
        get a shorter vector. Useful for trading accuracy for speed/memory.

        Args:
            text:       Text to embed.
            dimensions: Target number of dimensions (e.g. 256, 512, 768).
            model:      Model override (default: embedding_model or self.model).

        Returns:
            Embedding vector truncated to the requested dimensions.
        """
        selected_model = model or self.embedding_model or self.model
        payload: dict = {
            "model": selected_model,
            "input": text,
            "dimensions": dimensions,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        self.last_usage = {
            "embedding_dims": True,
            "dimensions": dimensions,
            "model": selected_model,
        }
        return data["data"][0]["embedding"]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embedding vectors.

        Args:
            a: First embedding vector.
            b: Second embedding vector.

        Returns:
            Similarity score between -1.0 and 1.0 (1.0 = identical).
        """
        if len(a) != len(b):
            raise ValueError(f"Vector dimensions must match: {len(a)} != {len(b)}")
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def nearest_neighbors(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        """Find the most similar documents to a query using embeddings.

        Embeds the query and all documents, then ranks by cosine similarity.

        Args:
            query:     The search query text.
            documents: List of document texts to search.
            top_k:     Number of top results to return.

        Returns:
            List of {index, text, score} dicts, sorted by score descending.
        """
        query_vec = self.embed(query)
        doc_vecs = self.embed_batch(documents) if documents else []

        results = []
        for i, (doc, vec) in enumerate(zip(documents, doc_vecs)):
            score = self.cosine_similarity(query_vec, vec)
            results.append({"index": i, "text": doc, "score": round(score, 4)})

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def embed_image(
        self,
        image_path: Path,
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate an embedding vector for an image (CLIP-style).

        Encodes the image as base64 and sends it to /v1/embeddings.
        Requires a multimodal embedding model (e.g. CLIP, LLaVA-embed).

        Args:
            image_path: Path to image file (png, jpg, etc.).
            model:      Embedding model override.

        Returns:
            Embedding vector as list of floats.
        """
        import base64
        selected_model = model or self.vision_model or self.embedding_model or self.model
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = "image/png" if str(image_path).endswith(".png") else "image/jpeg"
        payload = {
            "model": selected_model,
            "input": f"data:{mime};base64,{b64}",
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/v1/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Image embedding timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Image embedding error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        self.last_usage = {"model": selected_model, "image_embedding": True}
        return data["data"][0]["embedding"]

    def _is_model_loaded(self) -> bool:
        """Check if the configured model is present in /v1/models."""
        try:
            resp = httpx.get(f"{self.base_url}/v1/models", timeout=3.0)
            if resp.status_code == 200:
                ids = [m.get("id", "") for m in resp.json().get("data", [])]
                return self.model in ids
        except Exception:
            pass
        return False

    def _wait_for_model(
        self,
        timeout: float = _COLD_START_TIMEOUT,
        interval: float = _COLD_START_INTERVAL,
    ) -> bool:
        """Poll until the model appears in /v1/models or timeout is reached."""
        elapsed = 0.0
        while elapsed < timeout:
            if self._is_model_loaded():
                return True
            time.sleep(interval)
            elapsed += interval
        return False

    def execute(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        stop: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> str:
        t_start = time.perf_counter()
        system = self._system_prompt(mode, project_path)
        selected_model = self._select_model(prompt)
        payload: dict = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            **self.sampling_params_for_mode(mode),
        }
        if stop:
            payload["stop"] = stop
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed
        headers = self._headers()
        t_prep = time.perf_counter()

        last_error: Optional[str] = None
        response = None

        for attempt in range(3):
            try:
                response = httpx.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
                if response.status_code >= 500:
                    try:
                        err = response.json().get("error", {})
                        msg = err.get("message", response.text) if isinstance(err, dict) else str(err)
                    except Exception:
                        msg = response.text
                    last_error = msg

                    if attempt < 2:
                        # Model may still be cold-loading — wait for it to appear
                        # before retrying rather than sleeping a fixed amount.
                        self._wait_for_model()
                        continue

                    raise RuntimeError(f"LocalAI error ({response.status_code}): {msg}")

                if response.status_code >= 400:
                    raise RuntimeError(f"LocalAI error ({response.status_code}): {response.text}")

                break  # success

            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError(
                    f"LocalAI timed out at {self.base_url}.\n"
                    "The model may still be loading. Check logs: make local-logs"
                )

        if response is None:
            raise RuntimeError(f"LocalAI failed after retries. Last error: {last_error}")

        try:
            data = response.json()
        except Exception:
            return response.text

        t_response = time.perf_counter()

        # Capture usage metadata for observability
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        gen_ms = (t_response - t_prep) * 1000
        self.last_usage = {
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "prep_ms": round((t_prep - t_start) * 1000, 1),
            "generation_ms": round(gen_ms, 1),
            "total_ms": round((t_response - t_start) * 1000, 1),
            "tokens_per_sec": (
                round(completion_tokens / (gen_ms / 1000), 1)
                if completion_tokens and gen_ms > 0 else None
            ),
        }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LocalAI response: {str(data)[:200]}")

    def execute_stream(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        stop: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> Iterator[str]:
        """Stream the response token-by-token using SSE.

        Yields string chunks as they arrive. The caller is responsible for
        assembling them into the full response if needed.

        Usage::
            for chunk in backend.execute_stream(prompt, mode, path):
                print(chunk, end="", flush=True)
        """
        system = self._system_prompt(mode, project_path)
        selected_model = self._select_model(prompt)
        payload: dict = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "stream": True,
            **self.sampling_params_for_mode(mode),
        }
        if stop:
            payload["stop"] = stop
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed
        headers = self._headers()

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            ) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"LocalAI error ({resp.status_code}): {resp.read().decode()[:200]}"
                    )
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        raw = line[6:]
                        try:
                            data = json.loads(raw)
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                yield chunk
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}. "
                "The model may still be loading. Check logs: make local-logs"
            )

    def execute_vision(
        self,
        prompt: str,
        image_data: str,
        mode: Mode,
        project_path: Path,
        image_mime: str = "image/png",
    ) -> str:
        """Execute a vision request with an image.

        Args:
            prompt: Text prompt describing what to do with the image.
            image_data: Base64-encoded image data.
            image_mime: MIME type of the image (default: image/png).
            mode: Permission mode.
            project_path: Project directory for context.

        Returns:
            Model response text.
        """
        model = self.vision_model or self.model
        system = self._system_prompt(mode, project_path)
        data_url = f"data:{image_mime};base64,{image_data}"

        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "max_tokens": self.max_tokens,
            **self.sampling_params_for_mode(mode),
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=180.0,  # vision requests are slower
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Vision request timed out at {self.base_url}. "
                "The model may still be loading (vision models take longer)."
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI vision error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": data.get("model", model) if isinstance(data, dict) else model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "vision": True,
        }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected vision response: {str(data)[:200]}")

    def execute_multimodal(
        self,
        messages: list[dict],
        images: list[dict],
        mode: Mode,
        project_path: Path,
        seed: Optional[int] = None,
    ) -> str:
        """Multi-turn chat with inline images in the message array.

        Unlike execute_vision() which is single-shot, this method supports
        full conversation history with images at any position. Each image
        is referenced by a placeholder ``{img:N}`` in message content,
        replaced with the actual base64 data URL.

        Args:
            messages:     Chat messages list [{role, content}, ...].
                          Use ``{img:0}``, ``{img:1}`` etc. as placeholders
                          for images in the content field.
            images:       List of image dicts [{data: base64_str, mime: "image/png"}, ...].
            mode:         Permission mode for sampling profile.
            project_path: Project root for context building.
            seed:         Optional seed for reproducible output.

        Returns:
            The model's response text.
        """
        model = self.vision_model or self.model
        system = self._system_prompt(mode, project_path)

        # Build the API messages with multimodal content
        api_messages: list[dict] = [{"role": "system", "content": system}]

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Check if this message references any images
            has_images = any(f"{{img:{i}}}" in content for i in range(len(images)))

            if has_images and role == "user":
                # Build multimodal content array
                parts: list[dict] = []
                remaining = content
                for i, img in enumerate(images):
                    placeholder = f"{{img:{i}}}"
                    if placeholder in remaining:
                        # Split text around placeholder
                        before, remaining = remaining.split(placeholder, 1)
                        if before.strip():
                            parts.append({"type": "text", "text": before.strip()})
                        data_url = f"data:{img.get('mime', 'image/png')};base64,{img['data']}"
                        parts.append({"type": "image_url", "image_url": {"url": data_url}})
                if remaining.strip():
                    parts.append({"type": "text", "text": remaining.strip()})
                if not parts:
                    parts.append({"type": "text", "text": content})
                api_messages.append({"role": role, "content": parts})
            else:
                api_messages.append({"role": role, "content": content})

        payload: dict = {
            "model": model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
            **self.sampling_params_for_mode(mode),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=180.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Multimodal request timed out at {self.base_url}. "
                "Vision models take longer to process images."
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI multimodal error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": data.get("model", model) if isinstance(data, dict) else model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "multimodal": True,
            "images": len(images),
        }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected multimodal response: {str(data)[:200]}")

    def transcribe(
        self,
        audio_path: Path,
        model: str = "",
        language: str = "en",
        response_format: str = "json",
    ) -> dict:
        """Transcribe an audio file using the whisper backend.

        Args:
            audio_path: Path to the audio file (wav, mp3, ogg, flac, etc.).
            model: Whisper model name configured in LocalAI.
            language: Language hint for transcription.
            response_format: Output format (json, text, srt, vtt).

        Returns:
            Dict with 'text' key containing the transcription.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data = {"model": model or self.whisper_model, "language": language, "response_format": response_format}
            try:
                resp = httpx.post(
                    f"{self.base_url}/v1/audio/transcriptions",
                    files=files,
                    data=data,
                    headers=self._headers(),
                    timeout=120.0,
                )
            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError("Transcription timed out. Audio file may be too long.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Transcription error ({resp.status_code}): {resp.text[:300]}")

        result = resp.json()
        self.last_usage = {"model": model, "audio_file": audio_path.name, "transcription": True}
        return result

    def transcribe_detailed(
        self,
        audio_path: Path,
        model: str = "",
        language: str = "",
        timestamp_granularities: Optional[list[str]] = None,
        temperature: float = 0.0,
    ) -> dict:
        """Transcribe audio with verbose output including timestamps.

        Uses the OpenAI-compatible ``verbose_json`` response format to get
        word-level and/or segment-level timestamps.

        Args:
            audio_path:              Path to audio file.
            model:                   Whisper model override.
            language:                Language hint (ISO 639-1, e.g. "en", "fr").
            timestamp_granularities: List of "word" and/or "segment" (default: ["segment"]).
            temperature:             Sampling temperature for transcription (0.0-1.0).

        Returns:
            Dict with 'text', 'language', 'duration', 'words' and/or 'segments'.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        granularities = timestamp_granularities or ["segment"]
        selected_model = model or self.whisper_model

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data: dict = {
                "model": selected_model,
                "response_format": "verbose_json",
                "temperature": str(temperature),
            }
            if language:
                data["language"] = language
            # OpenAI API accepts timestamp_granularities[] as repeated form fields
            for g in granularities:
                data.setdefault("timestamp_granularities[]", [])
                if isinstance(data["timestamp_granularities[]"], list):
                    data["timestamp_granularities[]"] = g  # httpx sends last value
            # For multiple granularities, use the array form
            if len(granularities) > 1:
                data["timestamp_granularities[]"] = granularities

            try:
                resp = httpx.post(
                    f"{self.base_url}/v1/audio/transcriptions",
                    files=files,
                    data=data,
                    headers=self._headers(),
                    timeout=120.0,
                )
            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError("Transcription timed out. Audio file may be too long.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Transcription error ({resp.status_code}): {resp.text[:300]}")

        result = resp.json()
        self.last_usage = {
            "transcription_detailed": True,
            "model": selected_model,
            "audio_file": audio_path.name,
            "language": result.get("language", language),
            "duration": result.get("duration"),
            "granularities": granularities,
        }
        return result

    def speak(
        self,
        text: str,
        output_path: Path,
        model: str = "",
    ) -> Path:
        """Generate speech audio from text using the TTS backend.

        Args:
            text: Text to synthesize.
            output_path: Path to write the WAV file.
            model: TTS model name configured in LocalAI.

        Returns:
            Path to the generated audio file.
        """
        payload = {"model": model or self.tts_model, "input": text}
        try:
            resp = httpx.post(
                f"{self.base_url}/tts",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("TTS timed out. Text may be too long.")

        if resp.status_code >= 400:
            raise RuntimeError(f"TTS error ({resp.status_code}): {resp.text[:300]}")

        # Check if we got audio (not JSON error)
        content_type = resp.headers.get("content-type", "")
        if "json" in content_type:
            raise RuntimeError(f"TTS returned error: {resp.text[:300]}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        self.last_usage = {"model": model, "tts": True, "output_bytes": len(resp.content)}
        return output_path

    def tts(
        self,
        text: str,
        output_path: Path,
        voice: str = "",
        speed: float = 1.0,
        response_format: str = "wav",
        model: str = "",
    ) -> Path:
        """Generate speech using the OpenAI-compatible /v1/audio/speech endpoint.

        Supports voice selection, speed control, and output format.

        Args:
            text:            Text to synthesize.
            output_path:     Path to write the audio file.
            voice:           Voice name (model-dependent, e.g. "en-us-amy-low").
            speed:           Playback speed multiplier (0.25-4.0, default 1.0).
            response_format: Output format: "wav", "mp3", "opus", "flac" (default "wav").
            model:           TTS model override (default: self.tts_model).

        Returns:
            Path to the generated audio file.
        """
        selected_model = model or self.tts_model
        speed = max(0.25, min(speed, 4.0))
        payload: dict = {
            "model": selected_model,
            "input": text,
            "response_format": response_format,
            "speed": speed,
        }
        if voice:
            payload["voice"] = voice

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/audio/speech",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("TTS timed out. Text may be too long.")

        if resp.status_code >= 400:
            raise RuntimeError(f"TTS error ({resp.status_code}): {resp.text[:300]}")

        content_type = resp.headers.get("content-type", "")
        if "json" in content_type:
            raise RuntimeError(f"TTS returned error: {resp.text[:300]}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        self.last_usage = {
            "tts": True,
            "model": selected_model,
            "voice": voice or "(default)",
            "speed": speed,
            "format": response_format,
            "output_bytes": len(resp.content),
        }
        return output_path

    def tts_voices(self, model: str = "") -> list[str]:
        """List available TTS voices by querying the models endpoint.

        This is a best-effort introspection — not all backends expose voice lists.
        Falls back to an empty list on error.

        Args:
            model: TTS model to query (default: self.tts_model).

        Returns:
            List of voice identifiers, or empty list if unavailable.
        """
        selected_model = model or self.tts_model
        try:
            resp = httpx.get(
                f"{self.base_url}/models/{selected_model}",
                headers=self._headers(),
                timeout=10.0,
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return []

        if resp.status_code >= 400:
            return []

        data = resp.json()
        # LocalAI may expose voices in config or metadata
        voices = data.get("voices", [])
        if not voices:
            voices = data.get("metadata", {}).get("voices", [])
        return voices

    def voice_pipeline(
        self,
        audio_input: Path,
        audio_output: Path,
        mode: Mode,
        project_path: Path,
        whisper_model: str = "",
        tts_model: str = "",
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Full voice pipeline: audio in → transcribe → LLM → TTS → audio out.

        Args:
            audio_input: Path to input audio file (wav, mp3, ogg, flac).
            audio_output: Path to write the response audio (WAV).
            mode: Permission mode for the LLM.
            project_path: Project directory for context.
            whisper_model: STT model name.
            tts_model: TTS model name.
            system_prompt: Optional override for the system prompt.

        Returns:
            Dict with keys: transcription, response, audio_output, usage.
        """
        # Step 1: Transcribe
        stt_result = self.transcribe(audio_input, model=whisper_model)
        transcription = stt_result.get("text", "").strip()
        if not transcription:
            raise RuntimeError("No speech detected in audio input.")

        # Step 2: LLM response
        response = self.execute(transcription, mode, project_path)

        # Step 3: TTS
        self.speak(response, audio_output, model=tts_model)

        return {
            "transcription": transcription,
            "response": response,
            "audio_output": str(audio_output),
            "usage": getattr(self, "last_usage", {}),
        }

    def rerank(
        self,
        query: str,
        documents: list[str],
        model: str = "",
        top_n: int | None = None,
    ) -> list[dict]:
        """Rerank documents against a query using a cross-encoder model.

        Args:
            query: The search query.
            documents: List of document strings to rank.
            model: Reranker model name configured in LocalAI.
            top_n: Return only the top N results (default: all).

        Returns:
            List of dicts with keys: index, relevance_score, sorted by score descending.
        """
        payload: dict = {
            "model": model or self.reranker_model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/rerank",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Reranking timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Rerank error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()
        results = data.get("results", [])
        # Sort by relevance_score descending
        results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        self.last_usage = {"model": model, "reranking": True, "documents": len(documents)}
        return results

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        model: str = "",
        size: str = "512x512",
        step: Optional[int] = None,
    ) -> Path:
        """Generate an image from a text prompt using Stable Diffusion.

        Args:
            prompt: Text description of the image to generate.
                    Use '|' to separate positive and negative prompts.
            output_path: Path to write the generated PNG file.
            model: Image generation model name configured in LocalAI.
            size: Image dimensions as 'WxH' (default: 512x512).
            step: Number of diffusion steps (overrides model config if set).

        Returns:
            Path to the generated image file.
        """
        payload: dict = {"prompt": prompt, "model": model or self.image_model, "size": size}
        if step is not None:
            payload["step"] = step

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/images/generations",
                json=payload,
                headers=self._headers(),
                timeout=300.0,  # image generation is slow
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Image generation timed out. Try fewer steps or smaller size.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Image generation error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()

        # Response may contain base64 data or a URL to the generated image
        try:
            images = data.get("data", [])
            if not images:
                raise RuntimeError(f"No images returned: {str(data)[:200]}")
            item = images[0]
            b64_data = item.get("b64_json")
            url = item.get("url")
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected image response: {str(data)[:200]}") from e

        if b64_data:
            import base64
            image_bytes = base64.b64decode(b64_data)
        elif url:
            # LocalAI serves generated images from its own endpoint
            img_resp = httpx.get(url, timeout=30.0)
            if img_resp.status_code >= 400:
                raise RuntimeError(f"Failed to download image from {url}: {img_resp.status_code}")
            image_bytes = img_resp.content
        else:
            raise RuntimeError(f"No image data in response: {str(item)[:200]}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        self.last_usage = {
            "model": model,
            "image_generation": True,
            "size": size,
            "output_bytes": len(image_bytes),
        }
        return output_path

    def generate_sound(
        self,
        prompt: str,
        output_path: Path,
        model: str = "",
        duration: Optional[float] = None,
    ) -> Path:
        """Generate sound/music from a text description.

        Uses LocalAI's /v1/sound-generation endpoint (ElevenLabs-compatible).

        Args:
            prompt:      Text description of the sound to generate.
            output_path: Path to write the generated audio file.
            model:       Sound generation model name.
            duration:    Optional duration in seconds.

        Returns:
            Path to the generated audio file.
        """
        payload: dict = {"model": model or self.sound_model, "input": prompt}
        if duration is not None:
            payload["duration"] = duration

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/sound-generation",
                json=payload,
                headers=self._headers(),
                timeout=300.0,  # generation can be slow
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Sound generation timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Sound generation error ({resp.status_code}): {resp.text[:200]}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        self.last_usage = {
            "model": model,
            "sound_generation": True,
            "output_bytes": len(resp.content),
        }
        return output_path

    def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> str:
        """Raw text completion via /v1/completions (no chat template).

        Better for code infill, text continuation, and tasks where
        chat framing adds unwanted overhead.

        Args:
            prompt:     The text to complete.
            max_tokens: Maximum tokens to generate (default: self.max_tokens).
            stop:       Optional stop sequences.

        Returns:
            The completed text.
        """
        payload: dict = {
            "model": self._select_model(prompt),
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            **self._sampling_params(),
        }
        if stop:
            payload["stop"] = stop

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Completion request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Completion error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "completion": True,
        }

        try:
            return data["choices"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected response: {str(data)[:200]}")

    def complete_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> Iterator[str]:
        """Streaming raw text completion via /v1/completions.

        Yields text chunks as they arrive. Usage::

            for chunk in backend.complete_stream("Once upon a time"):
                print(chunk, end="", flush=True)
        """
        payload: dict = {
            "model": self._select_model(prompt),
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
            **self._sampling_params(),
        }
        if stop:
            payload["stop"] = stop

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/v1/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            ) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"Completion error ({resp.status_code}): {resp.read().decode()[:200]}"
                    )
                for line in resp.iter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            text = data["choices"][0].get("text", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Streaming completion timed out.")

    def complete_logprobs(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        top_logprobs: int = 5,
        seed: Optional[int] = None,
    ) -> dict:
        """Raw text completion with per-token log probabilities.

        Uses /v1/completions with logprobs enabled. Unlike execute_logprobs()
        which uses chat format, this operates on raw text without templates.

        Args:
            prompt:       Text to complete.
            max_tokens:   Max tokens to generate.
            top_logprobs: Number of top alternatives per position (1-20).
            seed:         Optional seed for reproducibility.

        Returns:
            Dict with text, tokens, logprobs, and avg_logprob.
        """
        payload: dict = {
            "model": self._select_model(prompt),
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            "logprobs": max(1, min(top_logprobs, 20)),
            **self._sampling_params(),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Completion request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Completion error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "completion_logprobs": True,
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        try:
            choice = data["choices"][0]
            text = choice["text"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected response: {str(data)[:200]}")

        lp_data = choice.get("logprobs", {}) or {}
        tokens = lp_data.get("tokens", [])
        token_logprobs = lp_data.get("token_logprobs", [])
        top_lps = lp_data.get("top_logprobs", [])

        avg_lp = sum(v for v in token_logprobs if v is not None) / len(token_logprobs) if token_logprobs else 0.0

        return {
            "text": text,
            "tokens": tokens,
            "token_logprobs": token_logprobs,
            "top_logprobs": top_lps,
            "avg_logprob": round(avg_lp, 4),
        }

    def complete_n(
        self,
        prompt: str,
        n: int = 3,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> list[dict]:
        """Generate N raw text completions for the same prompt.

        Uses /v1/completions with the n parameter. No chat template.

        Args:
            prompt:     Text to complete.
            n:          Number of completions (1-10).
            max_tokens: Max tokens per completion.
            seed:       Optional seed for reproducibility.

        Returns:
            List of {index, text, finish_reason} dicts.
        """
        n = max(1, min(n, 10))
        payload: dict = {
            "model": self._select_model(prompt),
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            "n": n,
            **self._sampling_params(),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Completion request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Completion error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices", [])
        results = []
        for choice in choices:
            try:
                results.append({
                    "index": choice.get("index", len(results)),
                    "text": choice["text"],
                    "finish_reason": choice.get("finish_reason", "stop"),
                })
            except (KeyError, TypeError):
                continue

        if not results:
            raise RuntimeError(f"Unexpected response: {str(data)[:200]}")

        return results

    def infill(
        self,
        prefix: str,
        suffix: str,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
        model: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> str:
        """Fill-in-the-Middle (FIM) code completion.

        Generates text that fits between a prefix and suffix — the technique
        behind Copilot-style code completion.  Uses /v1/completions with
        the ``prefix`` / ``suffix`` parameters that llama.cpp supports.

        Args:
            prefix:     Code/text before the cursor.
            suffix:     Code/text after the cursor.
            max_tokens: Maximum tokens to generate (default: self.max_tokens).
            stop:       Optional stop sequences.
            model:      Model override (default: code_model or self.model).
            seed:       Optional seed for reproducible output.

        Returns:
            The generated infill text.
        """
        selected_model = model or self.code_model or self.model
        payload: dict = {
            "model": selected_model,
            "prompt": prefix,
            "suffix": suffix,
            "max_tokens": max_tokens or self.max_tokens,
            **self._sampling_params(),
        }
        if stop:
            payload["stop"] = stop
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Infill request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Infill error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": selected_model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "infill": True,
        }

        try:
            return data["choices"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected response: {str(data)[:200]}")

    def tokenize_batch(self, texts: list[str], model: Optional[str] = None) -> list[dict]:
        """Tokenize multiple texts in one batch.

        Args:
            texts:  List of strings to tokenize.
            model:  Model to use (defaults to self.model).

        Returns:
            List of {tokens: [...], count: N} dicts, one per input text.
        """
        results = []
        for text in texts:
            results.append(self.tokenize(text, model=model))
        return results

    # ── N Completions / Best-of-N ───────────────────────────────────────────

    def execute_n(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        n: int = 3,
        seed: Optional[int] = None,
    ) -> list[dict]:
        """Generate multiple candidate responses for the same prompt.

        Uses the ``n`` parameter to get several completions in one request.
        Useful for best-of-N ranking, diversity sampling, and evaluation.

        Args:
            prompt:       The user prompt.
            mode:         Permission mode for sampling profile.
            project_path: Project root for context building.
            n:            Number of completions to generate (1-10).
            seed:         Optional seed for reproducible output.

        Returns:
            List of dicts, each with keys: index, text, finish_reason.
        """
        n = max(1, min(n, 10))
        system = self._system_prompt(mode, project_path)
        selected_model = self._select_model(prompt)
        payload: dict = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "n": n,
            **self.sampling_params_for_mode(mode),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}.\n"
                "The model may still be loading. Check logs: make local-logs"
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "n_completions": n,
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        choices = data.get("choices", [])
        results = []
        for choice in choices:
            try:
                results.append({
                    "index": choice.get("index", len(results)),
                    "text": choice["message"]["content"],
                    "finish_reason": choice.get("finish_reason", "stop"),
                })
            except (KeyError, TypeError):
                continue

        if not results:
            raise RuntimeError(f"Unexpected LocalAI response: {str(data)[:200]}")

        return results

    # ── Logprobs / Token Probabilities ──────────────────────────────────────

    def execute_logprobs(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        top_logprobs: int = 5,
        seed: Optional[int] = None,
    ) -> dict:
        """Execute a prompt and return the response with per-token log probabilities.

        Uses the ``logprobs`` and ``top_logprobs`` parameters to get token-level
        confidence scores. Useful for evaluation, calibration, and best-of-N.

        Args:
            prompt:       The user prompt.
            mode:         Permission mode for sampling profile.
            project_path: Project root for context building.
            top_logprobs: Number of top token alternatives per position (1-20).
            seed:         Optional seed for reproducible output.

        Returns:
            Dict with keys:
                text:      The generated text.
                logprobs:  List of token logprob entries from the API.
                tokens:    List of generated tokens.
                avg_logprob: Average log probability (confidence metric).
        """
        system = self._system_prompt(mode, project_path)
        selected_model = self._select_model(prompt)
        payload: dict = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "logprobs": True,
            "top_logprobs": max(1, min(top_logprobs, 20)),
            **self.sampling_params_for_mode(mode),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}.\n"
                "The model may still be loading. Check logs: make local-logs"
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "logprobs": True,
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LocalAI response: {str(data)[:200]}")

        # Extract logprobs from the response
        lp_data = choice.get("logprobs", {}) or {}
        content_lp = lp_data.get("content", [])

        tokens = [entry.get("token", "") for entry in content_lp]
        logprob_values = [entry.get("logprob", 0.0) for entry in content_lp]
        avg_lp = sum(logprob_values) / len(logprob_values) if logprob_values else 0.0

        return {
            "text": text,
            "logprobs": content_lp,
            "tokens": tokens,
            "avg_logprob": round(avg_lp, 4),
        }

    # ── JSON Mode / Structured Output ────────────────────────────────────────

    def execute_json(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        schema: Optional[dict] = None,
        seed: Optional[int] = None,
    ) -> dict:
        """Execute a prompt with JSON mode — forces valid JSON output.

        Uses response_format={"type": "json_object"} to guarantee the LLM
        returns parseable JSON. Optionally validates against a JSON Schema.

        Args:
            prompt:       The user prompt (should mention JSON in the instruction).
            mode:         Permission mode for sampling profile.
            project_path: Project root for context building.
            schema:       Optional JSON Schema dict to include in the system prompt
                          so the model knows the expected structure.
            seed:         Optional seed for reproducible output.

        Returns:
            Parsed JSON dict from the model's response.
        """
        system = self._system_prompt(mode, project_path)
        if schema:
            schema_str = json.dumps(schema, indent=2)
            system += f"\n\nRespond with valid JSON matching this schema:\n{schema_str}"

        selected_model = self._select_model(prompt)
        payload: dict = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            **self.sampling_params_for_mode(mode),
        }
        effective_seed = seed if seed is not None else self.seed
        if effective_seed is not None:
            payload["seed"] = effective_seed
        headers = self._headers()

        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LocalAI timed out at {self.base_url}.\n"
                "The model may still be loading. Check logs: make local-logs"
            )

        if response.status_code >= 400:
            raise RuntimeError(f"LocalAI error ({response.status_code}): {response.text[:200]}")

        data = response.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "json_mode": True,
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected LocalAI response: {str(data)[:200]}")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Model returned invalid JSON: {e}\nContent: {content[:200]}")

    # ── Batch / Concurrent Execution ────────────────────────────────────────

    def execute_batch(
        self,
        prompts: list[str],
        mode: Mode,
        project_path: Path,
        max_workers: int = 4,
        stop: Optional[list[str]] = None,
    ) -> list[dict]:
        """Execute multiple prompts concurrently and collect results.

        Uses a thread pool to run prompts in parallel.  Each result dict
        contains ``prompt``, ``response``, ``error`` (if failed), and
        ``duration_ms``.

        Args:
            prompts:     List of prompt strings.
            mode:        Permission mode for all prompts.
            project_path: Project directory for context.
            max_workers: Max concurrent requests (default: 4).
            stop:        Optional stop sequences applied to all prompts.

        Returns:
            List of result dicts in the same order as the input prompts.
        """
        import time as _time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run_one(idx: int, prompt: str) -> dict:
            t0 = _time.perf_counter()
            try:
                resp = self.execute(prompt, mode, project_path, stop=stop)
                return {
                    "index": idx,
                    "prompt": prompt,
                    "response": resp,
                    "error": None,
                    "duration_ms": round((_time.perf_counter() - t0) * 1000, 1),
                }
            except Exception as e:
                return {
                    "index": idx,
                    "prompt": prompt,
                    "response": None,
                    "error": str(e),
                    "duration_ms": round((_time.perf_counter() - t0) * 1000, 1),
                }

        results: list[dict] = [{}] * len(prompts)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_one, i, p): i for i, p in enumerate(prompts)}
            for future in as_completed(futures):
                result = future.result()
                results[result["index"]] = result
        return results

    def embed_batch_concurrent(
        self,
        texts: list[str],
        max_workers: int = 4,
    ) -> list[list[float]]:
        """Embed multiple texts concurrently.

        Unlike ``embed_batch`` which sends all texts in one request,
        this method runs individual embed calls in parallel — useful
        when the backend doesn't support true batch embedding or when
        texts are very long.

        Args:
            texts:       List of strings to embed.
            max_workers: Max concurrent requests (default: 4).

        Returns:
            List of embedding vectors in the same order as input.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[Optional[list[float]]] = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.embed, t): i for i, t in enumerate(texts)}
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()
        return results  # type: ignore[return-value]

    # ── Mode-Aware Sampling ──────────────────────────────────────────────────

    # Default temperature overrides per permission mode.
    # Think = more focused, Edit = moderate creativity, Act = deterministic.
    _MODE_SAMPLING: dict = {
        "think": {"temperature": 0.7},
        "edit":  {"temperature": 0.4},
        "act":   {"temperature": 0.1},
    }

    def sampling_params_for_mode(self, mode: Mode) -> dict:
        """Return sampling params with mode-aware defaults applied.

        Explicit config values (self.temperature etc.) always take precedence.
        Mode defaults only fill in when nothing is explicitly set.
        """
        base = self._sampling_params()
        mode_defaults = self._MODE_SAMPLING.get(mode.value, {})
        # Only apply mode defaults for keys NOT already set explicitly
        for key, value in mode_defaults.items():
            if key not in base:
                base[key] = value
        return base

    def _connect_error_message(self) -> str:
        """Build a diagnostic message when LocalAI is unreachable."""
        # Try to give a more specific hint by checking Docker state
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True, text=True, timeout=3,
            )
            output = result.stdout.strip()
            if "localai" in output.lower():
                if '"Status":"exited"' in output or '"State":"exited"' in output:
                    hint = "Container is stopped. Start it with: make local-up"
                else:
                    hint = "Container may be starting. Check logs: make local-logs"
            elif result.returncode == 0:
                hint = "Container not found. Build and start it: make setup-local-only"
            else:
                hint = "Start LocalAI with: make local-up"
        except Exception:
            hint = "Start LocalAI with: make local-up"

        return (
            f"Cannot connect to LocalAI at {self.base_url}.\n"
            f"  {hint}\n"
            f"  Check status with: make local-status"
        )

    def execute_grammar(
        self,
        prompt: str,
        grammar: str,
        mode: Mode,
        project_path: Path,
    ) -> str:
        """Execute with GBNF grammar constraint.

        The grammar forces the model's output to conform to a formal grammar
        (GBNF format, similar to BNF). This is more powerful than JSON mode —
        it can constrain output to YAML, CSV, enums, custom DSLs, etc.

        Args:
            prompt: The user prompt.
            grammar: GBNF grammar string (e.g. 'root ::= ("yes" | "no")').
            mode: Permission mode.
            project_path: Project directory for context.

        Returns:
            The constrained model response.
        """
        system = self._system_prompt(mode, project_path)
        payload: dict = {
            "model": self._select_model(prompt),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "grammar": grammar,
            **self.sampling_params_for_mode(mode),
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Grammar-constrained request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_usage = {
            "model": data.get("model", self.model) if isinstance(data, dict) else self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "grammar": True,
        }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected response: {str(data)[:200]}")

    def execute_with_tools(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        tools: Optional[list[dict]] = None,
        max_rounds: int = 5,
    ) -> str:
        """Execute with function calling, running a tool loop.

        Injects tool definitions into the system prompt using Hermes 2 Pro's
        native <tools>/<tool_call> format. Parses tool calls from the response
        and feeds results back until the model produces a final text answer.
        """
        from aicp.core.tools import execute_tool, get_tools_for_mode

        if tools is None:
            tools = get_tools_for_mode(mode.value)

        # Build system prompt with tools injected
        base_system = self._system_prompt(mode, project_path)
        tools_json = json.dumps([t["function"] for t in tools], indent=2)
        system = (
            f"{base_system}\n\n"
            f"You are a function calling AI model. You have access to the following tools:\n"
            f"<tools>\n{tools_json}\n</tools>\n\n"
            f"To call a tool, respond ONLY with JSON inside <tool_call></tool_call> tags:\n"
            f"<tool_call>\n"
            f'{{\"name\": \"function_name\", \"arguments\": {{\"arg\": \"value\"}}}}\n'
            f"</tool_call>\n\n"
            f"If you don't need to call a tool, respond normally with text."
        )

        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        selected_model = self._select_model(prompt)
        headers = self._headers()

        for _round in range(max_rounds):
            payload: dict = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                **self.sampling_params_for_mode(mode),
            }

            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

            data = resp.json()
            content = data["choices"][0]["message"].get("content") or ""

            # Parse tool calls from <tool_call>...</tool_call> tags
            tool_calls = self._parse_tool_calls(content)
            if not tool_calls:
                # No tool calls — this is the final response
                # Strip any residual tags
                clean = re.sub(r"</?tool_call>", "", content).strip()
                return clean

            # Execute each tool and build result messages
            messages.append({"role": "assistant", "content": content})
            for tc in tool_calls:
                args = tc.get("arguments") or tc.get("parameters") or {}
                result = execute_tool(tc["name"], json.dumps(args), project_path, backend=self)
                messages.append({
                    "role": "user",
                    "content": f"Tool result for {tc['name']}:\n{result}",
                })

        return messages[-1].get("content", "(tool loop exhausted)")

    def execute_with_native_tools(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        tools: Optional[list[dict]] = None,
        max_rounds: int = 5,
        tool_choice: str = "auto",
        grammar: Optional[str] = None,
    ) -> str:
        """Execute with OpenAI-compatible native function calling.

        Uses the ``tools`` parameter in the chat completions payload.
        LocalAI constrains output via grammar to ensure valid tool call JSON.
        Falls back to ``<tool_call>`` tag parsing if the model response
        doesn't include native ``tool_calls``.

        Args:
            prompt:       User prompt.
            mode:         Permission mode.
            project_path: Project directory for context.
            tools:        OpenAI-format tool definitions. Auto-selected if None.
            max_rounds:   Maximum tool-call/response loops.
            tool_choice:  "auto", "none", or {"type":"function","function":{"name":"fn"}}.
            grammar:      Optional GBNF grammar to constrain the final text response.
        """
        from aicp.core.tools import execute_tool, get_tools_for_mode

        if tools is None:
            tools = get_tools_for_mode(mode.value)

        system = self._system_prompt(mode, project_path)
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        selected_model = self._select_model(prompt)
        headers = self._headers()

        for _round in range(max_rounds):
            payload: dict = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "tools": tools,
                "tool_choice": tool_choice,
                **self.sampling_params_for_mode(mode),
            }
            if grammar:
                payload["grammar"] = grammar

            try:
                resp = httpx.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError("Function calling request timed out.")

            if resp.status_code >= 400:
                raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            native_tool_calls = message.get("tool_calls")

            # ── Native tool_calls in response ──────────────────────────
            if native_tool_calls:
                messages.append(message)  # preserve assistant message with tool_calls
                for tc in native_tool_calls:
                    fn = tc["function"]
                    tool_call_id = tc.get("id", f"call_{_round}")
                    result = execute_tool(
                        fn["name"],
                        fn.get("arguments", "{}"),
                        project_path,
                        backend=self,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result,
                    })
                continue  # next round — let model process results

            # ── Fallback: parse <tool_call> tags from content ──────────
            tag_calls = self._parse_tool_calls(content)
            if tag_calls:
                messages.append({"role": "assistant", "content": content})
                for tc in tag_calls:
                    args = tc.get("arguments") or tc.get("parameters") or {}
                    result = execute_tool(tc["name"], json.dumps(args), project_path, backend=self)
                    messages.append({
                        "role": "user",
                        "content": f"Tool result for {tc['name']}:\n{result}",
                    })
                continue

            # ── No tool calls — final text response ────────────────────
            clean = re.sub(r"</?tool_call>", "", content).strip()
            return clean

        # All rounds exhausted
        last_content = messages[-1].get("content", "")
        return last_content or "(tool loop exhausted)"

    def execute_with_tools_stream(
        self,
        prompt: str,
        mode: Mode,
        project_path: Path,
        tools: Optional[list[dict]] = None,
        max_rounds: int = 5,
        tool_choice: str = "auto",
    ) -> Iterator[str]:
        """Streaming tool calls — yields text chunks, executes tools mid-stream.

        Uses SSE streaming with OpenAI-compatible ``tools`` parameter.
        When the model emits ``delta.tool_calls`` instead of ``delta.content``,
        the tool call is accumulated, executed, and the result fed back for
        the next round.  Text chunks are yielded as they arrive.

        Usage::
            for chunk in backend.execute_with_tools_stream(prompt, mode, path):
                print(chunk, end="", flush=True)
        """
        from aicp.core.tools import execute_tool, get_tools_for_mode

        if tools is None:
            tools = get_tools_for_mode(mode.value)

        system = self._system_prompt(mode, project_path)
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        selected_model = self._select_model(prompt)
        headers = self._headers()

        for _round in range(max_rounds):
            payload: dict = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "tools": tools,
                "tool_choice": tool_choice,
                "stream": True,
                **self.sampling_params_for_mode(mode),
            }

            # Accumulate streamed tool calls and content
            accumulated_content = ""
            # tool_calls_acc: {index: {"id": ..., "function": {"name": ..., "arguments": ...}}}
            tool_calls_acc: dict[int, dict] = {}

            try:
                with httpx.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                ) as resp:
                    if resp.status_code >= 400:
                        raise RuntimeError(
                            f"LocalAI error ({resp.status_code}): {resp.read().decode()[:200]}"
                        )
                    for line in resp.iter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

                        # ── Text content chunk ──
                        text_chunk = delta.get("content", "")
                        if text_chunk:
                            accumulated_content += text_chunk
                            yield text_chunk

                        # ── Tool call chunks ──
                        tc_deltas = delta.get("tool_calls", [])
                        for tc_delta in tc_deltas:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc_delta.get("id", f"call_{_round}_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            fn_delta = tc_delta.get("function", {})
                            if "name" in fn_delta:
                                tool_calls_acc[idx]["function"]["name"] += fn_delta["name"]
                            if "arguments" in fn_delta:
                                tool_calls_acc[idx]["function"]["arguments"] += fn_delta["arguments"]

            except httpx.ConnectError:
                raise RuntimeError(self._connect_error_message())
            except httpx.TimeoutException:
                raise RuntimeError(
                    f"LocalAI timed out at {self.base_url}. "
                    "The model may still be loading. Check logs: make local-logs"
                )

            # ── Process accumulated tool calls ──
            if tool_calls_acc:
                # Build the assistant message with tool_calls
                assistant_msg: dict = {"role": "assistant", "content": accumulated_content or None}
                assistant_msg["tool_calls"] = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
                messages.append(assistant_msg)

                for tc in assistant_msg["tool_calls"]:
                    fn = tc["function"]
                    tool_call_id = tc.get("id", f"call_{_round}")
                    result = execute_tool(
                        fn["name"],
                        fn.get("arguments", "{}"),
                        project_path,
                        backend=self,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result,
                    })
                continue  # next round

            # ── No tool calls — also check for <tool_call> tags in content ──
            tag_calls = self._parse_tool_calls(accumulated_content)
            if tag_calls:
                messages.append({"role": "assistant", "content": accumulated_content})
                for tc in tag_calls:
                    args = tc.get("arguments") or tc.get("parameters") or {}
                    result = execute_tool(tc["name"], json.dumps(args), project_path, backend=self)
                    messages.append({
                        "role": "user",
                        "content": f"Tool result for {tc['name']}:\n{result}",
                    })
                continue  # next round

            # No tool calls at all — we're done
            return

        # Exhausted all rounds
        return

    @staticmethod
    def _parse_tool_calls(content: str) -> list[dict]:
        """Extract tool calls from <tool_call>JSON</tool_call> tags.

        Also handles the case where </tool_call> is stripped by stopwords,
        leaving just <tool_call>JSON at the end of the response.
        """
        calls = []
        # First try complete tags
        for match in re.finditer(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL):
            try:
                parsed = json.loads(match.group(1))
                if "name" in parsed:
                    calls.append(parsed)
            except json.JSONDecodeError:
                continue
        if calls:
            return calls
        # Fallback: closing tag stripped by stopwords
        for match in re.finditer(r"<tool_call>\s*(.*?)$", content, re.DOTALL):
            try:
                parsed = json.loads(match.group(1).strip())
                if "name" in parsed:
                    calls.append(parsed)
            except json.JSONDecodeError:
                continue
        return calls

    def _system_prompt(self, mode: Mode, project_path: Path) -> str:
        parts = []

        if mode == Mode.THINK:
            parts.append("You are a helpful assistant. Read-only mode: do not suggest edits or commands.")
        elif mode == Mode.EDIT:
            parts.append("You are a helpful assistant. Edit mode: you may suggest file edits but not commands.")
        else:
            parts.append("You are a helpful assistant. Full mode: you may suggest edits and commands.")

        parts.append(f"Project: {project_path.name}.")

        # Inject project context for richer answers
        context = build_project_context(project_path, max_chars=800)
        if context:
            parts.append(context)

        return "\n\n".join(parts)

    # ── Stores API ─────────────────────────────────────────────────────────

    def store_set(
        self,
        texts: list[str],
        store_name: str = "default",
    ) -> int:
        """Embed and store texts in LocalAI's native store.

        Args:
            texts:      List of texts to store.
            store_name: Store name (auto-created if new).

        Returns:
            Number of entries stored.
        """
        from aicp.core.stores import LocalAIStore

        embeddings = self.embed_batch(texts)
        store = LocalAIStore(self.base_url, store_name=store_name, api_key=self.api_key)
        store.set(embeddings, texts)
        return len(texts)

    def store_find(
        self,
        query: str,
        store_name: str = "default",
        top_k: int = 5,
    ) -> list[dict]:
        """Search LocalAI's native store by semantic similarity.

        Args:
            query:      Search query (will be embedded automatically).
            store_name: Store name to search.
            top_k:      Number of results.

        Returns:
            List of dicts with 'value' and 'similarity' fields.
        """
        from aicp.core.stores import LocalAIStore

        embedding = self.embed(query)
        store = LocalAIStore(self.base_url, store_name=store_name, api_key=self.api_key)
        results = store.find(embedding, top_k=top_k)
        return [{"value": r["value"], "similarity": r["similarity"]} for r in results]

    def store_delete(
        self,
        texts: list[str],
        store_name: str = "default",
    ) -> None:
        """Delete texts from LocalAI's native store.

        Args:
            texts:      List of texts to remove (re-embedded to find keys).
            store_name: Store name.
        """
        from aicp.core.stores import LocalAIStore

        embeddings = self.embed_batch(texts)
        store = LocalAIStore(self.base_url, store_name=store_name, api_key=self.api_key)
        store.delete(embeddings)

    # ── Model Management ───────────────────────────────────────────────────

    def models_available(self) -> list[dict]:
        """List models available in the LocalAI gallery.

        Returns:
            List of dicts with name, description, installed, tags, gallery fields.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/models/available",
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Gallery error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        results = []
        for m in data:
            results.append({
                "name": m.get("name", ""),
                "description": m.get("description", ""),
                "installed": m.get("installed", False),
                "tags": m.get("tags", []),
                "gallery": m.get("gallery", {}).get("name", ""),
                "license": m.get("license", ""),
            })
        return results

    def model_apply(self, model_id: str, name: str = "") -> dict:
        """Install a model from the gallery (async download).

        Args:
            model_id: Gallery model ID (e.g. "huggingface@user/model").
            name:     Optional custom name for the installed model.

        Returns:
            Dict with 'uuid' (job ID) and 'status' (progress URL).
        """
        payload: dict = {"id": model_id}
        if name:
            payload["name"] = name

        try:
            resp = httpx.post(
                f"{self.base_url}/models/apply",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Model apply error ({resp.status_code}): {resp.text[:200]}")

        return resp.json()

    def model_job_status(self, job_uuid: str) -> dict:
        """Check the progress of a model download job.

        Args:
            job_uuid: Job UUID returned by model_apply().

        Returns:
            Dict with processed, progress, file_size, downloaded_size, error fields.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/models/jobs/{job_uuid}",
                headers=self._headers(),
                timeout=10.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Job status error ({resp.status_code}): {resp.text[:200]}")

        return resp.json()

    def model_shutdown(self, model_name: str) -> bool:
        """Unload a model from GPU memory (does not delete files).

        Args:
            model_name: Name of the model to unload.

        Returns:
            True if shutdown was successful.
        """
        try:
            resp = httpx.post(
                f"{self.base_url}/backend/shutdown",
                json={"model": model_name},
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        return resp.status_code < 400

    def model_monitor(self, model_name: str) -> dict:
        """Check a model's status and memory usage.

        Args:
            model_name: Name of the model to check.

        Returns:
            Dict with 'state' (0=uninit, 1=busy, 2=ready, -1=error)
            and 'memory' details.
        """
        try:
            resp = httpx.post(
                f"{self.base_url}/backend/monitor",
                json={"model": model_name},
                headers=self._headers(),
                timeout=10.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            return {"state": -1, "memory": {}}

        return resp.json()

    # ── P2P / Cluster ──────────────────────────────────────────────────────

    def p2p_stats(self) -> dict:
        """Get P2P cluster statistics.

        Returns:
            Dict with online/total node counts, or empty if P2P is not enabled.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/api/p2p/stats",
                headers=self._headers(),
                timeout=10.0,
            )
        except httpx.ConnectError:
            return {"enabled": False, "error": "cannot connect"}

        if resp.status_code >= 400:
            return {"enabled": False, "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        data["enabled"] = True
        return data

    def p2p_workers(self) -> list[dict]:
        """List P2P worker nodes.

        Returns:
            List of worker dicts with name, online status, etc.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/api/p2p/workers",
                headers=self._headers(),
                timeout=10.0,
            )
        except httpx.ConnectError:
            return []

        if resp.status_code >= 400:
            return []

        return resp.json() if isinstance(resp.json(), list) else []

    # ── Tokenization ──────────────────────────────────────────────────────

    def tokenize(self, text: str, model: Optional[str] = None) -> dict:
        """Tokenize text and return token IDs.

        Args:
            text:  The text to tokenize.
            model: Model whose tokenizer to use (default: self.model).

        Returns:
            Dict with 'tokens' (list of int) and 'count' (int).
        """
        payload: dict = {
            "content": text,
            "model": model or self.model,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/tokenize",
                json=payload,
                headers=self._headers(),
                timeout=10.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code >= 400:
            raise RuntimeError(f"Tokenize error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        tokens = data.get("tokens", [])
        return {"tokens": tokens, "count": len(tokens)}

    # ── Text Edits ─────────────────────────────────────────────────────────

    def edit(
        self,
        input_text: str,
        instruction: str,
        model: Optional[str] = None,
    ) -> str:
        """Edit text based on an instruction via /v1/edits.

        Args:
            input_text:  The text to edit.
            instruction: What edit to perform.
            model:       Model to use (default: self.model).

        Returns:
            The edited text.
        """
        payload: dict = {
            "model": model or self.model,
            "input": input_text,
            "instruction": instruction,
            **self._sampling_params(),
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/edits",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Edit request timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Edit error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        try:
            return data["choices"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Unexpected edit response: {str(data)[:200]}")

    # ── Voice Activity Detection ───────────────────────────────────────────

    def vad(
        self,
        audio_path: Path,
        model: Optional[str] = None,
    ) -> list[dict]:
        """Detect voice segments in an audio file via /v1/audio/vad.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.).
            model:      VAD model name (defaults to whisper model).

        Returns:
            List of segments: [{start: float, end: float, text: str}, ...].
        """
        model = model or getattr(self, "whisper_model", None) or "whisper-1"
        try:
            with open(audio_path, "rb") as f:
                resp = httpx.post(
                    f"{self.base_url}/v1/audio/vad",
                    files={"file": (audio_path.name, f)},
                    data={"model": model},
                    headers=self._headers(),
                    timeout=120.0,
                )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("VAD request timed out.")

        if resp.status_code == 404:
            raise RuntimeError("VAD endpoint not available. Requires whisper backend.")
        if resp.status_code >= 400:
            raise RuntimeError(f"VAD error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        segments = data.get("segments", data if isinstance(data, list) else [])
        return segments

    # ── Object Detection ─────────────────────────────────────────────────────

    def detect(
        self,
        image_path: Path,
        model: Optional[str] = None,
    ) -> list[dict]:
        """Detect objects in an image via /v1/detection.

        Args:
            image_path: Path to image file.
            model:      Detection model name.

        Returns:
            List of detections: [{label: str, confidence: float, box: {...}}, ...].
        """
        model = model or self.vision_model or self.model
        try:
            with open(image_path, "rb") as f:
                resp = httpx.post(
                    f"{self.base_url}/v1/detection",
                    files={"file": (image_path.name, f)},
                    data={"model": model},
                    headers=self._headers(),
                    timeout=120.0,
                )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Detection request timed out.")

        if resp.status_code == 404:
            raise RuntimeError("Detection endpoint not available. Requires a detection model.")
        if resp.status_code >= 400:
            raise RuntimeError(f"Detection error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        detections = data.get("detections", data if isinstance(data, list) else [])
        return detections

    # ── Health & Readiness ───────────────────────────────────────────────────

    def health_check(self) -> dict:
        """Check LocalAI health via /healthz. Returns {"healthy": bool, ...}."""
        try:
            resp = httpx.get(
                f"{self.base_url}/healthz",
                headers=self._headers(),
                timeout=5.0,
            )
            return {"healthy": resp.status_code == 200, "status_code": resp.status_code}
        except httpx.ConnectError:
            return {"healthy": False, "error": "connection refused"}
        except httpx.TimeoutException:
            return {"healthy": False, "error": "timeout"}

    def is_ready(self) -> bool:
        """Check if LocalAI is ready to serve via /readyz."""
        try:
            resp = httpx.get(
                f"{self.base_url}/readyz",
                headers=self._headers(),
                timeout=5.0,
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    # ── Backend Management ───────────────────────────────────────────────────

    def backends_list(self) -> list[dict]:
        """List installed backends via GET /api/backends."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/backends",
                headers=self._headers(),
                timeout=10.0,
            )
            if resp.status_code >= 400:
                return []
            data = resp.json()
            return data if isinstance(data, list) else []
        except (httpx.ConnectError, httpx.TimeoutException):
            return []

    def backend_apply(self, backend_id: str) -> dict:
        """Install a backend at runtime via POST /api/backends/apply."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/backends/apply",
                json={"id": backend_id},
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Backend apply timed out.")

        if resp.status_code >= 400:
            raise RuntimeError(f"Backend apply error ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def backend_delete(self, backend_name: str) -> bool:
        """Delete a backend via POST /api/backends/delete."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/backends/delete",
                json={"name": backend_name},
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def model_delete(self, model_name: str) -> bool:
        """Delete/uninstall a model via POST /api/models/delete."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/models/delete",
                json={"name": model_name},
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    # ── Server Configuration & Feature Detection ─────────────────────────────

    def server_config(self) -> dict:
        """Retrieve server configuration for feature detection."""
        result: dict = {
            "healthy": False,
            "ready": False,
            "models": [],
            "backends": [],
            "features": [],
        }

        # Health + readiness
        result["healthy"] = self.health_check().get("healthy", False)
        result["ready"] = self.is_ready()

        if not result["healthy"]:
            return result

        # Models
        try:
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=5.0,
            )
            if resp.status_code == 200:
                result["models"] = [m["id"] for m in resp.json().get("data", [])]
        except Exception:
            pass

        # Backends
        result["backends"] = [
            b if isinstance(b, str) else b.get("name", str(b))
            for b in self.backends_list()
        ]

        # Feature detection — probe endpoints to see what's available
        feature_probes = {
            "embeddings": ("GET", "/v1/models"),  # if embedding model loaded
            "reranking": ("POST", "/v1/reranking"),
            "tokenize": ("POST", "/v1/tokenize"),
            "edits": ("POST", "/v1/edits"),
            "sound_generation": ("POST", "/v1/sound-generation"),
            "stores": ("POST", "/stores/get"),
            "p2p": ("GET", "/api/p2p/stats"),
        }

        for feature, (method, path) in feature_probes.items():
            try:
                if method == "GET":
                    resp = httpx.get(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        timeout=3.0,
                    )
                else:
                    resp = httpx.post(
                        f"{self.base_url}{path}",
                        json={},
                        headers=self._headers(),
                        timeout=3.0,
                    )
                # 404 = endpoint doesn't exist, anything else = feature exists
                if resp.status_code != 404:
                    result["features"].append(feature)
            except Exception:
                pass

        return result

    def metrics(self) -> dict:
        """Retrieve Prometheus metrics and system status from LocalAI.

        Combines /metrics parsing, GPU status, and loaded model info
        into a single observability snapshot.

        Returns:
            Dict with localai (goroutines, memory, api_calls) and gpu sub-dicts.
        """
        from aicp.core.observability import get_system_status
        return get_system_status(self.base_url)

    # ── LoRA Adapter Management ──────────────────────────────────────────────

    def lora_load(self, model_name: str, adapter_path: str) -> dict:
        """Load a LoRA adapter onto a model at runtime.

        Args:
            model_name:   The base model to attach the adapter to.
            adapter_path: Path to the LoRA adapter (local path or URL).

        Returns:
            Server response dict.
        """
        try:
            resp = httpx.post(
                f"{self.base_url}/models/apply",
                json={
                    "id": model_name,
                    "lora_adapter": adapter_path,
                },
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("LoRA load timed out.")

        if resp.status_code == 404:
            raise RuntimeError("LoRA adapter endpoint not available on this LocalAI version.")
        if resp.status_code >= 400:
            raise RuntimeError(f"LoRA load error ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    # ── Model Warm-up & Preloading ─────────────────────────────────────────

    def model_loaded(self, model_name: Optional[str] = None) -> bool:
        """Check if a model is currently loaded in LocalAI.

        Queries /v1/models and checks if the model appears in the list.

        Args:
            model_name: Model to check (default: self.model).

        Returns:
            True if the model is loaded and ready.
        """
        name = model_name or self.model
        try:
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=5.0,
            )
            if resp.status_code == 200:
                ids = [m.get("id", "") for m in resp.json().get("data", [])]
                return name in ids
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        return False

    def model_warmup(
        self,
        model_name: Optional[str] = None,
        timeout: float = 120.0,
    ) -> dict:
        """Warm up a model by triggering a minimal inference request.

        Sends a tiny prompt to force the model to load into VRAM.
        On SINGLE_ACTIVE_BACKEND=true, this will unload the current model
        and load the requested one.

        Args:
            model_name: Model to warm up (default: self.model).
            timeout:    Maximum seconds to wait for the model to load.

        Returns:
            Dict with loaded (bool), model, duration_ms, and tokens_generated.
        """
        name = model_name or self.model
        t_start = time.perf_counter()

        # Check if already loaded
        if self.model_loaded(name):
            return {
                "loaded": True,
                "model": name,
                "duration_ms": 0,
                "already_loaded": True,
            }

        # Trigger load with a minimal inference
        payload: dict = {
            "model": name,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "temperature": 0,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            return {
                "loaded": False,
                "model": name,
                "duration_ms": round((time.perf_counter() - t_start) * 1000),
                "error": f"Timed out after {timeout}s",
            }

        duration_ms = round((time.perf_counter() - t_start) * 1000)

        if resp.status_code >= 400:
            return {
                "loaded": False,
                "model": name,
                "duration_ms": duration_ms,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }

        return {
            "loaded": True,
            "model": name,
            "duration_ms": duration_ms,
            "already_loaded": False,
        }

    def models_loaded(self) -> list[str]:
        """List all currently loaded model IDs.

        Returns:
            List of model ID strings from /v1/models.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=5.0,
            )
            if resp.status_code == 200:
                return [m.get("id", "") for m in resp.json().get("data", [])]
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        return []

    # ── Model Configuration API ────────────────────────────────────────────

    def model_config(self, model_name: Optional[str] = None) -> dict:
        """Read the current runtime configuration for a model.

        Queries /models/<name> for context_size, gpu_layers, threads, etc.
        Defaults to self.model if no name given.

        Args:
            model_name: Model to query (default: self.model).

        Returns:
            Dict with the model's configuration.
        """
        name = model_name or self.model
        try:
            resp = httpx.get(
                f"{self.base_url}/models/{name}",
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())

        if resp.status_code == 404:
            raise RuntimeError(f"Model '{name}' not found.")
        if resp.status_code >= 400:
            raise RuntimeError(f"Model config error ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def model_config_update(
        self,
        model_name: Optional[str] = None,
        *,
        context_size: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        threads: Optional[int] = None,
        batch_size: Optional[int] = None,
        f16: Optional[bool] = None,
        mmap: Optional[bool] = None,
    ) -> dict:
        """Update runtime model parameters without restarting LocalAI.

        Uses POST /models/apply to change context_size, gpu_layers, threads, etc.
        Only non-None parameters are sent to the server.

        Args:
            model_name:   Model to update (default: self.model).
            context_size: Context window size (e.g. 2048, 4096, 8192).
            gpu_layers:   Number of layers to offload to GPU (-1 = all).
            threads:      Number of CPU threads for inference.
            batch_size:   Batch size for prompt processing.
            f16:          Use float16 memory.
            mmap:         Memory-map the model file.

        Returns:
            Server response dict.
        """
        name = model_name or self.model
        params: dict = {"id": name}

        if context_size is not None:
            params["context_size"] = context_size
        if gpu_layers is not None:
            params["gpu_layers"] = gpu_layers
        if threads is not None:
            params["threads"] = threads
        if batch_size is not None:
            params["batch_size"] = batch_size
        if f16 is not None:
            params["f16"] = f16
        if mmap is not None:
            params["mmap"] = mmap

        try:
            resp = httpx.post(
                f"{self.base_url}/models/apply",
                json=params,
                headers=self._headers(),
                timeout=120.0,
            )
        except httpx.ConnectError:
            raise RuntimeError(self._connect_error_message())
        except httpx.TimeoutException:
            raise RuntimeError("Model config update timed out.")

        if resp.status_code == 404:
            raise RuntimeError("Model configuration endpoint not available on this LocalAI version.")
        if resp.status_code >= 400:
            raise RuntimeError(f"Model config update error ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def lora_list(self, model_name: Optional[str] = None) -> list[dict]:
        """List models that have LoRA adapters configured.

        Checks model gallery/config for adapter presence.

        Args:
            model_name: Optional filter by model name.

        Returns:
            List of model config dicts that have lora_adapter set.
        """
        models = self.models_available()
        lora_models = [
            m for m in models
            if m.get("lora_adapter") or m.get("config", {}).get("lora_adapter")
        ]
        if model_name:
            lora_models = [m for m in lora_models if m.get("name") == model_name]
        return lora_models
