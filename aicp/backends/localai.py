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
        # Advanced sampling (llama.cpp)
        mirostat: Optional[int] = None,
        mirostat_tau: Optional[float] = None,
        mirostat_eta: Optional[float] = None,
        typical_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
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
        # Advanced sampling
        self.mirostat = mirostat
        self.mirostat_tau = mirostat_tau
        self.mirostat_eta = mirostat_eta
        self.typical_p = typical_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

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

    def execute(self, prompt: str, mode: Mode, project_path: Path) -> str:
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
            **self._sampling_params(),
        }
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

    def execute_stream(self, prompt: str, mode: Mode, project_path: Path) -> Iterator[str]:
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
            **self._sampling_params(),
        }
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
            **self._sampling_params(),
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

    def transcribe(
        self,
        audio_path: Path,
        model: str = "whisper-1",
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
            data = {"model": model, "language": language, "response_format": response_format}
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

    def speak(
        self,
        text: str,
        output_path: Path,
        model: str = "piper-tts",
    ) -> Path:
        """Generate speech audio from text using the TTS backend.

        Args:
            text: Text to synthesize.
            output_path: Path to write the WAV file.
            model: TTS model name configured in LocalAI.

        Returns:
            Path to the generated audio file.
        """
        payload = {"model": model, "input": text}
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

    def voice_pipeline(
        self,
        audio_input: Path,
        audio_output: Path,
        mode: Mode,
        project_path: Path,
        whisper_model: str = "whisper-1",
        tts_model: str = "piper-tts",
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
        model: str = "bge-reranker-v2-m3",
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
            "model": model,
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
        model: str = "stablediffusion",
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
        payload: dict = {"prompt": prompt, "model": model, "size": size}
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
        model: str = "transformers-musicgen",
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
        payload: dict = {"model": model, "input": prompt}
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

    def execute_json(
        self, prompt: str, mode: Mode, project_path: Path,
        schema: Optional[dict] = None,
    ) -> dict:
        """Execute and return a parsed JSON response.

        Uses response_format: json_object to guarantee valid JSON output.
        If schema is provided, it is included in the system prompt to guide structure.
        """
        system = self._system_prompt(mode, project_path)
        if schema:
            system += f"\n\nRespond with JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        else:
            system += "\n\nRespond with valid JSON only. No markdown, no explanation."

        payload: dict = {
            "model": self._select_model(prompt),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            **self._sampling_params(),
        }

        resp = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=120.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"LocalAI error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

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
            **self._sampling_params(),
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
                **self._sampling_params(),
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
                **self._sampling_params(),
            }

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
