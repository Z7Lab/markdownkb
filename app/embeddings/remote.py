"""Remote embedding via Ollama or OpenAI-compatible API."""

import logging

import httpx

logger = logging.getLogger(__name__)


class RemoteEmbedder:
    """Embedding via a remote API (Ollama or OpenAI-compatible)."""

    def __init__(self, model: str, api_base: str, api_type: str = "ollama", api_key: str = ""):
        self._model = model
        self._api_base = api_base.rstrip("/")
        self._api_type = api_type
        self._api_key = api_key
        self._dimensions: int | None = None
        logger.info(
            "Remote embedder: model=%s api_base=%s type=%s key=%s",
            model, api_base, api_type, "set" if api_key else "none",
        )

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            # Detect dimensions by embedding a test string
            result = self.embed(["test"])
            if result:
                self._dimensions = len(result[0])
            else:
                raise RuntimeError("Cannot detect embedding dimensions — remote API returned empty result")
        return self._dimensions

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed texts via remote API. Returns list of float vectors."""
        if not texts:
            return []

        if self._api_type == "ollama":
            return self._embed_ollama(texts)
        return self._embed_openai(texts, batch_size)

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Embed via Ollama POST /api/embed (batch endpoint)."""
        try:
            resp = httpx.post(
                f"{self._api_base}/api/embed",
                json={"model": self._model, "input": texts},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if not embeddings:
                raise RuntimeError(f"Ollama returned no embeddings for model {self._model}")
            return embeddings
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama embedding failed: {e}") from e

    def _embed_openai(self, texts: list[str], batch_size: int) -> list[list[float]]:
        """Embed via OpenAI-compatible POST /v1/embeddings."""
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                resp = httpx.post(
                    f"{self._api_base}/v1/embeddings",
                    json={"model": self._model, "input": batch},
                    headers=headers,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                # OpenAI format: data[].embedding
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                all_embeddings.extend(d["embedding"] for d in sorted_data)
            except httpx.HTTPError as e:
                raise RuntimeError(f"Remote embedding failed: {e}") from e
        return all_embeddings


def test_remote_embedding(model: str, api_base: str, api_type: str = "ollama", api_key: str = "") -> dict:
    """Test a remote embedding endpoint. Returns status dict."""
    try:
        embedder = RemoteEmbedder(model, api_base, api_type, api_key=api_key)
        result = embedder.embed(["test connection"])
        if result and len(result[0]) > 0:
            return {
                "ok": True,
                "dimensions": len(result[0]),
                "message": f"Connected — {len(result[0])} dimensions",
            }
        return {"ok": False, "message": "API returned empty embeddings"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
