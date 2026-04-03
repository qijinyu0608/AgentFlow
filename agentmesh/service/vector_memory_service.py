from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

from ..common import logger
from ..common.database import memory_db_manager, vector_db_manager


def _pack_f32(vec: np.ndarray) -> bytes:
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    return vec.tobytes()


def _unpack_f32(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=int(dim)).reshape(1, int(dim))


@dataclass(frozen=True)
class VectorHit:
    memory_item_id: int
    score: float
    content: str
    meta: Dict[str, Any]


@dataclass(frozen=True)
class CachedVectorIndex:
    index: Any
    ids: List[int]
    metas: List[Dict[str, Any]]
    generation: int


class VectorMemoryService:
    def __init__(self):
        self.memory_db = memory_db_manager
        self.vector_db = vector_db_manager
        self._provider = "local"
        self._model_name = "BAAI/bge-small-zh-v1.5"
        self._api_base: Optional[str] = None
        self._api_key: Optional[str] = None
        self._active_profile = "local_light"
        self._embedder = None
        self._faiss = None
        self._dim: Optional[int] = None
        self._runtime_signature: Optional[str] = None
        self._index_cache: Dict[str, CachedVectorIndex] = {}
        self._cache_lock = threading.RLock()
        self._index_generation = 0

    @staticmethod
    def _scope_cache_key(conversation_id: Optional[str]) -> str:
        return f"conv:{conversation_id}" if conversation_id else "global"

    def _current_generation(self) -> int:
        with self._cache_lock:
            return self._index_generation

    def invalidate_index_cache(self, conversation_id: Optional[str] = None) -> None:
        with self._cache_lock:
            self._index_generation += 1
            if conversation_id is None:
                self._index_cache.clear()
                return
            keys_to_drop = {"global", self._scope_cache_key(conversation_id)}
            for key in keys_to_drop:
                self._index_cache.pop(key, None)

    @staticmethod
    def _default_profiles() -> Dict[str, Dict[str, Any]]:
        return {
            "local_light": {
                "provider": "local",
                "model": "BAAI/bge-small-zh-v1.5",
            },
            "qwen_remote": {
                "provider": "openai",
                "model": "Qwen3-Embedding-8B",
                "api_base": "https://modelservice.jdcloud.com/v1",
            },
        }

    def current_runtime_info(self) -> Dict[str, Any]:
        self._load_runtime_config()
        return {
            "profile": self._active_profile,
            "provider": self._provider,
            "model": self._model_name,
            "api_base": self._api_base,
            "dim": self._dim,
        }

    def _load_runtime_config(self) -> None:
        embeddings_cfg: Dict[str, Any] = {}
        try:
            from ..common import config as get_config
            cfg = get_config() or {}
            if isinstance(cfg, dict):
                embeddings_cfg = cfg.get("embeddings", {}) or {}
        except Exception:
            embeddings_cfg = {}

        profiles_cfg = embeddings_cfg.get("profiles", {}) if isinstance(embeddings_cfg.get("profiles", {}), dict) else {}
        merged_profiles = self._default_profiles()
        for key, value in profiles_cfg.items():
            if isinstance(value, dict):
                merged_profiles[str(key)] = {**merged_profiles.get(str(key), {}), **value}

        legacy_cfg = {}
        for field in ("provider", "model", "api_base", "api_key"):
            raw = embeddings_cfg.get(field)
            if raw is not None and str(raw).strip():
                legacy_cfg[field] = raw

        active_profile = (os.environ.get("AGENTMESH_EMBEDDING_PROFILE") or embeddings_cfg.get("active_profile") or "").strip()
        selected_profile_name = active_profile or ("legacy" if legacy_cfg else "local_light")
        selected_cfg = legacy_cfg if selected_profile_name == "legacy" else merged_profiles.get(selected_profile_name, {})

        provider = (os.environ.get("AGENTMESH_EMBEDDING_PROVIDER") or selected_cfg.get("provider") or legacy_cfg.get("provider") or "local").strip().lower()
        model = (os.environ.get("AGENTMESH_EMBEDDING_MODEL") or selected_cfg.get("model") or legacy_cfg.get("model") or "").strip()
        api_base = (os.environ.get("OPENAI_API_BASE") or selected_cfg.get("api_base") or legacy_cfg.get("api_base") or "").strip()
        api_key = (os.environ.get("OPENAI_API_KEY") or selected_cfg.get("api_key") or legacy_cfg.get("api_key") or "").strip()

        if not model:
            model = "Qwen3-Embedding-8B" if provider != "local" else "BAAI/bge-small-zh-v1.5"

        runtime_signature = f"{selected_profile_name}|{provider}|{model}|{api_base}"
        if self._runtime_signature != runtime_signature:
            # Reset cached state if runtime embedding config changed.
            self._embedder = None
            self.invalidate_index_cache()
            self._runtime_signature = runtime_signature

        self._active_profile = selected_profile_name
        self._provider = provider
        self._model_name = model
        self._api_base = api_base or None
        self._api_key = api_key or None

    def _lazy_imports(self, need_embedder: bool = True) -> None:
        if need_embedder and self._provider == "local" and self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self._model_name)
        if self._faiss is None:
            import faiss  # type: ignore

            self._faiss = faiss

    @staticmethod
    def _normalize_rows(vec: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vec / norms).astype(np.float32, copy=False)

    def _embed_text_remote(self, text: str) -> np.ndarray:
        if not self._api_base or not self._api_key:
            raise ValueError(
                "Remote embedding provider requires api_base and api_key. "
                "Set OPENAI_API_BASE/OPENAI_API_KEY or config.yaml embeddings.api_base/api_key."
            )

        base = self._api_base.rstrip("/")
        url = base if base.endswith("/embeddings") else base + "/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "input": [text],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        rows = data.get("data") or []
        if not rows or "embedding" not in rows[0]:
            raise ValueError(f"Invalid embedding response from {url}: missing data[0].embedding")
        vec = np.asarray(rows[0]["embedding"], dtype=np.float32).reshape(1, -1)
        return self._normalize_rows(vec)

    def embed_text(self, text: str) -> np.ndarray:
        self._load_runtime_config()
        if self._provider == "local":
            self._lazy_imports(need_embedder=True)
            vec = self._embedder.encode([text], normalize_embeddings=True)
            vec = np.asarray(vec, dtype=np.float32)
            if vec.ndim == 1:
                vec = vec.reshape(1, -1)
            vec = self._normalize_rows(vec)
        else:
            self._lazy_imports(need_embedder=False)
            vec = self._embed_text_remote(text)
        self._dim = int(vec.shape[1])
        return vec

    def upsert_embedding(self, memory_item_id: int) -> None:
        row = self.memory_db.execute_query(
            """
            SELECT id, content
            FROM memory_items
            WHERE id = ? AND status = 'active'
            """,
            (int(memory_item_id),),
        )
        if not row:
            return
        content = row[0]["content"] or ""
        if not content.strip():
            return

        self._upsert_embedding_content(memory_item_id=int(memory_item_id), content=content.strip(), invalidate=True)

    def _upsert_embedding_content(self, memory_item_id: int, content: str, invalidate: bool) -> None:
        vec = self.embed_text(content.strip())
        dim = int(vec.shape[1])
        blob = _pack_f32(vec)
        self.vector_db.execute_update(
            """
            INSERT INTO memory_embeddings (memory_item_id, model, vector_blob, dim, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(memory_item_id, model) DO UPDATE SET
              vector_blob=excluded.vector_blob,
              dim=excluded.dim,
              updated_at=CURRENT_TIMESTAMP
            """,
            (int(memory_item_id), self._model_name, blob, dim),
        )
        if invalidate:
            self.invalidate_index_cache()

    def delete_embeddings_for_items(self, memory_item_ids: List[int], keep_model: Optional[str] = None) -> int:
        ids = [int(x) for x in memory_item_ids if int(x) > 0]
        if not ids:
            return 0
        placeholders = ",".join(["?"] * len(ids))
        params: List[Any] = ids
        sql = f"DELETE FROM memory_embeddings WHERE memory_item_id IN ({placeholders})"
        if keep_model:
            sql += " AND model != ?"
            params.append(str(keep_model))
        deleted = self.vector_db.execute_update(sql, tuple(params))
        if deleted:
            self.invalidate_index_cache()
        return int(deleted)

    @staticmethod
    def _search_visibility_clause(conversation_id: Optional[str], scope: Optional[str]) -> Optional[Tuple[str, List[Any]]]:
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

    def _backfill_missing_embeddings(
        self,
        memory_rows: List[Dict[str, Any]],
        embedding_map: Dict[int, Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        missing_rows = [r for r in memory_rows if int(r["memory_item_id"]) not in embedding_map]
        if not missing_rows:
            return embedding_map

        updated = False
        for row in missing_rows:
            rid = int(row["memory_item_id"])
            content = str(row["content"] or "").strip()
            if not content:
                continue
            try:
                self._upsert_embedding_content(memory_item_id=rid, content=content, invalidate=False)
                updated = True
            except Exception as e:
                logger.warning(
                    "Failed to backfill embedding for memory_item_id=%s with model=%s: %s",
                    rid,
                    self._model_name,
                    e,
                )

        if not updated:
            return embedding_map

        placeholders = ",".join(["?"] * len([r for r in missing_rows]))
        refreshed_rows = self.vector_db.execute_query(
            f"""
            SELECT memory_item_id, vector_blob, dim
            FROM memory_embeddings
            WHERE model = ? AND memory_item_id IN ({placeholders})
            """,
            tuple([self._model_name] + [int(r["memory_item_id"]) for r in missing_rows]),
        )
        refreshed_map = dict(embedding_map)
        for row in refreshed_rows:
            refreshed_map[int(row["memory_item_id"])] = {
                "vector_blob": row["vector_blob"],
                "dim": int(row["dim"] or 0),
            }
        self.invalidate_index_cache()
        return refreshed_map

    def _fetch_kb_chunk_meta(self, memory_item_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        ids = [int(x) for x in memory_item_ids if int(x) > 0]
        if not ids:
            return {}
        placeholders = ",".join(["?"] * len(ids))
        rows = self.memory_db.execute_query(
            f"""
            SELECT
              c.memory_item_id,
              c.document_id,
              c.chunk_index,
              d.file_name,
              d.file_ext,
              d.mime_type,
              COALESCE(json_extract(a.metadata_json, '$.title'), '') AS document_title
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            LEFT JOIN rag_document_annotations a ON a.document_id = d.id
            WHERE c.memory_item_id IN ({placeholders})
            """,
            tuple(ids),
        )
        out: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            memory_item_id = int(row["memory_item_id"])
            file_name = str(row["file_name"] or "").strip()
            chunk_index = int(row["chunk_index"] or 0)
            out[memory_item_id] = {
                "document_id": int(row["document_id"]),
                "chunk_index": chunk_index,
                "file_name": file_name,
                "file_ext": str(row["file_ext"] or ""),
                "mime_type": str(row["mime_type"] or ""),
                "document_title": str(row["document_title"] or "").strip(),
                "source_label": f"{file_name} / chunk {chunk_index}" if file_name else f"chunk {chunk_index}",
            }
        return out

    def _load_embeddings(
        self,
        conversation_id: Optional[str],
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> Tuple[np.ndarray, List[int], List[Dict[str, Any]]]:
        clauses = ["status = 'active'"]
        params: List[Any] = []
        visibility = self._search_visibility_clause(conversation_id=conversation_id, scope=scope)
        if visibility is None:
            return np.zeros((0, 1), dtype=np.float32), [], []
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
        memory_rows = self.memory_db.execute_query(
            f"""
            SELECT id AS memory_item_id, conversation_id, content, scope, kind, confidence, tags_json, source_message_id
            FROM memory_items
            WHERE {where}
            ORDER BY updated_at DESC, id DESC
            """,
            tuple(params),
        )
        if not memory_rows:
            return np.zeros((0, 1), dtype=np.float32), [], []

        memory_ids = [int(r["memory_item_id"]) for r in memory_rows]
        placeholders = ",".join(["?"] * len(memory_ids))
        embedding_rows = self.vector_db.execute_query(
            f"""
            SELECT memory_item_id, vector_blob, dim
            FROM memory_embeddings
            WHERE model = ? AND memory_item_id IN ({placeholders})
            """,
            tuple([self._model_name] + memory_ids),
        )
        dims = {int(r["dim"] or 0) for r in embedding_rows if int(r["dim"] or 0) > 0}
        if len(dims) > 1:
            raise ValueError(
                f"Inconsistent embedding dimensions for model '{self._model_name}': {sorted(dims)}"
            )
        embedding_map: Dict[int, Dict[str, Any]] = {
            int(r["memory_item_id"]): {"vector_blob": r["vector_blob"], "dim": int(r["dim"] or 0)}
            for r in embedding_rows
        }
        embedding_map = self._backfill_missing_embeddings(memory_rows=memory_rows, embedding_map=embedding_map)
        if not embedding_map:
            placeholders2 = ",".join(["?"] * len(memory_ids))
            model_rows = self.vector_db.execute_query(
                f"""
                SELECT model, COUNT(*) AS cnt
                FROM memory_embeddings
                WHERE memory_item_id IN ({placeholders2})
                GROUP BY model
                ORDER BY cnt DESC
                """,
                tuple(memory_ids),
            )
            if model_rows:
                available_models = ", ".join(str(r["model"]) for r in model_rows)
                raise ValueError(
                    f"No embeddings found for configured model '{self._model_name}'. "
                    f"Available models in vector DB: {available_models}"
                )
            return np.zeros((0, 1), dtype=np.float32), [], []

        kb_chunk_meta = self._fetch_kb_chunk_meta(memory_ids)

        vecs: List[np.ndarray] = []
        ids: List[int] = []
        metas: List[Dict[str, Any]] = []
        dim = int(next(iter(embedding_map.values()))["dim"] or 0)
        for r in memory_rows:
            rid = int(r["memory_item_id"])
            em = embedding_map.get(rid)
            if not em:
                continue
            blob = em["vector_blob"]
            rdim = int(em["dim"] or dim)
            if not blob or rdim <= 0:
                continue
            v = _unpack_f32(blob, rdim)
            vecs.append(v)
            ids.append(rid)
            meta = {
                "content": r["content"],
                "conversation_id": r["conversation_id"],
                "scope": r["scope"],
                "kind": r["kind"],
                "confidence": float(r["confidence"] or 0.0),
                "tags": json.loads(r["tags_json"] or "[]"),
                "source_message_id": r["source_message_id"],
            }
            extra = kb_chunk_meta.get(rid)
            if extra:
                meta.update(extra)
            metas.append(meta)
        if not vecs:
            return np.zeros((0, 1), dtype=np.float32), [], []
        missing_ids = [int(r["memory_item_id"]) for r in memory_rows if int(r["memory_item_id"]) not in set(ids)]
        if missing_ids:
            logger.warning(
                "Active memories missing embeddings for model '%s': ids=%s",
                self._model_name,
                missing_ids,
            )
        mat = np.vstack(vecs).astype(np.float32)
        self._dim = int(mat.shape[1])
        return mat, ids, metas

    def _build_cached_index(
        self,
        conversation_id: Optional[str],
        scope: Optional[str],
        kind: Optional[str],
        generation: int,
    ) -> CachedVectorIndex:
        self._load_runtime_config()
        self._lazy_imports(need_embedder=False)
        mat, ids, metas = self._load_embeddings(conversation_id, scope=scope, kind=kind)
        if mat.shape[0] == 0:
            return CachedVectorIndex(index=None, ids=[], metas=[], generation=generation)
        dim = int(mat.shape[1])
        index = self._faiss.IndexFlatIP(dim)
        index.add(mat)
        return CachedVectorIndex(index=index, ids=ids, metas=metas, generation=generation)

    def _ensure_index(
        self,
        conversation_id: Optional[str],
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> Tuple[Any, List[int], List[Dict[str, Any]]]:
        self._load_runtime_config()
        scope_key = f"{self._scope_cache_key(conversation_id)}|scope:{scope or '*'}|kind:{kind or '*'}"
        generation = self._current_generation()

        with self._cache_lock:
            cached = self._index_cache.get(scope_key)
            if cached and cached.generation == generation:
                return cached.index, cached.ids, cached.metas

        built = self._build_cached_index(conversation_id, scope=scope, kind=kind, generation=generation)

        with self._cache_lock:
            latest_generation = self._index_generation
            if latest_generation != generation:
                cached = self._index_cache.get(scope_key)
                if cached and cached.generation == latest_generation:
                    return cached.index, cached.ids, cached.metas
                built = self._build_cached_index(conversation_id, scope=scope, kind=kind, generation=latest_generation)
            self._index_cache[scope_key] = built
            return built.index, built.ids, built.metas

    def search(
        self,
        q: str,
        conversation_id: Optional[str],
        k: int = 10,
        min_score: Optional[float] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> List[VectorHit]:
        if not q.strip():
            return []
        try:
            index, ids, metas = self._ensure_index(conversation_id, scope=scope, kind=kind)
        except Exception as e:
            logger.exception("Vector index build failed: %s", e)
            raise
        if index is None:
            return []
        qv = self.embed_text(q.strip())
        scores, idxs = index.search(qv.astype(np.float32), int(k))
        hits: List[VectorHit] = []
        for score, ix in zip(scores.reshape(-1).tolist(), idxs.reshape(-1).tolist()):
            if ix < 0 or ix >= len(ids):
                continue
            if min_score is not None and float(score) < float(min_score):
                continue
            mid = ids[ix]
            meta = metas[ix]
            hits.append(VectorHit(memory_item_id=mid, score=float(score), content=str(meta.get("content") or ""), meta=meta))
        return hits


vector_memory_service = VectorMemoryService()
