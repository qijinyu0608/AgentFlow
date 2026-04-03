from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from ..common import logger
from ..common.database import vector_db_manager
from .memory_item_service import memory_item_service
from .rag_ingest_service import rag_ingest_service
from .vector_memory_service import vector_memory_service

YamlValue = Union[str, List[str], Dict[str, str]]

KNOWLEDGE_BASE_SCOPE = "knowledge_base"
LONG_TERM_SCOPE = "long_term"
LONG_TERM_KIND = "long_term_profile"
LONG_TERM_TAG = "long_term_profile"
LONG_TERM_SOURCE = "data/sqlite/memory.db::memory_items"


@dataclass(frozen=True)
class LongTermMemorySnapshot:
    source: str
    item_id: Optional[int]
    raw_text: str
    body_text: str
    meta: Dict[str, Any]
    updated_at: str


class UnifiedMemoryService:
    """
    Single entrypoint for memory operations.

    Route all memory CRUD/search through split-db services:
    - memory_items + memory_embeddings
    - rag_documents + rag_chunks
    """

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
        if with_embedding:
            try:
                vector_memory_service.upsert_embedding(item_id)
            except Exception as e:
                logger.exception("Embedding update failed for memory item %s: %s", item_id, e)
        return int(item_id)

    def list_memory_items(
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

    def get_memory_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        return memory_item_service.get_item(item_id)

    def search_text(
        self,
        q: str,
        conversation_id: Optional[str],
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        return memory_item_service.text_search(
            q=q,
            conversation_id=conversation_id,
            scope=scope,
            kind=kind,
            k=k,
        )

    def search_vector(
        self,
        q: str,
        conversation_id: Optional[str],
        k: int = 10,
        min_score: Optional[float] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ):
        return vector_memory_service.search(
            q=q,
            conversation_id=conversation_id,
            k=k,
            min_score=min_score,
            scope=scope,
            kind=kind,
        )

    def ingest_document(
        self,
        document_id: int,
        chunk_size: int = 700,
        overlap: int = 100,
    ) -> Dict[str, Any]:
        return rag_ingest_service.ingest_document(document_id=document_id, chunk_size=chunk_size, overlap=overlap)

    @staticmethod
    def _parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
        if not text.startswith("---\n"):
            return {}, text
        end = text.find("\n---\n", 4)
        if end == -1:
            return {}, text
        raw = text[4:end].splitlines()
        body = text[end + 5 :]
        meta: Dict[str, YamlValue] = {}
        i = 0
        while i < len(raw):
            line = raw[i].rstrip()
            i += 1
            if not line or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                continue
            key, rest = line.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if rest in ("", "|"):
                if rest == "|":
                    buf: List[str] = []
                    while i < len(raw):
                        nxt = raw[i]
                        if not nxt.startswith("  "):
                            break
                        buf.append(nxt[2:])
                        i += 1
                    meta[key] = "\n".join(buf).rstrip("\n")
                    continue
                items: List[str] = []
                j = i
                while j < len(raw) and raw[j].startswith("  - "):
                    items.append(raw[j][4:].strip())
                    j += 1
                if items:
                    i = j
                    meta[key] = items
                    continue
                mapping: Dict[str, str] = {}
                j = i
                while j < len(raw):
                    nxt = raw[j]
                    if not nxt.startswith("  "):
                        break
                    stripped = nxt[2:].rstrip()
                    if not stripped or stripped.lstrip().startswith("#"):
                        j += 1
                        continue
                    if ":" not in stripped:
                        break
                    mk, mv = stripped.split(":", 1)
                    mk = mk.strip()
                    mv = mv.strip()
                    if mk:
                        mapping[mk] = mv
                    j += 1
                if mapping:
                    i = j
                    meta[key] = mapping
                    continue
                meta[key] = []
                continue
            meta[key] = rest
        if "custom_kv" in meta and "custom" not in meta:
            meta["custom"] = meta.pop("custom_kv")
        return dict(meta), body.lstrip("\n")

    @staticmethod
    def _render_front_matter(meta: Dict[str, Any], body: str) -> str:
        lines: List[str] = ["---"]
        preferred = [
            "name",
            "role",
            "organization",
            "contact",
            "timezone",
            "language",
            "preferences",
            "tags",
            "custom",
            "updated_at",
        ]
        keys = [k for k in preferred if k in meta] + [k for k in meta.keys() if k not in preferred]
        for k in keys:
            v = meta.get(k)
            if v is None:
                continue
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    s = str(item).strip()
                    if s:
                        lines.append(f"  - {s}")
            elif isinstance(v, dict):
                lines.append(f"{k}:")
                for mk, mv in v.items():
                    mk_s = str(mk).strip()
                    if mk_s:
                        lines.append(f"  {mk_s}: {str(mv).strip()}")
            else:
                s = str(v)
                if "\n" in s:
                    lines.append(f"{k}: |")
                    for ln in s.splitlines():
                        lines.append(f"  {ln}")
                else:
                    lines.append(f"{k}: {s.strip()}")
        lines.append("---")
        body = (body or "").rstrip() + "\n"
        return f"{chr(10).join(lines)}\n\n{body}"

    def put_long_term_memory(self, meta: Dict[str, Any], content: str) -> LongTermMemorySnapshot:
        payload_meta = dict(meta or {})
        payload_meta["updated_at"] = datetime.now().isoformat()
        rendered = self._render_front_matter(payload_meta, content or "")
        item_id = self.create_memory_item(
            content=rendered,
            scope=LONG_TERM_SCOPE,
            kind=LONG_TERM_KIND,
            conversation_id=None,
            confidence=1.0,
            tags=[LONG_TERM_TAG],
            deprecate_previous=True,
            with_embedding=True,
        )
        return LongTermMemorySnapshot(
            source=LONG_TERM_SOURCE,
            item_id=item_id,
            raw_text=rendered,
            body_text=content or "",
            meta=payload_meta,
            updated_at=str(payload_meta["updated_at"]),
        )

    def get_long_term_memory(self) -> LongTermMemorySnapshot:
        items = self.list_memory_items(
            conversation_id=None,
            scope=LONG_TERM_SCOPE,
            kind=LONG_TERM_KIND,
            status="active",
            limit=1,
            offset=0,
        )
        if not items:
            now = datetime.now().isoformat()
            return LongTermMemorySnapshot(
                source=LONG_TERM_SOURCE,
                item_id=None,
                raw_text="",
                body_text="",
                meta={"updated_at": now},
                updated_at=now,
            )
        top = items[0]
        raw_text = str(top.get("content") or "")
        meta, body = self._parse_front_matter(raw_text)
        updated_at = str(meta.get("updated_at") or top.get("updated_at") or datetime.now().isoformat())
        return LongTermMemorySnapshot(
            source=LONG_TERM_SOURCE,
            item_id=int(top["id"]),
            raw_text=raw_text,
            body_text=body,
            meta=meta,
            updated_at=updated_at,
        )

    def export_long_term_markdown(self) -> str:
        snapshot = self.get_long_term_memory()
        return snapshot.raw_text

    def reindex_long_term_memory(self) -> LongTermMemorySnapshot:
        snapshot = self.get_long_term_memory()
        if snapshot.item_id is None:
            return snapshot
        vector_memory_service.upsert_embedding(int(snapshot.item_id))
        runtime_info = vector_memory_service.current_runtime_info()
        model = str(runtime_info.get("model") or "").strip()
        if model:
            vector_db_manager.execute_update(
                "DELETE FROM memory_embeddings WHERE memory_item_id = ? AND model != ?",
                (int(snapshot.item_id), model),
            )
            vector_memory_service.invalidate_index_cache()
        return self.get_long_term_memory()


unified_memory_service = UnifiedMemoryService()
