from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..service.vector_memory_service import VectorHit, vector_memory_service
from .storage import memory_storage


@dataclass(frozen=True)
class RetrievedVectorHit:
    memory_item_id: int
    score: float
    content: str
    meta: Dict[str, Any]
    source: Dict[str, Any]


class VectorIndex:
    """FAISS-backed vector index manager."""

    def warmup(
        self,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> int:
        index, ids, _ = vector_memory_service._ensure_index(
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
        )
        if index is None:
            return 0
        return len(ids)

    def invalidate(self, conversation_id: Optional[str] = None) -> None:
        vector_memory_service.invalidate_index_cache(conversation_id=conversation_id)

    def upsert(self, memory_item_id: int) -> None:
        vector_memory_service.upsert_embedding(memory_item_id)

    def search(
        self,
        query: str,
        conversation_id: Optional[str],
        k: int = 10,
        min_score: Optional[float] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> List[RetrievedVectorHit]:
        hits: List[VectorHit] = vector_memory_service.search(
            q=query,
            conversation_id=conversation_id,
            k=k,
            min_score=min_score,
            scope=scope,
            kind=kind,
        )
        return [
            RetrievedVectorHit(
                memory_item_id=hit.memory_item_id,
                score=float(hit.score),
                content=hit.content,
                meta=dict(hit.meta or {}),
                source=memory_storage.get_memory_source(hit.memory_item_id),
            )
            for hit in hits
        ]


vector_index = VectorIndex()
