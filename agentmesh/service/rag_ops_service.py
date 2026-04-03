from __future__ import annotations

import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..common.database import conversation_db_manager, memory_db_manager, vector_db_manager
from .rag_ingest_service import rag_ingest_service
from .vector_memory_service import vector_memory_service


class RagOpsService:
    def __init__(self) -> None:
        self.memory_db = memory_db_manager
        self.vector_db = vector_db_manager
        self.conversation_db = conversation_db_manager
        self._rebuild_lock = threading.Lock()

    @staticmethod
    def _query_one(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> Tuple[Any, ...]:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return tuple(row) if row else tuple()

    @staticmethod
    def _fetch_active_ids(conn: sqlite3.Connection) -> List[int]:
        cur = conn.cursor()
        cur.execute("SELECT id FROM memory_items WHERE status='active'")
        return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

    def _count_embeddings_for_ids(self, conn: sqlite3.Connection, ids: List[int], model: str) -> int:
        if not ids or not model:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        row = self._query_one(
            conn,
            f"SELECT COUNT(DISTINCT memory_item_id) FROM memory_embeddings WHERE model = ? AND memory_item_id IN ({placeholders})",
            tuple([model] + ids),
        )
        return int(row[0] or 0) if row else 0

    def _count_residue_embeddings(self, conn: sqlite3.Connection, ids: List[int], model: str) -> int:
        if not ids or not model:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        row = self._query_one(
            conn,
            f"SELECT COUNT(*) FROM memory_embeddings WHERE model != ? AND memory_item_id IN ({placeholders})",
            tuple([model] + ids),
        )
        return int(row[0] or 0) if row else 0

    @staticmethod
    def _backup_file(path: Path, backup_dir: Path) -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        dst = backup_dir / f"{path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        shutil.copy2(path, dst)
        return dst

    @staticmethod
    def _fetch_ids(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> List[int]:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

    @staticmethod
    def _build_document_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "document_id": int(row["id"]),
                    "file_name": str(row["file_name"] or ""),
                    "status": str(row["status"] or ""),
                    "file_hash": str(row["file_hash"] or ""),
                    "updated_at": str(row["updated_at"] or ""),
                    "created_at": str(row["created_at"] or ""),
                    "active_chunk_count": int(row["active_chunk_count"] or 0),
                    "chunk_total": int(row["chunk_total"] or 0),
                    "title": str(row["title"] or ""),
                }
            )
        return items

    def get_document_history(self, document_id: int, limit: int = 20) -> Dict[str, Any]:
        rows = self.memory_db.execute_query(
            """
            SELECT id, file_name
            FROM rag_documents
            WHERE id = ?
            """,
            (int(document_id),),
        )
        if not rows:
            raise ValueError("Document not found")
        file_name = str(rows[0]["file_name"] or "")
        history_rows = self.memory_db.execute_query(
            """
            SELECT
              d.id,
              d.file_name,
              d.status,
              d.file_hash,
              d.created_at,
              d.updated_at,
              COALESCE(json_extract(a.metadata_json, '$.title'), '') AS title,
              COUNT(c.id) AS chunk_total,
              SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
            FROM rag_documents d
            LEFT JOIN rag_document_annotations a ON a.document_id = d.id
            LEFT JOIN rag_chunks c ON c.document_id = d.id
            WHERE d.file_name = ?
            GROUP BY d.id, d.file_name, d.status, d.file_hash, d.created_at, d.updated_at, a.metadata_json
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ?
            """,
            (file_name, int(limit)),
        )
        items = self._build_document_rows(history_rows)
        return {
            "document_id": int(document_id),
            "file_name": file_name,
            "version_count": len(items),
            "items": items,
        }

    def get_overview(self, history_document_id: int | None = None, history_limit: int = 20) -> Dict[str, Any]:
        runtime = vector_memory_service.current_runtime_info()
        configured_model = str(runtime.get("model") or "").strip()

        with sqlite3.connect(self.memory_db.db_path) as mem_conn, sqlite3.connect(self.vector_db.db_path) as vec_conn:
            mem_conn.row_factory = sqlite3.Row
            vec_conn.row_factory = sqlite3.Row

            active_ids = self._fetch_active_ids(mem_conn)
            active_memory_items = len(active_ids)
            total_embeddings = int(self._query_one(vec_conn, "SELECT COUNT(*) FROM memory_embeddings")[0] or 0)

            active_model_coverage = self._count_embeddings_for_ids(vec_conn, active_ids, configured_model)
            residue_embeddings = self._count_residue_embeddings(vec_conn, active_ids, configured_model)

            model_rows = vec_conn.execute(
                """
                SELECT model, COUNT(*) AS cnt, MIN(dim) AS min_dim, MAX(dim) AS max_dim
                FROM memory_embeddings
                GROUP BY model
                ORDER BY cnt DESC, model ASC
                """
            ).fetchall()
            model_distribution = [
                {
                    "model": str(row["model"] or ""),
                    "count": int(row["cnt"] or 0),
                    "min_dim": int(row["min_dim"] or 0),
                    "max_dim": int(row["max_dim"] or 0),
                    "is_active_model": str(row["model"] or "") == configured_model,
                }
                for row in model_rows
            ]

            doc_stats = self._query_one(
                mem_conn,
                """
                SELECT
                  COUNT(*) AS total_documents,
                  SUM(CASE WHEN status='indexed' THEN 1 ELSE 0 END) AS indexed_documents,
                  SUM(CASE WHEN status='uploaded' THEN 1 ELSE 0 END) AS uploaded_documents,
                  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_documents
                FROM rag_documents
                """,
            )
            chunk_stats = self._query_one(
                mem_conn,
                """
                SELECT
                  COUNT(*) AS total_chunks,
                  SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_chunks
                FROM rag_chunks
                """,
            )
            orphan_doc_chunks = int(
                self._query_one(
                    mem_conn,
                    """
                    SELECT COUNT(*)
                    FROM memory_items m
                    LEFT JOIN rag_chunks c ON c.memory_item_id = m.id
                    WHERE m.status='active'
                      AND m.scope='knowledge_base'
                      AND m.kind='doc_chunk'
                      AND c.id IS NULL
                    """,
                )[0]
                or 0
            )
            indexed_without_chunks = int(
                self._query_one(
                    mem_conn,
                    """
                    SELECT COUNT(*)
                    FROM rag_documents d
                    LEFT JOIN (
                      SELECT document_id, SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
                      FROM rag_chunks
                      GROUP BY document_id
                    ) c ON c.document_id = d.id
                    WHERE d.status='indexed' AND COALESCE(c.active_chunk_count, 0) = 0
                    """,
                )[0]
                or 0
            )

            scope_rows = mem_conn.execute(
                """
                SELECT scope, kind, status, COUNT(*) AS cnt
                FROM memory_items
                GROUP BY scope, kind, status
                ORDER BY scope, kind, status
                """
            ).fetchall()
            memory_distribution = [
                {
                    "scope": str(row["scope"] or ""),
                    "kind": str(row["kind"] or ""),
                    "status": str(row["status"] or ""),
                    "count": int(row["cnt"] or 0),
                }
                for row in scope_rows
            ]

            duplicate_hash_rows = mem_conn.execute(
                """
                SELECT file_hash, COUNT(*) AS cnt
                FROM rag_documents
                GROUP BY file_hash
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC, file_hash ASC
                LIMIT 10
                """
            ).fetchall()
            duplicate_groups: List[Dict[str, Any]] = []
            for row in duplicate_hash_rows:
                docs = mem_conn.execute(
                    """
                    SELECT
                      d.id,
                      d.file_name,
                      d.status,
                      d.file_hash,
                      d.created_at,
                      d.updated_at,
                      COALESCE(json_extract(a.metadata_json, '$.title'), '') AS title,
                      COUNT(c.id) AS chunk_total,
                      SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
                    FROM rag_documents d
                    LEFT JOIN rag_document_annotations a ON a.document_id = d.id
                    LEFT JOIN rag_chunks c ON c.document_id = d.id
                    WHERE d.file_hash = ?
                    GROUP BY d.id, d.file_name, d.status, d.file_hash, d.created_at, d.updated_at, a.metadata_json
                    ORDER BY d.updated_at DESC, d.id DESC
                    """,
                    (str(row["file_hash"] or ""),),
                ).fetchall()
                duplicate_groups.append(
                    {
                        "file_hash": str(row["file_hash"] or ""),
                        "count": int(row["cnt"] or 0),
                        "items": self._build_document_rows(docs),
                    }
                )

            version_group_rows = mem_conn.execute(
                """
                SELECT file_name, COUNT(*) AS cnt, MAX(updated_at) AS latest_updated_at
                FROM rag_documents
                GROUP BY file_name
                HAVING COUNT(*) > 1
                ORDER BY latest_updated_at DESC, cnt DESC, file_name ASC
                LIMIT 10
                """
            ).fetchall()
            version_groups: List[Dict[str, Any]] = []
            for row in version_group_rows:
                docs = mem_conn.execute(
                    """
                    SELECT
                      d.id,
                      d.file_name,
                      d.status,
                      d.file_hash,
                      d.created_at,
                      d.updated_at,
                      COALESCE(json_extract(a.metadata_json, '$.title'), '') AS title,
                      COUNT(c.id) AS chunk_total,
                      SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
                    FROM rag_documents d
                    LEFT JOIN rag_document_annotations a ON a.document_id = d.id
                    LEFT JOIN rag_chunks c ON c.document_id = d.id
                    WHERE d.file_name = ?
                    GROUP BY d.id, d.file_name, d.status, d.file_hash, d.created_at, d.updated_at, a.metadata_json
                    ORDER BY d.updated_at DESC, d.id DESC
                    """,
                    (str(row["file_name"] or ""),),
                ).fetchall()
                version_groups.append(
                    {
                        "file_name": str(row["file_name"] or ""),
                        "count": int(row["cnt"] or 0),
                        "latest_updated_at": str(row["latest_updated_at"] or ""),
                        "items": self._build_document_rows(docs),
                    }
                )

        history = None
        if history_document_id:
            history = self.get_document_history(document_id=int(history_document_id), limit=int(history_limit))

        return {
            "runtime": {
                "profile": str(runtime.get("profile") or ""),
                "provider": str(runtime.get("provider") or ""),
                "model": configured_model,
                "api_base": str(runtime.get("api_base") or ""),
                "dim": int(runtime.get("dim") or 0),
            },
            "stats": {
                "active_memory_items": int(active_memory_items),
                "total_memory_embeddings": int(total_embeddings),
                "active_model_coverage": int(active_model_coverage),
                "active_model_coverage_ratio": (
                    float(active_model_coverage) / float(active_memory_items) if active_memory_items > 0 else 1.0
                ),
                "residual_non_current_embeddings_on_active": int(residue_embeddings),
                "orphan_doc_chunks": int(orphan_doc_chunks),
                "indexed_documents_without_active_chunks": int(indexed_without_chunks),
                "total_documents": int(doc_stats[0] or 0) if doc_stats else 0,
                "indexed_documents": int(doc_stats[1] or 0) if doc_stats else 0,
                "uploaded_documents": int(doc_stats[2] or 0) if doc_stats else 0,
                "failed_documents": int(doc_stats[3] or 0) if doc_stats else 0,
                "total_chunks": int(chunk_stats[0] or 0) if chunk_stats else 0,
                "active_chunks": int(chunk_stats[1] or 0) if chunk_stats else 0,
            },
            "model_distribution": model_distribution,
            "memory_distribution": memory_distribution,
            "duplicate_groups": duplicate_groups,
            "version_groups": version_groups,
            "document_history": history,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def rebuild_indices(
        self,
        chunk_size: int = 700,
        overlap: int = 100,
        skip_reindex: bool = False,
    ) -> Dict[str, Any]:
        if not self._rebuild_lock.acquire(blocking=False):
            raise RuntimeError("RAG rebuild is already running")
        try:
            backup_dir = Path(self.memory_db.db_path).resolve().parents[1] / "backups" / "rag-rebuild"
            backup_files: List[str] = []
            for path in (Path(self.conversation_db.db_path), Path(self.memory_db.db_path), Path(self.vector_db.db_path)):
                if path.exists():
                    backup_files.append(str(self._backup_file(path, backup_dir)))

            mem = sqlite3.connect(self.memory_db.db_path)
            vec = sqlite3.connect(self.vector_db.db_path)
            try:
                mem.row_factory = sqlite3.Row
                vec.row_factory = sqlite3.Row

                long_term_ids = self._fetch_ids(
                    mem,
                    """
                    SELECT id
                    FROM memory_items
                    WHERE scope='knowledge_base' AND kind='long_term_profile'
                    """,
                )
                orphan_doc_ids = self._fetch_ids(
                    mem,
                    """
                    SELECT m.id
                    FROM memory_items m
                    LEFT JOIN rag_chunks c ON c.memory_item_id = m.id
                    WHERE m.status='active'
                      AND m.scope='knowledge_base'
                      AND m.kind='doc_chunk'
                      AND c.id IS NULL
                    """,
                )
                docs_to_ingest = self._fetch_ids(
                    mem,
                    """
                    SELECT d.id
                    FROM rag_documents d
                    LEFT JOIN (
                      SELECT document_id, SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
                      FROM rag_chunks
                      GROUP BY document_id
                    ) c ON c.document_id = d.id
                    WHERE COALESCE(d.raw_text, '') != ''
                      AND COALESCE(c.active_chunk_count, 0) = 0
                    ORDER BY d.id
                    """,
                )

                if long_term_ids:
                    placeholders = ",".join(["?"] * len(long_term_ids))
                    mem.execute(
                        f"UPDATE memory_items SET scope='long_term', updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                        tuple(long_term_ids),
                    )
                    mem.commit()

                if orphan_doc_ids:
                    placeholders = ",".join(["?"] * len(orphan_doc_ids))
                    mem.execute(
                        f"UPDATE memory_items SET status='deprecated', updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                        tuple(orphan_doc_ids),
                    )
                    vec.execute(
                        f"DELETE FROM memory_embeddings WHERE memory_item_id IN ({placeholders})",
                        tuple(orphan_doc_ids),
                    )
                    mem.commit()
                    vec.commit()

                ingested_docs: List[Dict[str, Any]] = []
                for doc_id in docs_to_ingest:
                    result = rag_ingest_service.ingest_document(
                        document_id=int(doc_id),
                        chunk_size=int(chunk_size),
                        overlap=int(overlap),
                    )
                    ingested_docs.append(result)

                runtime = vector_memory_service.current_runtime_info()
                target_model = str(runtime.get("model") or "").strip()
                active_ids = self._fetch_ids(mem, "SELECT id FROM memory_items WHERE status='active'")
                cleared_non_target = 0
                rebuilt_embeddings = 0

                if target_model and active_ids:
                    cleared_non_target = int(
                        vector_memory_service.delete_embeddings_for_items(active_ids, keep_model=target_model)
                    )

                if not skip_reindex:
                    for memory_item_id in active_ids:
                        vector_memory_service.upsert_embedding(int(memory_item_id))
                    rebuilt_embeddings = len(active_ids)

                for manager in (self.memory_db, self.vector_db, self.conversation_db):
                    try:
                        manager.checkpoint_and_compact()
                    except Exception:
                        pass

                post_overview = self.get_overview()
                return {
                    "backup_dir": str(backup_dir),
                    "backup_files": backup_files,
                    "migrated_long_term_items": len(long_term_ids),
                    "deprecated_orphan_doc_chunks": len(orphan_doc_ids),
                    "docs_to_reingest": docs_to_ingest,
                    "ingested_docs": ingested_docs,
                    "target_model": target_model,
                    "active_memory_items": len(active_ids),
                    "cleared_non_target_embeddings": int(cleared_non_target),
                    "rebuilt_embeddings": int(rebuilt_embeddings),
                    "post_overview": post_overview,
                    "completed_at": datetime.now().isoformat(timespec="seconds"),
                }
            finally:
                mem.close()
                vec.close()
        finally:
            self._rebuild_lock.release()


rag_ops_service = RagOpsService()
