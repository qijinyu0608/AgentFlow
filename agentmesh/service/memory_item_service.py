import json
from typing import Any, Dict, List, Optional

from ..common.database import memory_db_manager


class MemoryItemService:
    def __init__(self):
        self.db = memory_db_manager

    @staticmethod
    def _invalidate_vector_cache(conversation_id: Optional[str]) -> None:
        try:
            from .vector_memory_service import vector_memory_service

            vector_memory_service.invalidate_index_cache(conversation_id=conversation_id)
        except Exception:
            # Cache invalidation is best-effort; DB write already succeeded.
            pass

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
        scope = (scope or "conversation").strip()
        kind = (kind or "fact").strip()
        conversation_id = (conversation_id or "").strip() or None

        if scope == "conversation" and not conversation_id:
            raise ValueError("conversation scope requires conversation_id")
        if scope != "conversation" and conversation_id is not None:
            raise ValueError(f"{scope} scope does not allow conversation_id")

        if deprecate_previous:
            self._deprecate_similar(scope=scope, kind=kind, conversation_id=conversation_id, tags=tags)

        tags_json = json.dumps(tags or [], ensure_ascii=False)
        item_id = self.db.execute_insert(
            """
            INSERT INTO memory_items (conversation_id, scope, kind, content, status, source_message_id, confidence, tags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (conversation_id, scope, kind, content, source_message_id, float(confidence), tags_json),
        )
        self._invalidate_vector_cache(conversation_id)
        return int(item_id)

    @staticmethod
    def _search_visibility_clause(conversation_id: Optional[str], scope: Optional[str]) -> Optional[tuple]:
        normalized_scope = (scope or "").strip() or None
        normalized_conversation_id = (conversation_id or "").strip() or None

        if normalized_scope == "conversation" and not normalized_conversation_id:
            return None

        if normalized_conversation_id:
            return (
                "((scope = 'conversation' AND conversation_id = ?) OR (scope != 'conversation' AND conversation_id IS NULL))",
                [normalized_conversation_id],
            )
        return ("conversation_id IS NULL AND scope != 'conversation'", [])

    def _deprecate_similar(
        self,
        scope: str,
        kind: str,
        conversation_id: Optional[str],
        tags: Optional[List[str]],
    ) -> None:
        # Conservative strategy:
        # - If tags provided, deprecate active items that share at least one tag within same scope/kind/(conversation)
        # - Else, only deprecate by exact (scope,kind,conversation) to avoid over-deprecating.
        if tags:
            # coarse match by tags_json LIKE
            clauses = ["scope = ?", "kind = ?", "status = 'active'"]
            params: List[Any] = [scope, kind]
            if conversation_id is None:
                clauses.append("conversation_id IS NULL")
            else:
                clauses.append("conversation_id = ?")
                params.append(conversation_id)
            tag_like = " OR ".join(["tags_json LIKE ?"] * len(tags))
            clauses.append(f"({tag_like})")
            params.extend([f"%{t}%" for t in tags])
            where = " AND ".join(clauses)
            self.db.execute_update(
                f"UPDATE memory_items SET status='deprecated', updated_at=CURRENT_TIMESTAMP WHERE {where}",
                tuple(params),
            )
            self._invalidate_vector_cache(conversation_id)
        else:
            clauses = ["scope = ?", "kind = ?", "status = 'active'"]
            params2: List[Any] = [scope, kind]
            if conversation_id is None:
                clauses.append("conversation_id IS NULL")
            else:
                clauses.append("conversation_id = ?")
                params2.append(conversation_id)
            where = " AND ".join(clauses)
            self.db.execute_update(
                f"UPDATE memory_items SET status='deprecated', updated_at=CURRENT_TIMESTAMP WHERE {where}",
                tuple(params2),
            )
            self._invalidate_vector_cache(conversation_id)

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query(
            """
            SELECT id, conversation_id, scope, kind, content, status, source_message_id, confidence, tags_json, created_at, updated_at
            FROM memory_items
            WHERE id = ?
            """,
            (int(item_id),),
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "id": int(r["id"]),
            "conversation_id": r["conversation_id"],
            "scope": r["scope"],
            "kind": r["kind"],
            "content": r["content"],
            "status": r["status"],
            "source_message_id": r["source_message_id"],
            "confidence": float(r["confidence"] or 0.0),
            "tags": json.loads(r["tags_json"] or "[]"),
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        }

    def list_items(
        self,
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: str = "active",
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if conversation_id is None:
            clauses.append("conversation_id IS NULL")
        else:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)
        if scope:
            clauses.append("scope = ?")
            params.append(scope)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.db.execute_query(
            f"""
            SELECT id, conversation_id, scope, kind, content, status, source_message_id, confidence, tags_json, created_at, updated_at
            FROM memory_items
            WHERE {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [int(limit), int(offset)]),
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r["id"]),
                    "conversation_id": r["conversation_id"],
                    "scope": r["scope"],
                    "kind": r["kind"],
                    "content": r["content"],
                    "status": r["status"],
                    "source_message_id": r["source_message_id"],
                    "confidence": float(r["confidence"] or 0.0),
                    "tags": json.loads(r["tags_json"] or "[]"),
                    "created_at": str(r["created_at"]),
                    "updated_at": str(r["updated_at"]),
                }
            )
        return out

    def text_search(
        self,
        q: str,
        conversation_id: Optional[str],
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        clauses = ["status = 'active'", "content LIKE ?"]
        params: List[Any] = [f"%{q}%"]
        visibility = self._search_visibility_clause(conversation_id=conversation_id, scope=scope)
        if visibility is None:
            return []
        visibility_clause, visibility_params = visibility
        clauses.append(visibility_clause)
        params.extend(visibility_params)
        if scope:
            clauses.append("scope = ?")
            params.append(scope)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = " AND ".join(clauses)
        rows = self.db.execute_query(
            f"""
            SELECT id, conversation_id, scope, kind, content, status, source_message_id, confidence, tags_json, created_at, updated_at
            FROM memory_items
            WHERE {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params + [int(k)]),
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r["id"]),
                    "conversation_id": r["conversation_id"],
                    "scope": r["scope"],
                    "kind": r["kind"],
                    "content": r["content"],
                    "confidence": float(r["confidence"] or 0.0),
                    "tags": json.loads(r["tags_json"] or "[]"),
                    "updated_at": str(r["updated_at"]),
                }
            )
        return out


memory_item_service = MemoryItemService()
