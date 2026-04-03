from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..common.database import memory_db_manager
from ..service.memory_item_service import memory_item_service


@dataclass(frozen=True)
class StorageHit:
    memory_item_id: int
    conversation_id: Optional[str]
    scope: str
    kind: str
    content: str
    confidence: float
    tags: List[str]
    updated_at: str
    keyword_score: float
    source: Dict[str, Any]


class MemoryStorage:
    """
    SQLite access layer for memory/rag records.

    The current project still stores memory through service modules, so this
    storage layer delegates writes to the existing services and centralizes
    read/query helpers for the new `agentmesh.memory` package.
    """

    def __init__(self) -> None:
        self.db = memory_db_manager
        self._fts_ready = False
        self._fts_attempted = False

    def ensure_fts5(self) -> bool:
        if self._fts_attempted:
            return self._fts_ready
        self._fts_attempted = True
        try:
            self.db.execute_update(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts
                USING fts5(content, content='memory_items', content_rowid='id')
                """
            )
            self.db.execute_update(
                """
                INSERT INTO memory_items_fts(rowid, content)
                SELECT id, content FROM memory_items
                WHERE id NOT IN (SELECT rowid FROM memory_items_fts)
                """
            )
            self._fts_ready = True
        except Exception:
            self._fts_ready = False
        return self._fts_ready

    @staticmethod
    def _visibility_clause(conversation_id: Optional[str], scope: Optional[str]) -> Optional[Tuple[str, List[Any]]]:
        return memory_item_service._search_visibility_clause(conversation_id=conversation_id, scope=scope)

    @staticmethod
    def _normalize_keyword_query(query: str) -> str:
        parts = [p for p in re.split(r"[\s,，。；;:：/\\|]+", (query or "").strip()) if p]
        if not parts:
            return ""
        return " OR ".join(f'"{p}"' for p in parts[:8])

    def create_item(
        self,
        content: str,
        scope: str = "conversation",
        kind: str = "fact",
        conversation_id: Optional[str] = None,
        source_message_id: Optional[int] = None,
        confidence: float = 0.5,
        tags: Optional[List[str]] = None,
        deprecate_previous: bool = True,
    ) -> int:
        item_id = memory_item_service.create_item(
            content=content,
            scope=scope,
            kind=kind,
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            confidence=confidence,
            tags=tags,
            deprecate_previous=deprecate_previous,
        )
        if self.ensure_fts5():
            try:
                self.db.execute_update(
                    "INSERT OR REPLACE INTO memory_items_fts(rowid, content) VALUES (?, ?)",
                    (int(item_id), content),
                )
            except Exception:
                pass
        return int(item_id)

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        return memory_item_service.get_item(item_id)

    def list_items(
        self,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: str = "active",
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return memory_item_service.list_items(
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )

    def get_memory_source(self, memory_item_id: int) -> Dict[str, Any]:
        rows = self.db.execute_query(
            """
            SELECT
              c.id AS chunk_id,
              c.document_id,
              c.chunk_index,
              d.file_name,
              d.storage_path,
              d.mime_type,
              d.file_ext
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.memory_item_id = ?
            LIMIT 1
            """,
            (int(memory_item_id),),
        )
        if not rows:
            return {}
        row = rows[0]
        return {
            "chunk_id": int(row["chunk_id"]),
            "document_id": int(row["document_id"]),
            "chunk_index": int(row["chunk_index"]),
            "file_name": str(row["file_name"] or ""),
            "storage_path": str(row["storage_path"] or ""),
            "mime_type": str(row["mime_type"] or ""),
            "file_ext": str(row["file_ext"] or ""),
        }

    def keyword_search(
        self,
        query: str,
        conversation_id: Optional[str],
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: int = 10,
    ) -> List[StorageHit]:
        visibility = self._visibility_clause(conversation_id=conversation_id, scope=scope)
        if visibility is None:
            return []

        visibility_clause, visibility_params = visibility
        params: List[Any] = []
        rows = []

        if self.ensure_fts5():
            match_query = self._normalize_keyword_query(query)
            if match_query:
                clauses = ["m.status = 'active'", visibility_clause, "f.content MATCH ?"]
                params = list(visibility_params) + [match_query]
                if scope:
                    clauses.append("m.scope = ?")
                    params.append(scope)
                if kind:
                    clauses.append("m.kind = ?")
                    params.append(kind)
                where = " AND ".join(clauses)
                rows = self.db.execute_query(
                    f"""
                    SELECT
                      m.id,
                      m.conversation_id,
                      m.scope,
                      m.kind,
                      m.content,
                      m.confidence,
                      m.tags_json,
                      m.updated_at,
                      bm25(memory_items_fts) AS rank
                    FROM memory_items_fts f
                    JOIN memory_items m ON m.id = f.rowid
                    WHERE {where}
                    ORDER BY rank ASC, m.updated_at DESC, m.id DESC
                    LIMIT ?
                    """,
                    tuple(params + [int(k)]),
                )

        if not rows:
            fallback = memory_item_service.text_search(
                q=query,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=k,
            )
            return [
                StorageHit(
                    memory_item_id=int(item["id"]),
                    conversation_id=item.get("conversation_id"),
                    scope=str(item.get("scope") or ""),
                    kind=str(item.get("kind") or ""),
                    content=str(item.get("content") or ""),
                    confidence=float(item.get("confidence") or 0.0),
                    tags=list(item.get("tags") or []),
                    updated_at=str(item.get("updated_at") or ""),
                    keyword_score=1.0,
                    source=self.get_memory_source(int(item["id"])),
                )
                for item in fallback
            ]

        hits: List[StorageHit] = []
        for row in rows:
            rank = float(row["rank"] or 0.0)
            keyword_score = 1.0 / (1.0 + max(rank, 0.0))
            hits.append(
                StorageHit(
                    memory_item_id=int(row["id"]),
                    conversation_id=row["conversation_id"],
                    scope=str(row["scope"] or ""),
                    kind=str(row["kind"] or ""),
                    content=str(row["content"] or ""),
                    confidence=float(row["confidence"] or 0.0),
                    tags=json.loads(row["tags_json"] or "[]"),
                    updated_at=str(row["updated_at"] or ""),
                    keyword_score=keyword_score,
                    source=self.get_memory_source(int(row["id"])),
                )
            )
        return hits


memory_storage = MemoryStorage()
