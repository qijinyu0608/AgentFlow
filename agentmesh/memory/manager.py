from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .chunker import TextChunk, text_chunker
from .config import MemoryConfig, get_default_memory_config
from .embedding import embedding_adapter
from .storage import StorageHit, memory_storage
from .summarizer import memory_summarizer
from .vector_index import RetrievedVectorHit, vector_index
from ..service.context_builder import context_builder
from ..service.rag_ingest_service import rag_ingest_service
from ..service.unified_memory_service import unified_memory_service


@dataclass(frozen=True)
class HybridSearchHit:
    memory_item_id: int
    score: float
    vector_score: float
    keyword_score: float
    content: str
    scope: str
    kind: str
    tags: List[str]
    source: Dict[str, Any]
    meta: Dict[str, Any]


class MemoryManager:
    """Unified entrypoint for sync/chunk/embed/retrieve/memory-guided context building."""

    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or get_default_memory_config()
        self.storage = memory_storage
        self.vector_index = vector_index
        self.chunker = text_chunker
        self.embedding = embedding_adapter
        self.summarizer = memory_summarizer

    def create_memory_item(
        self,
        content: str,
        scope: str = "conversation",
        kind: str = "fact",
        conversation_id: Optional[str] = None,
        source_message_id: Optional[int] = None,
        confidence: float = 0.5,
        tags: Optional[List[str]] = None,
        deprecate_previous: bool = True,
        with_embedding: bool = True,
    ) -> int:
        item_id = unified_memory_service.create_memory_item(
            content=content,
            scope=scope,
            kind=kind,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            confidence=confidence,
            tags=tags,
            deprecate_previous=deprecate_previous,
            with_embedding=with_embedding,
        )
        return int(item_id)

    def get_memory_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        item = self.storage.get_item(item_id)
        if not item:
            return None
        item["source"] = self.storage.get_memory_source(int(item_id))
        return item

    def list_memory_items(
        self,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: str = "active",
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        items = self.storage.list_items(
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )
        for item in items:
            item["source"] = self.storage.get_memory_source(int(item["id"]))
        return items

    def get_long_term_memory(self):
        return unified_memory_service.get_long_term_memory()

    def put_long_term_memory(self, meta: Dict[str, Any], content: str):
        return unified_memory_service.put_long_term_memory(meta=meta, content=content)

    def upload_document(self, filename: str, mime_type: str, content: bytes) -> Dict[str, Any]:
        return rag_ingest_service.save_upload(filename=filename, mime_type=mime_type, content=content)

    def ingest_document(
        self,
        document_id: int,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> Dict[str, Any]:
        return unified_memory_service.ingest_document(
            document_id=int(document_id),
            chunk_size=int(chunk_size or 700),
            overlap=int(overlap or 100),
        )

    def list_documents(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return rag_ingest_service.list_documents(limit=limit, offset=offset)

    def get_document(
        self,
        document_id: int,
        include_paragraphs: bool = False,
        include_raw_text: bool = False,
    ) -> Dict[str, Any]:
        return rag_ingest_service.get_document(
            document_id=int(document_id),
            include_paragraphs=include_paragraphs,
            include_raw_text=include_raw_text,
        )

    def list_document_chunks(self, document_id: int, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return rag_ingest_service.list_chunks(document_id=int(document_id), limit=limit, offset=offset)

    def chunk_text(
        self,
        text: str,
        source_path: Optional[str] = None,
        chunk_max_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
    ) -> List[TextChunk]:
        return self.chunker.chunk_text(
            text=text,
            source_path=source_path,
            chunk_max_tokens=chunk_max_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
        )

    def embed_text(self, text: str):
        return self.embedding.embed(text)

    def warmup_vector_index(
        self,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> int:
        return self.vector_index.warmup(conversation_id=conversation_id, scope=scope, kind=kind)

    def search_keyword(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: Optional[int] = None,
    ) -> List[StorageHit]:
        return self.storage.keyword_search(
            query=query,
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            k=int(k or self.config.max_results),
        )

    def search_vector(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[RetrievedVectorHit]:
        try:
            return self.vector_index.search(
                query=query,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=int(k or self.config.max_results),
                min_score=min_score if min_score is not None else self.config.min_score,
            )
        except Exception:
            return []

    def search_hybrid(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[HybridSearchHit]:
        limit = int(k or self.config.max_results)
        vector_hits = self.search_vector(
            query=query,
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            k=limit,
            min_score=min_score,
        )
        keyword_hits = self.search_keyword(
            query=query,
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            k=limit,
        )

        merged: Dict[int, Dict[str, Any]] = {}
        for hit in vector_hits:
            merged[hit.memory_item_id] = {
                "memory_item_id": hit.memory_item_id,
                "content": hit.content,
                "scope": str(hit.meta.get("scope") or ""),
                "kind": str(hit.meta.get("kind") or ""),
                "tags": list(hit.meta.get("tags") or []),
                "source": dict(hit.source or {}),
                "meta": dict(hit.meta or {}),
                "vector_score": float(hit.score),
                "keyword_score": 0.0,
            }
        for hit in keyword_hits:
            item = merged.setdefault(
                hit.memory_item_id,
                {
                    "memory_item_id": hit.memory_item_id,
                    "content": hit.content,
                    "scope": hit.scope,
                    "kind": hit.kind,
                    "tags": list(hit.tags or []),
                    "source": dict(hit.source or {}),
                    "meta": {
                        "conversation_id": hit.conversation_id,
                        "confidence": hit.confidence,
                        "updated_at": hit.updated_at,
                    },
                    "vector_score": 0.0,
                    "keyword_score": 0.0,
                },
            )
            item["keyword_score"] = max(float(item.get("keyword_score") or 0.0), float(hit.keyword_score))
            if not item.get("content"):
                item["content"] = hit.content

        ranked: List[HybridSearchHit] = []
        for item in merged.values():
            vector_score = float(item["vector_score"])
            keyword_score = float(item["keyword_score"])
            score = (self.config.vector_weight * vector_score) + (self.config.keyword_weight * keyword_score)
            if min_score is not None and score < float(min_score):
                continue
            ranked.append(
                HybridSearchHit(
                    memory_item_id=int(item["memory_item_id"]),
                    score=score,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    content=str(item["content"] or ""),
                    scope=str(item["scope"] or ""),
                    kind=str(item["kind"] or ""),
                    tags=list(item["tags"] or []),
                    source=dict(item["source"] or {}),
                    meta=dict(item["meta"] or {}),
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    def build_memory_guidance(
        self,
        conversation_id: Optional[str],
        user_text: str,
        recent_limit: int = 20,
        memory_k: Optional[int] = None,
        memory_min_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        return context_builder.build_task_bundle(
            conversation_id=conversation_id,
            user_text=user_text,
            recent_limit=recent_limit,
            memory_k=int(memory_k or self.config.max_results),
            memory_min_score=float(memory_min_score if memory_min_score is not None else self.config.min_score),
        )

    def flush_memory(
        self,
        conversation_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        instructions: str = "",
    ) -> Dict[str, Any]:
        return self.summarizer.flush_conversation(
            conversation_id=conversation_id,
            start_seq=start_seq,
            end_seq=end_seq,
            instructions=instructions,
        )

    @staticmethod
    def serialize_hit(hit: HybridSearchHit) -> Dict[str, Any]:
        return asdict(hit)


memory_manager = MemoryManager()
