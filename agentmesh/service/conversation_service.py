import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..common.database import conversation_db_manager, memory_db_manager, vector_db_manager


@dataclass(frozen=True)
class ConversationMessageRow:
    id: int
    conversation_id: str
    role: str
    content: str
    ts: str
    seq: int
    meta: Dict[str, Any]


@dataclass(frozen=True)
class ConversationSummaryRow:
    conversation_id: str
    summary: str
    window_start_seq: int
    window_end_seq: int
    updated_at: str
    meta: Dict[str, Any]


class ConversationService:
    def __init__(self):
        self.db = conversation_db_manager

    def create_conversation(self, title: Optional[str] = None) -> str:
        conversation_id = str(uuid.uuid4())
        self.db.execute_update(
            """
            INSERT INTO conversations (conversation_id, title, status, created_at, updated_at)
            VALUES (?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (conversation_id, title),
        )
        return conversation_id

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query(
            """
            SELECT conversation_id, title, status, created_at, updated_at
            FROM conversations
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "conversation_id": r["conversation_id"],
            "title": r["title"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    @staticmethod
    def _decode_meta(meta_json: Any) -> Dict[str, Any]:
        try:
            return json.loads(meta_json or "{}")
        except Exception:
            return {}

    @staticmethod
    def _build_preview(content: Any, role: Any) -> str:
        text = str(content or "").strip().replace("\n", " ")
        text = " ".join(text.split())
        if not text:
            return ""
        prefix = ""
        role_text = str(role or "").strip().lower()
        if role_text == "user":
            prefix = "你："
        elif role_text == "assistant":
            prefix = "助手："
        return f"{prefix}{text[:120]}"

    def _row_to_conversation_overview(self, row: Any) -> Dict[str, Any]:
        task_meta = self._decode_meta(row["last_task_meta_json"])
        team_meta = self._decode_meta(row["last_team_meta_json"])
        return {
            "conversation_id": row["conversation_id"],
            "title": row["title"],
            "status": row["status"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "message_count": int(row["message_count"] or 0),
            "preview": self._build_preview(row["last_message_content"], row["last_message_role"]),
            "last_message_at": str(row["last_message_ts"] or ""),
            "latest_task_id": task_meta.get("task_id"),
            "latest_team": team_meta.get("team"),
        }

    def list_conversations(
        self,
        status: str = "active",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if status:
            clauses.append("c.status = ?")
            params.append(status)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.db.execute_query(
            f"""
            SELECT
              c.conversation_id,
              c.title,
              c.status,
              c.created_at,
              c.updated_at,
              (
                SELECT COUNT(*)
                FROM conversation_messages cmc
                WHERE cmc.conversation_id = c.conversation_id
              ) AS message_count,
              (
                SELECT cm.content
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_message_content,
              (
                SELECT cm.role
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_message_role,
              (
                SELECT cm.ts
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_message_ts,
              (
                SELECT cm.meta_json
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_meta_json,
              (
                SELECT cm.meta_json
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                  AND cm.meta_json LIKE '%"task_id"%'
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_task_meta_json,
              (
                SELECT cm.meta_json
                FROM conversation_messages cm
                WHERE cm.conversation_id = c.conversation_id
                  AND cm.meta_json LIKE '%"team"%'
                ORDER BY cm.seq DESC, cm.id DESC
                LIMIT 1
              ) AS last_team_meta_json
            FROM conversations c
            WHERE {where}
            ORDER BY c.updated_at DESC, c.created_at DESC, c.conversation_id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [int(limit), int(offset)]),
        )
        return [self._row_to_conversation_overview(row) for row in rows]

    def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: List[str] = []
        params: List[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if not fields:
            return self.get_conversation(conversation_id)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(conversation_id)
        affected = self.db.execute_update(
            f"""
            UPDATE conversations
            SET {", ".join(fields)}
            WHERE conversation_id = ?
            """,
            tuple(params),
        )
        if affected <= 0:
            return None
        return self.get_conversation(conversation_id)

    def _get_next_seq(self, conversation_id: str) -> int:
        rows = self.db.execute_query(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM conversation_messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        max_seq = int(rows[0]["max_seq"] or 0) if rows else 0
        return max_seq + 1

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        meta: Optional[Dict[str, Any]] = None,
        ts_iso: Optional[str] = None,
    ) -> ConversationMessageRow:
        ts = ts_iso or datetime.now().isoformat()
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                seq_row = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM conversation_messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
                seq = int(seq_row["max_seq"] or 0) + 1 if seq_row else 1

                cursor = conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content, ts, seq, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (conversation_id, role, content, ts, seq, meta_json),
                )
                conn.execute(
                    "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                    (conversation_id,),
                )
                row = conn.execute(
                    """
                    SELECT id, conversation_id, role, content, ts, seq, meta_json
                    FROM conversation_messages
                    WHERE id = ?
                    """,
                    (int(cursor.lastrowid),),
                ).fetchone()
                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                raise

        if row is None:
            raise ValueError(f"Failed to append message for conversation {conversation_id}")

        return ConversationMessageRow(
            id=int(row["id"]),
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            ts=row["ts"],
            seq=int(row["seq"]),
            meta=json.loads(row["meta_json"] or "{}"),
        )

    def list_messages(self, conversation_id: str, limit: int = 200, offset: int = 0) -> List[ConversationMessageRow]:
        rows = self.db.execute_query(
            """
            SELECT id, conversation_id, role, content, ts, seq, meta_json
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY seq ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (conversation_id, limit, offset),
        )
        out: List[ConversationMessageRow] = []
        for r in rows:
            out.append(
                ConversationMessageRow(
                    id=int(r["id"]),
                    conversation_id=r["conversation_id"],
                    role=r["role"],
                    content=r["content"],
                    ts=r["ts"],
                    seq=int(r["seq"]),
                    meta=json.loads(r["meta_json"] or "{}"),
                )
            )
        return out

    def list_recent_messages(self, conversation_id: str, limit: int = 20) -> List[ConversationMessageRow]:
        rows = self.db.execute_query(
            """
            SELECT id, conversation_id, role, content, ts, seq, meta_json
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY seq DESC, id DESC
            LIMIT ?
            """,
            (conversation_id, int(limit)),
        )
        tmp: List[ConversationMessageRow] = []
        for r in rows:
            tmp.append(
                ConversationMessageRow(
                    id=int(r["id"]),
                    conversation_id=r["conversation_id"],
                    role=r["role"],
                    content=r["content"],
                    ts=r["ts"],
                    seq=int(r["seq"]),
                    meta=json.loads(r["meta_json"] or "{}"),
                )
            )
        return list(reversed(tmp))

    def get_summary(self, conversation_id: str) -> Optional[ConversationSummaryRow]:
        rows = self.db.execute_query(
            """
            SELECT conversation_id, summary, window_start_seq, window_end_seq, updated_at, meta_json
            FROM conversation_summaries
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return ConversationSummaryRow(
            conversation_id=r["conversation_id"],
            summary=r["summary"],
            window_start_seq=int(r["window_start_seq"] or 0),
            window_end_seq=int(r["window_end_seq"] or 0),
            updated_at=r["updated_at"],
            meta=json.loads(r["meta_json"] or "{}"),
        )

    def upsert_summary(
        self,
        conversation_id: str,
        summary: str,
        window_start_seq: int,
        window_end_seq: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ConversationSummaryRow:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        self.db.execute_update(
            """
            INSERT INTO conversation_summaries (conversation_id, summary, window_start_seq, window_end_seq, updated_at, meta_json)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
              summary=excluded.summary,
              window_start_seq=excluded.window_start_seq,
              window_end_seq=excluded.window_end_seq,
              updated_at=CURRENT_TIMESTAMP,
              meta_json=excluded.meta_json
            """,
            (conversation_id, summary, int(window_start_seq), int(window_end_seq), meta_json),
        )
        return self.get_summary(conversation_id)  # type: ignore[return-value]

    def get_messages_range(self, conversation_id: str, start_seq: int, end_seq: int) -> List[ConversationMessageRow]:
        rows = self.db.execute_query(
            """
            SELECT id, conversation_id, role, content, ts, seq, meta_json
            FROM conversation_messages
            WHERE conversation_id = ? AND seq >= ? AND seq <= ?
            ORDER BY seq ASC, id ASC
            """,
            (conversation_id, int(start_seq), int(end_seq)),
        )
        out: List[ConversationMessageRow] = []
        for r in rows:
            out.append(
                ConversationMessageRow(
                    id=int(r["id"]),
                    conversation_id=r["conversation_id"],
                    role=r["role"],
                    content=r["content"],
                    ts=r["ts"],
                    seq=int(r["seq"]),
                    meta=json.loads(r["meta_json"] or "{}"),
                )
            )
        return out

    def get_max_seq(self, conversation_id: str) -> int:
        rows = self.db.execute_query(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM conversation_messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        return int(rows[0]["max_seq"] or 0) if rows else 0

    def delete_conversation(self, conversation_id: str) -> Dict[str, Any]:
        conv = self.get_conversation(conversation_id)
        if not conv:
            raise ValueError("Conversation not found")

        message_rows = self.db.execute_query(
            """
            SELECT meta_json
            FROM conversation_messages
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        task_ids = set()
        for row in message_rows:
            meta = self._decode_meta(row["meta_json"])
            task_id = str(meta.get("task_id") or "").strip()
            if task_id:
                task_ids.add(task_id)

        memory_rows = memory_db_manager.execute_query(
            """
            SELECT id
            FROM memory_items
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        memory_ids = [int(r["id"]) for r in memory_rows]

        with self.db.get_connection() as conv_conn, memory_db_manager.get_connection() as mem_conn, vector_db_manager.get_connection() as vec_conn:
            try:
                conv_conn.execute("BEGIN IMMEDIATE")
                mem_conn.execute("BEGIN IMMEDIATE")
                vec_conn.execute("BEGIN IMMEDIATE")

                if task_ids:
                    placeholders = ",".join(["?"] * len(task_ids))
                    conv_conn.execute(
                        f"DELETE FROM workflow_events WHERE task_id IN ({placeholders})",
                        tuple(task_ids),
                    )
                    conv_conn.execute(
                        f"DELETE FROM tasks WHERE task_id IN ({placeholders})",
                        tuple(task_ids),
                    )

                conv_conn.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,))
                conv_conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
                conv_conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))

                if memory_ids:
                    placeholders = ",".join(["?"] * len(memory_ids))
                    vec_conn.execute(
                        f"DELETE FROM memory_embeddings WHERE memory_item_id IN ({placeholders})",
                        tuple(memory_ids),
                    )
                    mem_conn.execute(
                        f"DELETE FROM memory_items WHERE id IN ({placeholders})",
                        tuple(memory_ids),
                    )

                vec_conn.commit()
                mem_conn.commit()
                conv_conn.commit()
            except Exception:
                vec_conn.rollback()
                mem_conn.rollback()
                conv_conn.rollback()
                raise

        try:
            from .vector_memory_service import vector_memory_service

            vector_memory_service.invalidate_index_cache(conversation_id=conversation_id)
        except Exception:
            pass

        for manager in (conversation_db_manager, memory_db_manager, vector_db_manager):
            try:
                manager.checkpoint_and_compact()
            except Exception:
                pass

        return {
            "conversation_id": conversation_id,
            "deleted": True,
            "deleted_message_count": len(message_rows),
            "deleted_task_count": len(task_ids),
            "deleted_memory_item_count": len(memory_ids),
        }


conversation_service = ConversationService()
