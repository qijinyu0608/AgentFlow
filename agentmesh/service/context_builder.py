from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..common import logger
from ..common.database import memory_db_manager
from .conversation_service import conversation_service
from .unified_memory_service import KNOWLEDGE_BASE_SCOPE, unified_memory_service
from .vector_memory_service import vector_memory_service

DEFAULT_MEMORY_MIN_SCORE = 0.35
DOC_CHUNK_KIND = "doc_chunk"
DOC_CHUNK_SCOPE = KNOWLEDGE_BASE_SCOPE
CONVERSATION_SCOPE = "conversation"


class ContextBuilder:
    QUERY_PREFIXES = (
        "请问",
        "介绍一下",
        "介绍下",
        "帮我介绍一下",
        "帮我看下",
        "帮我查下",
        "说说",
        "看下",
        "查下",
    )
    PROFILE_QUERY_MARKERS = (
        "是谁",
        "介绍",
        "背景",
        "简历",
        "履历",
        "资料",
        "信息",
    )
    EDUCATION_QUERY_MARKERS = ("教育", "学历", "学校", "专业", "本科", "硕士", "博士")
    CAREER_QUERY_MARKERS = ("职业", "工作", "岗位", "任职", "实习", "公司", "项目")
    QUESTION_SUFFIXES = (
        "是谁啊",
        "是谁呀",
        "是谁",
        "是什么",
        "有哪些",
        "有谁",
        "在哪儿",
        "在哪里",
        "在哪",
        "多少",
        "几岁",
        "多大",
        "吗",
        "呢",
        "啊",
        "呀",
    )

    @classmethod
    def _expand_term_variants(cls, term: str) -> List[str]:
        src = (term or "").strip().lower()
        if not src:
            return []
        variants: List[str] = [src]
        for prefix in cls.QUERY_PREFIXES:
            if src.startswith(prefix) and len(src) > len(prefix):
                stripped = src[len(prefix) :].strip()
                if stripped:
                    variants.append(stripped)
        for suffix in cls.QUESTION_SUFFIXES:
            if src.endswith(suffix) and len(src) > len(suffix):
                stripped = src[: -len(suffix)].strip()
                if stripped:
                    variants.append(stripped)
        out: List[str] = []
        for item in variants:
            if len(item) >= 2 and item not in out:
                out.append(item)
        return out

    @staticmethod
    def _query_terms(text: str) -> List[str]:
        src = (text or "").strip().lower()
        if not src:
            return []
        parts = [p.strip() for p in re.split(r"[\s,，。；;:：/\\|]+", src) if p.strip()]
        expanded: List[str] = []
        for p in parts:
            expanded.extend(ContextBuilder._expand_term_variants(p))
        cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", src)
        for run in cjk_runs:
            expanded.extend(ContextBuilder._expand_term_variants(run))
        # Keep longer terms first; short terms add too much noise.
        parts = [p for p in (expanded or parts) if len(p) >= 2]
        uniq: List[str] = []
        for p in parts:
            if p not in uniq:
                uniq.append(p)
        return uniq[:10]

    def _extract_memory_evidence(self, memory_text: str, query_text: str, max_lines: int = 12) -> List[str]:
        if not memory_text.strip():
            return []
        terms = self._query_terms(query_text)
        if not terms:
            return []
        lines = [ln.strip() for ln in memory_text.splitlines() if ln.strip()]
        matched: List[str] = []
        for ln in lines:
            ll = ln.lower()
            if any(t in ll for t in terms):
                matched.append(ln)
            if len(matched) >= max_lines:
                break
        return matched

    @staticmethod
    def _memory_label(item_id: Optional[int]) -> str:
        if item_id:
            return f"长期记忆#{int(item_id)}"
        return "长期记忆"

    @staticmethod
    def _conversation_label(item_id: int) -> str:
        return f"会话记忆#{int(item_id)}"

    def _knowledge_base_labels(self, memory_item_ids: List[int]) -> Dict[int, str]:
        ids = [int(x) for x in memory_item_ids if int(x) > 0]
        if not ids:
            return {}
        placeholders = ",".join(["?"] * len(ids))
        try:
            rows = memory_db_manager.execute_query(
                f"""
                SELECT c.memory_item_id, c.chunk_index, d.file_name
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.memory_item_id IN ({placeholders})
                """,
                tuple(ids),
            )
        except Exception as e:
            logger.warning("Failed to resolve knowledge-base source labels: %s", e)
            return {mid: f"知识库#{mid}" for mid in ids}

        resolved: Dict[int, str] = {}
        for row in rows:
            mid = int(row["memory_item_id"])
            file_name = str(row["file_name"] or "").strip() or "未知文档"
            chunk_index = int(row["chunk_index"] or 0)
            resolved[mid] = f"知识库#{mid}（{file_name} / chunk {chunk_index}）"
        for mid in ids:
            resolved.setdefault(mid, f"知识库#{mid}")
        return resolved

    @staticmethod
    def _dedupe_strings(items: List[str], limit: int) -> List[str]:
        out: List[str] = []
        for item in items:
            s = str(item or "").strip()
            if not s or s in out:
                continue
            out.append(s)
            if len(out) >= int(limit):
                break
        return out

    def _looks_like_profile_query(self, text: str) -> bool:
        src = (text or "").strip().lower()
        return any(marker in src for marker in self.PROFILE_QUERY_MARKERS)

    def _extract_focus_terms(self, text: str) -> List[str]:
        src = (text or "").strip()
        if not src:
            return []
        markers = (
            list(self.PROFILE_QUERY_MARKERS)
            + list(self.EDUCATION_QUERY_MARKERS)
            + list(self.CAREER_QUERY_MARKERS)
            + list(self.QUESTION_SUFFIXES)
        )
        out: List[str] = []
        for marker in markers:
            idx = src.find(marker)
            if idx <= 0:
                continue
            candidate = src[:idx].strip().rstrip("的")
            for prefix in self.QUERY_PREFIXES:
                if candidate.startswith(prefix) and len(candidate) > len(prefix):
                    candidate = candidate[len(prefix) :].strip()
            if len(candidate) >= 2 and candidate not in out:
                out.append(candidate)
        return out

    def _build_retrieval_queries(self, text: str) -> List[str]:
        src = (text or "").strip()
        if not src:
            return []
        lower = src.lower()
        terms = self._query_terms(src)
        focus_from_split = self._extract_focus_terms(src)
        queries: List[str] = [src]
        queries.extend(terms[:4])
        queries.extend(focus_from_split)

        focus_terms = focus_from_split + [t for t in terms if not any(t.endswith(sfx) for sfx in self.QUESTION_SUFFIXES)]
        focus_terms = self._dedupe_strings(focus_terms, limit=3)
        if self._looks_like_profile_query(lower):
            for term in focus_terms:
                queries.extend(
                    [
                        f"{term} 简历",
                        f"{term} 教育经历",
                        f"{term} 工作经历",
                    ]
                )
        if any(marker in lower for marker in self.EDUCATION_QUERY_MARKERS):
            for term in focus_terms:
                queries.extend([f"{term} 教育经历", f"{term} 学历", f"{term} 学校"])
        if any(marker in lower for marker in self.CAREER_QUERY_MARKERS):
            for term in focus_terms:
                queries.extend([f"{term} 工作经历", f"{term} 实习经历", f"{term} 项目经历"])

        return self._dedupe_strings(queries, limit=8)

    @staticmethod
    def _normalize_hit(hit: Any) -> Dict[str, Any]:
        if isinstance(hit, dict):
            item_id = int(hit.get("id") or 0)
            score = float(hit.get("score") or 1.0)
            content = str(hit.get("content") or "")
            meta = dict(hit.get("meta") or {})
            if "scope" not in meta and hit.get("scope") is not None:
                meta["scope"] = hit.get("scope")
            if "kind" not in meta and hit.get("kind") is not None:
                meta["kind"] = hit.get("kind")
            return {"id": item_id, "score": score, "content": content, "meta": meta}
        return {
            "id": int(hit.memory_item_id),
            "score": float(hit.score),
            "content": str(hit.content),
            "meta": dict(getattr(hit, "meta", {}) or {}),
        }

    @staticmethod
    def _query_match_bonus(query: str, original_query: str, content: str, query_index: int) -> float:
        bonus = 0.0
        q = (query or "").strip().lower()
        original = (original_query or "").strip().lower()
        body = (content or "").lower()
        if q and q in body:
            bonus += 0.08
        if q and q != original:
            bonus += 0.03
        if query_index > 0:
            bonus -= min(query_index, 4) * 0.005
        return bonus

    def _merge_hits(self, hits: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
        merged: Dict[int, Dict[str, Any]] = {}
        for hit in hits:
            item_id = int(hit.get("id") or 0)
            if item_id <= 0:
                continue
            current = dict(hit)
            current_meta = dict(current.get("meta") or {})
            current_queries = list(current_meta.get("matched_queries") or [])
            current_meta["matched_queries"] = self._dedupe_strings(current_queries, limit=8)
            current["meta"] = current_meta

            existing = merged.get(item_id)
            if existing is None or float(current.get("score") or 0.0) > float(existing.get("score") or 0.0):
                if existing:
                    merged_queries = list(existing.get("meta", {}).get("matched_queries") or []) + current_queries
                    current["meta"]["matched_queries"] = self._dedupe_strings(merged_queries, limit=8)
                merged[item_id] = current
                continue

            existing_meta = dict(existing.get("meta") or {})
            merged_queries = list(existing_meta.get("matched_queries") or []) + current_queries
            existing_meta["matched_queries"] = self._dedupe_strings(merged_queries, limit=8)
            existing["meta"] = existing_meta

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                -float(item.get("score") or 0.0),
                -len(str(item.get("content") or "")),
                int(item.get("id") or 0),
            ),
        )
        return ranked[: int(k)]

    def _search_vector_multi(
        self,
        *,
        q: str,
        conversation_id: Optional[str],
        scope: str,
        kind: Optional[str] = None,
        k: int = 8,
        min_score: float = DEFAULT_MEMORY_MIN_SCORE,
    ) -> List[Dict[str, Any]]:
        queries = self._build_retrieval_queries(q)
        merged_hits: List[Dict[str, Any]] = []
        for idx, candidate in enumerate(queries):
            rows = unified_memory_service.search_vector(
                q=candidate,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=k,
                min_score=float(min_score),
            )
            for row in rows:
                normalized = self._normalize_hit(row)
                meta = dict(normalized.get("meta") or {})
                meta["matched_queries"] = self._dedupe_strings(
                    list(meta.get("matched_queries") or []) + [candidate],
                    limit=8,
                )
                normalized["meta"] = meta
                normalized["score"] = float(normalized.get("score") or 0.0) + self._query_match_bonus(
                    candidate,
                    q,
                    str(normalized.get("content") or ""),
                    idx,
                )
                merged_hits.append(normalized)
        return self._merge_hits(merged_hits, k=k)

    def _search_text_fallback(
        self,
        *,
        q: str,
        conversation_id: Optional[str],
        scope: str,
        kind: Optional[str] = None,
        k: int = 8,
    ) -> List[Dict[str, Any]]:
        terms = self._query_terms(q)
        candidates = terms or [q]
        merged: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            try:
                rows = unified_memory_service.search_text(
                    q=candidate,
                    conversation_id=conversation_id,
                    scope=scope,
                    kind=kind,
                    k=k,
                )
            except Exception:
                rows = []
            for row in rows:
                item_id = int(row.get("id") or 0)
                if item_id <= 0 or item_id in seen:
                    continue
                merged.append(row)
                seen.add(item_id)
                if len(merged) >= int(k):
                    return merged
        return merged

    def build_task_bundle(
        self,
        conversation_id: Optional[str],
        user_text: str,
        recent_limit: int = 20,
        memory_k: int = 8,
        memory_min_score: float = DEFAULT_MEMORY_MIN_SCORE,
    ) -> Dict[str, Any]:
        parts: List[str] = []
        retrieval_queries = self._build_retrieval_queries(user_text)
        parts.append(
            "【记忆优先规则】\n"
            "1) 回答必须以长期记忆与检索命中内容为事实来源，禁止补充未命中的履历、身份、组织、项目等细节。\n"
            "2) 若问题要求多个字段（如时间、岗位、经历）但证据不完整，只回答有证据的字段；缺失项明确写“未在知识库中检索到”。\n"
            "3) 最近对话仅用于理解当前问题，不作为新增事实来源；尤其不要复述历史 assistant 可能出现的猜测内容。\n"
            "4) 对用户身份、关系、偏好、设定类问题，只依据长期记忆中的明确内容。\n"
            "5) 如果需要标注来源，只能使用上下文里明确给出的证据标签，禁止自造“聊天记录”“合同扫描件”“API日志”等来源名称。\n"
            "6) 以上规则为内部约束，不得在最终回复中显式提及。"
        )

        memory_source_path = ""
        long_term_memory = ""
        memory_evidence: List[str] = []
        long_term_item_id: Optional[int] = None
        memory_load_error = ""
        vector_search_error = ""
        retrieval_mode = "vector"
        conversation_memory_hits = []
        doc_hits = []
        try:
            memory_snapshot = unified_memory_service.get_long_term_memory()
            memory_source_path = memory_snapshot.source
            long_term_item_id = memory_snapshot.item_id
            long_term_memory = memory_snapshot.body_text or ""
            long_term_memory = re.sub(r"\n{3,}", "\n\n", long_term_memory).strip()
        except Exception as e:
            memory_load_error = str(e)
            logger.exception("Failed to load long-term memory: %s", e)

        if long_term_memory:
            parts.append("【长期记忆（MEMORY.md）】\n" + long_term_memory)
            memory_evidence = self._extract_memory_evidence(long_term_memory, user_text)
            if memory_evidence:
                parts.append("【长期记忆命中片段（关键行）】\n" + "\n".join(f"- {x}" for x in memory_evidence))
            else:
                parts.append(
                    "【长期记忆命中片段（关键行）】\n"
                    "未在 MEMORY.md 中匹配到与当前问题直接相关的关键行。"
                )
        if retrieval_queries:
            parts.append("【检索改写】\n" + "\n".join(f"- {q}" for q in retrieval_queries))

        runtime_info = vector_memory_service.current_runtime_info()
        knowledge_labels: Dict[int, str] = {}

        # Mandatory pre-retrieval for every task:
        # vector evidence is always attempted before model generation.
        try:
            conversation_memory_hits = self._search_vector_multi(
                q=user_text,
                conversation_id=conversation_id,
                scope=CONVERSATION_SCOPE,
                k=max(1, min(int(memory_k), 4)),
                min_score=float(memory_min_score),
            )
            doc_hits = self._search_vector_multi(
                q=user_text,
                conversation_id=conversation_id,
                scope=DOC_CHUNK_SCOPE,
                kind=DOC_CHUNK_KIND,
                k=memory_k,
                min_score=float(memory_min_score),
            )
        except Exception as e:
            vector_search_error = str(e)
            logger.exception("Failed to run vector pre-retrieval: %s", e)
            retrieval_mode = "hybrid_fallback"
            conversation_memory_hits = self._search_text_fallback(
                q=user_text,
                conversation_id=conversation_id,
                scope=CONVERSATION_SCOPE,
                k=max(1, min(int(memory_k), 4)),
            )
            doc_hits = self._search_text_fallback(
                q=user_text,
                conversation_id=conversation_id,
                scope=DOC_CHUNK_SCOPE,
                kind=DOC_CHUNK_KIND,
                k=memory_k,
            )
        if doc_hits:
            knowledge_labels = self._knowledge_base_labels(
                [
                    int(h.get("id") or 0) if isinstance(h, dict) else int(h.memory_item_id)
                    for h in doc_hits
                ]
            )

        citation_lines: List[str] = []
        if long_term_memory:
            citation_lines.append(f"- {self._memory_label(long_term_item_id)}")
        if conversation_memory_hits:
            mem_lines = []
            for h in conversation_memory_hits:
                normalized = self._normalize_hit(h)
                item_id = int(normalized.get("id") or 0)
                score = float(normalized.get("score") or 0.0)
                content = str(normalized.get("content") or "")
                mem_lines.append(
                    f"- [{self._conversation_label(item_id)}, score={score:.3f}] {content}".strip()
                )
                citation_lines.append(f"- {self._conversation_label(item_id)}")
            parts.append("【会话记忆命中（前置检索）】\n" + "\n".join(mem_lines))
        elif conversation_id:
            parts.append(
                "【会话记忆命中（前置检索）】\n"
                "未检索到与当前会话直接相关的记忆。"
            )

        if doc_hits:
            mem_lines = []
            for h in doc_hits:
                normalized = self._normalize_hit(h)
                item_id = int(normalized.get("id") or 0)
                score = float(normalized.get("score") or 0.0)
                content = str(normalized.get("content") or "")
                label = knowledge_labels.get(item_id, f"知识库#{item_id}")
                mem_lines.append(
                    f"- [{label}, score={score:.3f}] {content}".strip()
                )
                citation_lines.append(f"- {label}")
            parts.append("【向量知识库命中（文档检索）】\n" + "\n".join(mem_lines))
        else:
            if vector_search_error:
                parts.append(
                    "【向量知识库命中（文档检索）】\n"
                    "向量检索执行失败，已切换到关键词兜底；若仍无结果，请勿臆测事实，必要时直接回答“未在知识库中检索到”。"
                )
            else:
                parts.append(
                    "【向量知识库命中（文档检索）】\n"
                    "未检索到满足阈值的相关记忆。请勿臆测事实，必要时直接回答“未在知识库中检索到”。"
                )
        if citation_lines:
            uniq_citations: List[str] = []
            for line in citation_lines:
                if line not in uniq_citations:
                    uniq_citations.append(line)
            parts.append(
                "【可引用证据标签】\n"
                "如果答案需要写来源，只能逐字使用以下标签：\n"
                + "\n".join(uniq_citations)
            )
        if memory_load_error:
            parts.append(
                "【长期记忆状态】\n"
                "长期记忆加载失败，已按无长期记忆处理。"
            )

        conv = conversation_service.get_conversation(conversation_id) if conversation_id else None
        if conv:
            summary = conversation_service.get_summary(conversation_id)
            if summary and summary.summary.strip():
                parts.append("【会话摘要】\n" + summary.summary.strip())

            recent = conversation_service.list_recent_messages(conversation_id, limit=recent_limit)
            if recent:
                msg_lines: List[str] = []
                for m in recent:
                    # Avoid self-reinforcing hallucinations from prior assistant outputs.
                    if m.role not in ("user", "system", "tool"):
                        continue
                    msg_lines.append(f"{m.role}: {m.content}".strip())
                if msg_lines:
                    parts.append("【最近对话】\n" + "\n".join(msg_lines))

        parts.append("【当前用户问题】\n" + (user_text or "").strip())
        return {
            "task_content": "\n\n".join([p for p in parts if p.strip()]),
            "memory_source_path": memory_source_path,
            "memory_keyline_hits": len(memory_evidence) if long_term_memory else 0,
            "vector_hit_count": len(conversation_memory_hits) + len(doc_hits),
            "conversation_memory_hit_count": len(conversation_memory_hits),
            "document_hit_count": len(doc_hits),
            "document_vector_scope": DOC_CHUNK_SCOPE,
            "document_vector_kind": DOC_CHUNK_KIND,
            "retrieval_mode": retrieval_mode,
            "active_embedding_profile": str(runtime_info.get("profile") or ""),
            "active_embedding_model": str(runtime_info.get("model") or ""),
            "memory_load_error": memory_load_error,
            "vector_search_error": vector_search_error,
            "memory_min_score": float(memory_min_score),
            "retrieval_queries": retrieval_queries,
        }

    def build_task_content(
        self,
        conversation_id: Optional[str],
        user_text: str,
        recent_limit: int = 20,
        memory_k: int = 8,
        memory_min_score: float = DEFAULT_MEMORY_MIN_SCORE,
    ) -> str:
        bundle = self.build_task_bundle(
            conversation_id=conversation_id,
            user_text=user_text,
            recent_limit=recent_limit,
            memory_k=memory_k,
            memory_min_score=memory_min_score,
        )
        return str(bundle.get("task_content") or "")


context_builder = ContextBuilder()
