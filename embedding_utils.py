from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_HF_EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"


@dataclass
class Embedder:
    provider: str
    model: str
    dimensions: int | None = None
    device: str | None = None
    _client: Any = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        texts = [text or "" for text in texts]
        if self.provider == "huggingface":
            vectors = self._client.encode(
                texts,
                batch_size=min(64, max(1, len(texts))),
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return vectors.tolist()

        kwargs: dict[str, Any] = {"model": self.model, "input": texts}
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        response = self._client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def _resolve_device(device: str) -> str | None:
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return None


def make_embedder(
    provider: str = "huggingface",
    model: str = DEFAULT_HF_EMBEDDING_MODEL,
    dimensions: int | None = None,
    device: str = "auto",
    openai_api_key_env: str = "OPENAI_API_KEY",
    hf_token_env: str = "HF_TOKEN",
) -> Embedder:
    if provider == "huggingface":
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise RuntimeError(
                "sentence-transformers is required for Hugging Face embeddings. "
                "Install it with: python -m pip install sentence-transformers"
            ) from exc

        resolved_device = _resolve_device(device)
        token = os.getenv(hf_token_env)
        kwargs: dict[str, Any] = {}
        if resolved_device:
            kwargs["device"] = resolved_device
        if token:
            kwargs["token"] = token
        client = SentenceTransformer(model, **kwargs)
        dims = int(client.get_sentence_embedding_dimension() or 0) or None
        return Embedder(provider=provider, model=model, dimensions=dims, device=resolved_device, _client=client)

    if provider == "openai":
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("openai package is required for OpenAI embeddings.") from exc
        api_key = os.getenv(openai_api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {openai_api_key_env}. Put it in .env or export it.")
        client = OpenAI(api_key=api_key)
        return Embedder(provider=provider, model=model, dimensions=dimensions, device=None, _client=client)

    raise ValueError(f"Unsupported embedding provider: {provider}")
