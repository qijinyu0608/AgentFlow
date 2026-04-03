from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

from ..common.database import memory_db_manager, vector_db_manager
from .memory_item_service import memory_item_service
from .vector_memory_service import vector_memory_service


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_RAW_TEXT_CHARS = 300000
DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 100
ALLOWED_EXTENSIONS = {".txt", ".docx"}


@dataclass
class ParsedDocument:
    text: str
    paragraphs: List[str]


class RagIngestService:
    @staticmethod
    def _detect_extension(filename: str, mime_type: str) -> str:
        ext = Path(filename or "").suffix.lower()
        if ext:
            return ext
        mt = (mime_type or "").lower()
        if mt.startswith("text/plain"):
            return ".txt"
        if "officedocument.wordprocessingml.document" in mt:
            return ".docx"
        return ""

    def __init__(self) -> None:
        self.db = memory_db_manager

    def _workspace_root(self) -> Path:
        try:
            import agentmesh  # local import to avoid hard dependency during utility tests
            return Path(agentmesh.get_workspace()).expanduser()
        except Exception:
            return Path.cwd()

    def _upload_dir(self) -> Path:
        d = self._workspace_root() / ".rag_uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _parse_txt(self, content: bytes) -> ParsedDocument:
        text = content.decode("utf-8", errors="ignore")
        cleaned = self._clean_text(text)
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        return ParsedDocument(text=cleaned, paragraphs=paragraphs)

    def _parse_docx(self, content: bytes) -> ParsedDocument:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(content)) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: List[str] = []
        for p in root.findall(".//w:p", ns):
            runs = [t.text or "" for t in p.findall(".//w:t", ns)]
            joined = "".join(runs).strip()
            if joined:
                paragraphs.append(joined)
        text = self._clean_text("\n\n".join(paragraphs))
        return ParsedDocument(text=text, paragraphs=paragraphs)

    def parse_file(self, filename: str, content: bytes, mime_type: str = "") -> ParsedDocument:
        ext = self._detect_extension(filename, mime_type)
        if ext == ".txt":
            parsed = self._parse_txt(content)
        elif ext == ".docx":
            parsed = self._parse_docx(content)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        if len(parsed.text) > MAX_RAW_TEXT_CHARS:
            raise ValueError(
                f"Parsed text too large ({len(parsed.text)} chars). Please split the file and retry."
            )
        return parsed

    def save_upload(
        self,
        filename: str,
        mime_type: str,
        content: bytes,
    ) -> Dict[str, Any]:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"File too large. Max size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.")
        ext = self._detect_extension(filename, mime_type)
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")

        parsed = self.parse_file(filename, content, mime_type=mime_type)
        digest = self._sha256(content)
        existing_rows = self.db.execute_query(
            """
            SELECT
              d.id,
              COALESCE(SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END), 0) AS active_chunk_count
            FROM rag_documents d
            LEFT JOIN rag_chunks c ON c.document_id = d.id
            WHERE d.file_hash = ?
            GROUP BY d.id
            ORDER BY active_chunk_count DESC, d.updated_at DESC, d.id DESC
            LIMIT 1
            """,
            (digest,),
        )
        if existing_rows:
            existing_id = int(existing_rows[0]["id"])
            doc = self.get_document(existing_id, include_paragraphs=True, include_raw_text=False)
            doc["deduplicated"] = True
            doc["dedupe_reason"] = "same_file_hash"
            return doc

        safe_name = Path(filename).name
        storage_name = f"{digest[:16]}_{safe_name}"
        storage_path = self._upload_dir() / storage_name
        storage_path.write_bytes(content)

        doc_id = self.db.execute_insert(
            """
            INSERT INTO rag_documents
              (file_name, file_ext, mime_type, file_size, file_hash, storage_path, raw_text, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                safe_name,
                ext,
                mime_type or "application/octet-stream",
                int(len(content)),
                digest,
                str(storage_path),
                parsed.text,
            ),
        )
        self._ensure_default_annotation(int(doc_id))
        # Upload response should stay lightweight to avoid large payload delays.
        doc = self.get_document(int(doc_id), include_paragraphs=True, include_raw_text=False)
        doc["deduplicated"] = False
        doc["dedupe_reason"] = ""
        return doc

    def _ensure_default_annotation(self, document_id: int) -> None:
        self.db.execute_update(
            """
            INSERT INTO rag_document_annotations (document_id, metadata_json, paragraph_marks_json, created_at, updated_at)
            VALUES (?, '{}', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(document_id) DO NOTHING
            """,
            (int(document_id),),
        )

    def set_annotation(self, document_id: int, metadata: Dict[str, Any], paragraph_marks: List[Dict[str, Any]]) -> None:
        self.db.execute_update(
            """
            INSERT INTO rag_document_annotations (document_id, metadata_json, paragraph_marks_json, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(document_id) DO UPDATE SET
              metadata_json=excluded.metadata_json,
              paragraph_marks_json=excluded.paragraph_marks_json,
              updated_at=CURRENT_TIMESTAMP
            """,
            (int(document_id), json.dumps(metadata or {}, ensure_ascii=False), json.dumps(paragraph_marks or [], ensure_ascii=False)),
        )

    def get_document(
        self,
        document_id: int,
        include_paragraphs: bool = False,
        include_raw_text: bool = False,
    ) -> Dict[str, Any]:
        rows = self.db.execute_query(
            """
            SELECT id, file_name, file_ext, mime_type, file_size, file_hash, storage_path, raw_text, status, created_at, updated_at
            FROM rag_documents
            WHERE id = ?
            """,
            (int(document_id),),
        )
        if not rows:
            raise ValueError("Document not found")
        r = rows[0]
        ann_rows = self.db.execute_query(
            """
            SELECT metadata_json, paragraph_marks_json
            FROM rag_document_annotations
            WHERE document_id = ?
            """,
            (int(document_id),),
        )
        metadata = {}
        paragraph_marks = []
        if ann_rows:
            metadata = json.loads(ann_rows[0]["metadata_json"] or "{}")
            paragraph_marks = json.loads(ann_rows[0]["paragraph_marks_json"] or "[]")

        text = str(r["raw_text"] or "")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        out = {
            "document_id": int(r["id"]),
            "file_name": r["file_name"],
            "file_ext": r["file_ext"],
            "mime_type": r["mime_type"],
            "file_size": int(r["file_size"] or 0),
            "file_hash": r["file_hash"],
            "storage_path": r["storage_path"],
            "status": r["status"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
            "metadata": metadata,
            "paragraph_marks": paragraph_marks,
        }
        if include_raw_text:
            out["raw_text"] = text
        if include_paragraphs:
            out["preview"] = paragraphs[:20]
        return out

    @staticmethod
    def _build_mark_index(paragraph_marks: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        idx: Dict[int, Dict[str, Any]] = {}
        for m in paragraph_marks or []:
            try:
                i = int(m.get("index"))
            except Exception:
                continue
            idx[i] = m
        return idx

    def _apply_marks(self, paragraphs: List[str], paragraph_marks: List[Dict[str, Any]]) -> List[str]:
        marks = self._build_mark_index(paragraph_marks)
        out: List[str] = []
        i = 0
        while i < len(paragraphs):
            cur = paragraphs[i]
            mark = marks.get(i, {})
            action = (mark.get("action") or "").strip().lower()
            if action == "ignore":
                i += 1
                continue
            if action == "merge_with_next" and i + 1 < len(paragraphs):
                merged = f"{cur}\n{paragraphs[i + 1]}".strip()
                out.append(merged)
                i += 2
                continue
            out.append(cur)
            i += 1
        return out

    @staticmethod
    def _chunk_text(paragraphs: List[str], chunk_size: int, overlap: int) -> List[str]:
        chunks: List[str] = []
        buf = ""
        for p in paragraphs:
            candidate = p if not buf else f"{buf}\n\n{p}"
            if len(candidate) <= chunk_size:
                buf = candidate
                continue
            if buf.strip():
                chunks.append(buf.strip())
            if len(p) <= chunk_size:
                buf = p
            else:
                start = 0
                step = max(1, chunk_size - overlap)
                while start < len(p):
                    part = p[start : start + chunk_size].strip()
                    if part:
                        chunks.append(part)
                    start += step
                buf = ""
        if buf.strip():
            chunks.append(buf.strip())
        return chunks

    def ingest_document(
        self,
        document_id: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> Dict[str, Any]:
        doc = self.get_document(int(document_id), include_paragraphs=False, include_raw_text=True)
        text = str(doc.get("raw_text") or "")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        marks = list(doc.get("paragraph_marks") or [])
        metadata = dict(doc.get("metadata") or {})
        tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []

        processed_paragraphs = self._apply_marks(paragraphs, marks)
        chunks = self._chunk_text(processed_paragraphs, int(chunk_size), int(overlap))
        chunks = [c for c in chunks if c.strip()]

        # deactivate previous chunks + memory items for this document
        old = self.db.execute_query(
            "SELECT memory_item_id FROM rag_chunks WHERE document_id = ? AND is_active = 1",
            (int(document_id),),
        )
        old_memory_ids = [int(r["memory_item_id"]) for r in old if r["memory_item_id"] is not None]
        self.db.execute_update("UPDATE rag_chunks SET is_active = 0 WHERE document_id = ?", (int(document_id),))
        if old_memory_ids:
            marks_sql = ",".join(["?"] * len(old_memory_ids))
            self.db.execute_update(
                f"UPDATE memory_items SET status='deprecated', updated_at=CURRENT_TIMESTAMP WHERE id IN ({marks_sql})",
                tuple(old_memory_ids),
            )
            vector_memory_service.invalidate_index_cache(conversation_id=None)

        inserted = 0
        failed = 0
        for i, chunk in enumerate(chunks):
            item_id = None
            try:
                item_id = memory_item_service.create_item(
                    content=chunk,
                    scope="knowledge_base",
                    kind="doc_chunk",
                    conversation_id=None,
                    source_message_id=None,
                    confidence=1.0,
                    tags=tags,
                    deprecate_previous=False,
                )
                vector_memory_service.upsert_embedding(item_id)
                self.db.execute_insert(
                    """
                    INSERT INTO rag_chunks (document_id, chunk_index, content, token_len, tags_json, is_active, memory_item_id, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                    """,
                    (int(document_id), int(i), chunk, int(len(chunk)), json.dumps(tags, ensure_ascii=False), int(item_id)),
                )
                inserted += 1
            except Exception:
                if item_id is not None:
                    try:
                        self.db.execute_update(
                            "UPDATE memory_items SET status='deprecated', updated_at=CURRENT_TIMESTAMP WHERE id = ?",
                            (int(item_id),),
                        )
                    except Exception:
                        pass
                    try:
                        vector_memory_service.delete_embeddings_for_items([int(item_id)])
                    except Exception:
                        pass
                failed += 1

        status = "indexed" if inserted > 0 else "failed"
        self.db.execute_update(
            "UPDATE rag_documents SET status = ?, updated_at=CURRENT_TIMESTAMP WHERE id = ?",
            (status, int(document_id)),
        )
        return {
            "document_id": int(document_id),
            "status": status,
            "chunk_total": len(chunks),
            "inserted": inserted,
            "failed": failed,
        }

    def list_chunks(self, document_id: int, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        rows = self.db.execute_query(
            """
            SELECT id, document_id, chunk_index, content, token_len, tags_json, is_active, memory_item_id, created_at
            FROM rag_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            LIMIT ? OFFSET ?
            """,
            (int(document_id), int(limit), int(offset)),
        )
        items = []
        for r in rows:
            items.append(
                {
                    "id": int(r["id"]),
                    "document_id": int(r["document_id"]),
                    "chunk_index": int(r["chunk_index"]),
                    "content": r["content"],
                    "token_len": int(r["token_len"] or 0),
                    "tags": json.loads(r["tags_json"] or "[]"),
                    "is_active": bool(r["is_active"]),
                    "memory_item_id": r["memory_item_id"],
                    "created_at": str(r["created_at"]),
                }
            )
        return {"items": items, "limit": int(limit), "offset": int(offset)}

    def list_documents(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        rows = self.db.execute_query(
            """
            SELECT
              d.id,
              d.file_name,
              d.file_ext,
              d.mime_type,
              d.file_size,
              d.file_hash,
              d.storage_path,
              d.status,
              d.created_at,
              d.updated_at,
              COALESCE(a.metadata_json, '{}') AS metadata_json,
              COUNT(c.id) AS chunk_total,
              SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_chunk_count
            FROM rag_documents d
            LEFT JOIN rag_document_annotations a ON a.document_id = d.id
            LEFT JOIN rag_chunks c ON c.document_id = d.id
            GROUP BY
              d.id, d.file_name, d.file_ext, d.mime_type, d.file_size, d.file_hash,
              d.storage_path, d.status, d.created_at, d.updated_at, a.metadata_json
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ? OFFSET ?
            """,
            (int(limit), int(offset)),
        )

        items = []
        for r in rows:
            metadata = json.loads(r["metadata_json"] or "{}")
            raw_title = metadata.get("title") if isinstance(metadata, dict) else ""
            tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
            items.append(
                {
                    "document_id": int(r["id"]),
                    "title": str(raw_title or "").strip(),
                    "file_name": r["file_name"],
                    "file_ext": r["file_ext"],
                    "mime_type": r["mime_type"],
                    "file_size": int(r["file_size"] or 0),
                    "status": r["status"],
                    "created_at": str(r["created_at"]),
                    "updated_at": str(r["updated_at"]),
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "tags": tags,
                    "chunk_total": int(r["chunk_total"] or 0),
                    "active_chunk_count": int(r["active_chunk_count"] or 0),
                }
            )
        return {"items": items, "limit": int(limit), "offset": int(offset)}

    def delete_document(self, document_id: int) -> Dict[str, Any]:
        rows = self.db.execute_query(
            """
            SELECT id, storage_path
            FROM rag_documents
            WHERE id = ?
            """,
            (int(document_id),),
        )
        if not rows:
            raise ValueError("Document not found")

        storage_path = str(rows[0]["storage_path"] or "").strip()
        shared_storage_refs = 0
        if storage_path:
            ref_rows = self.db.execute_query(
                """
                SELECT COUNT(*) AS cnt
                FROM rag_documents
                WHERE storage_path = ? AND id != ?
                """,
                (storage_path, int(document_id)),
            )
            shared_storage_refs = int(ref_rows[0]["cnt"] or 0) if ref_rows else 0
        chunk_rows = self.db.execute_query(
            """
            SELECT id, memory_item_id
            FROM rag_chunks
            WHERE document_id = ?
            """,
            (int(document_id),),
        )
        memory_ids = [int(r["memory_item_id"]) for r in chunk_rows if r["memory_item_id"] is not None]

        with self.db.get_connection() as mem_conn, vector_db_manager.get_connection() as vec_conn:
            try:
                mem_conn.execute("BEGIN IMMEDIATE")
                vec_conn.execute("BEGIN IMMEDIATE")

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

                mem_conn.execute("DELETE FROM rag_document_annotations WHERE document_id = ?", (int(document_id),))
                mem_conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (int(document_id),))
                mem_conn.execute("DELETE FROM rag_documents WHERE id = ?", (int(document_id),))

                vec_conn.commit()
                mem_conn.commit()
            except Exception:
                vec_conn.rollback()
                mem_conn.rollback()
                raise

        storage_file_deleted = False
        if storage_path and shared_storage_refs == 0:
            try:
                p = Path(storage_path)
                if p.exists():
                    p.unlink()
                    storage_file_deleted = True
            except Exception:
                pass

        try:
            vector_memory_service.invalidate_index_cache(conversation_id=None)
        except Exception:
            pass

        for manager in (memory_db_manager, vector_db_manager):
            try:
                manager.checkpoint_and_compact()
            except Exception:
                pass

        return {
            "document_id": int(document_id),
            "deleted": True,
            "deleted_chunk_count": len(chunk_rows),
            "deleted_memory_item_count": len(memory_ids),
            "storage_file_deleted": storage_file_deleted,
            "shared_storage_refs": int(shared_storage_refs),
        }


rag_ingest_service = RagIngestService()
