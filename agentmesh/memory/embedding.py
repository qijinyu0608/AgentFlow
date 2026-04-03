from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from .config import get_default_memory_config
from ..service.vector_memory_service import vector_memory_service


@dataclass(frozen=True)
class EmbeddingInfo:
    provider: str
    model: str
    dim: int


class EmbeddingAdapter:
    """Embedding model adapter for OpenAI or local sentence-transformers backends."""

    def embed(self, text: str) -> np.ndarray:
        return vector_memory_service.embed_text(text)

    def info(self) -> EmbeddingInfo:
        cfg = get_default_memory_config()
        dim = int(vector_memory_service._dim or cfg.embedding_dim)
        return EmbeddingInfo(
            provider=str(cfg.embedding_provider),
            model=str(cfg.embedding_model),
            dim=dim,
        )

    def as_dict(self) -> Dict[str, Any]:
        info = self.info()
        return {
            "provider": info.provider,
            "model": info.model,
            "dim": info.dim,
        }


embedding_adapter = EmbeddingAdapter()
