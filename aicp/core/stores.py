"""LocalAI Stores API — ephemeral vector key-value store.

Wraps the /stores/ endpoints for in-memory similarity search.
Stores are auto-created on first use and lost on LocalAI restart.

Typical flow:
    1. Embed text via /v1/embeddings → get vector
    2. Store vector + text via /stores/set
    3. Query with /stores/find → get top-K similar entries
"""

from __future__ import annotations

from typing import Any

import httpx


class LocalAIStore:
    """Client for LocalAI's /stores/ API.

    Args:
        base_url:   LocalAI API base URL (e.g. http://localhost:8090).
        store_name: Name of the store to use (default: "default").
        api_key:    Optional API key for authentication.
        timeout:    Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        store_name: str = "default",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.store_name = store_name
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def set(
        self,
        keys: list[list[float]],
        values: list[str],
    ) -> None:
        """Store key-value pairs. Keys are embedding vectors, values are strings.

        Identical keys overwrite existing values.

        Args:
            keys:   List of embedding vectors (must all have same dimension).
            values: List of string values (parallel to keys).
        """
        if len(keys) != len(values):
            raise ValueError(f"keys ({len(keys)}) and values ({len(values)}) must have same length")

        payload: dict[str, Any] = {
            "store": self.store_name,
            "keys": keys,
            "values": values,
        }
        resp = httpx.post(
            f"{self.base_url}/stores/set",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Stores set error ({resp.status_code}): {resp.text[:200]}")

    def get(self, keys: list[list[float]]) -> dict[str, Any]:
        """Retrieve values for given keys.

        Args:
            keys: List of embedding vectors to look up.

        Returns:
            Dict with 'keys' and 'values' arrays.
        """
        payload: dict[str, Any] = {
            "store": self.store_name,
            "keys": keys,
        }
        resp = httpx.post(
            f"{self.base_url}/stores/get",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Stores get error ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def delete(self, keys: list[list[float]]) -> None:
        """Remove entries by key. Non-existent keys are silently ignored.

        Args:
            keys: List of embedding vectors to delete.
        """
        payload: dict[str, Any] = {
            "store": self.store_name,
            "keys": keys,
        }
        resp = httpx.post(
            f"{self.base_url}/stores/delete",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Stores delete error ({resp.status_code}): {resp.text[:200]}")

    def find(
        self,
        key: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Similarity search. Returns top-K most similar entries.

        Args:
            key:   Query embedding vector.
            top_k: Number of results to return.

        Returns:
            List of dicts with 'value', 'similarity', and 'key' fields,
            ordered from most to least similar.
        """
        payload: dict[str, Any] = {
            "store": self.store_name,
            "key": key,
            "topk": top_k,
        }
        resp = httpx.post(
            f"{self.base_url}/stores/find",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Stores find error ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        results = []
        keys_list = data.get("keys", [])
        values_list = data.get("values", [])
        similarities = data.get("similarities", [])

        for i in range(len(values_list)):
            results.append({
                "value": values_list[i],
                "similarity": similarities[i] if i < len(similarities) else 0.0,
                "key": keys_list[i] if i < len(keys_list) else [],
            })

        return results


class EmbeddingStore:
    """High-level store that handles embedding automatically.

    Wraps LocalAIStore + embedding backend to provide a simple
    text-in / text-out interface for agent working memory.

    Args:
        backend: LocalAIBackend instance (for embedding).
        base_url: LocalAI API base URL.
        store_name: Store name (default: "memory").
        api_key: Optional API key.
    """

    def __init__(
        self,
        backend: Any,
        base_url: str,
        store_name: str = "memory",
        api_key: str = "",
    ) -> None:
        self.backend = backend
        self.store = LocalAIStore(
            base_url=base_url,
            store_name=store_name,
            api_key=api_key,
        )

    def remember(self, text: str, metadata: str = "") -> None:
        """Store a text in working memory.

        Args:
            text:     The text to remember.
            metadata: Optional metadata prefix (e.g. source, category).
        """
        embedding = self.backend.embed(text)
        value = f"{metadata}: {text}" if metadata else text
        self.store.set([embedding], [value])

    def remember_batch(self, texts: list[str], metadata: list[str] | None = None) -> None:
        """Store multiple texts in working memory.

        Args:
            texts:    List of texts to remember.
            metadata: Optional list of metadata prefixes (parallel to texts).
        """
        embeddings = self.backend.embed_batch(texts)
        if metadata:
            values = [f"{m}: {t}" if m else t for m, t in zip(metadata, texts)]
        else:
            values = texts
        self.store.set(embeddings, values)

    def recall(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search working memory for relevant information.

        Args:
            query: What to search for.
            top_k: Number of results to return.

        Returns:
            List of dicts with 'value' and 'similarity' fields.
        """
        embedding = self.backend.embed(query)
        results = self.store.find(embedding, top_k=top_k)
        # Strip the key vectors from results (not useful to callers)
        return [{"value": r["value"], "similarity": r["similarity"]} for r in results]

    def forget(self, text: str) -> None:
        """Remove a specific text from working memory.

        Args:
            text: The exact text to forget (must match what was stored).
        """
        embedding = self.backend.embed(text)
        self.store.delete([embedding])
