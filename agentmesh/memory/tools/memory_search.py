from __future__ import annotations

from typing import Any, Dict, List

from agentmesh.memory import memory_manager
from agentmesh.tools.base_tool import BaseTool, ToolResult


class MemorySearch(BaseTool):
    name = "memory_search"
    description = "Search conversation memory and knowledge-base chunks before answering. Supports hybrid/vector/keyword retrieval."
    params = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "conversation_id": {"type": "string", "description": "Conversation id for scoped memory retrieval"},
            "scope": {"type": "string", "description": "Optional scope filter, e.g. conversation or knowledge_base"},
            "kind": {"type": "string", "description": "Optional kind filter, e.g. fact or doc_chunk"},
            "mode": {"type": "string", "description": "hybrid | vector | keyword", "default": "hybrid"},
            "top_k": {"type": "integer", "description": "Maximum number of hits", "default": 5},
            "min_score": {"type": "number", "description": "Minimum score threshold", "default": 0.3},
        },
        "required": ["query"],
    }

    @staticmethod
    def _format_source(source: Dict[str, Any]) -> str:
        if not source:
            return "source=memory_items"
        if source.get("file_name"):
            return (
                f"source=document:{source.get('file_name')} "
                f"(document_id={source.get('document_id')}, chunk_index={source.get('chunk_index')})"
            )
        return "source=memory_items"

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        query = str(params.get("query") or "").strip()
        if not query:
            return ToolResult.fail("query is required")

        conversation_id = (params.get("conversation_id") or None) or None
        scope = (params.get("scope") or None) or None
        kind = (params.get("kind") or None) or None
        mode = str(params.get("mode") or "hybrid").strip().lower()
        top_k = max(1, int(params.get("top_k") or 5))
        min_score = float(params.get("min_score") or 0.3)

        if mode == "vector":
            hits = memory_manager.search_vector(
                query=query,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=top_k,
                min_score=min_score,
            )
            items = [
                {
                    "memory_item_id": hit.memory_item_id,
                    "score": hit.score,
                    "content": hit.content,
                    "source": hit.source,
                    "meta": hit.meta,
                }
                for hit in hits
            ]
        elif mode == "keyword":
            hits = memory_manager.search_keyword(
                query=query,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=top_k,
            )
            items = [
                {
                    "memory_item_id": hit.memory_item_id,
                    "score": hit.keyword_score,
                    "content": hit.content,
                    "source": hit.source,
                    "meta": {
                        "conversation_id": hit.conversation_id,
                        "scope": hit.scope,
                        "kind": hit.kind,
                        "confidence": hit.confidence,
                        "updated_at": hit.updated_at,
                        "tags": hit.tags,
                    },
                }
                for hit in hits
            ]
        else:
            hits = memory_manager.search_hybrid(
                query=query,
                conversation_id=conversation_id,
                scope=scope,
                kind=kind,
                k=top_k,
                min_score=min_score,
            )
            items = [memory_manager.serialize_hit(hit) for hit in hits]

        if not items:
            return ToolResult.success(
                {
                    "query": query,
                    "mode": mode,
                    "hits": [],
                    "summary": "No relevant memory found.",
                }
            )

        summary_lines: List[str] = []
        for idx, item in enumerate(items, start=1):
            score = float(item.get("score") or 0.0)
            content = str(item.get("content") or "").strip()
            source = self._format_source(dict(item.get("source") or {}))
            summary_lines.append(f"{idx}. [score={score:.3f}] {source}\n{content}")

        return ToolResult.success(
            {
                "query": query,
                "mode": mode,
                "hits": items,
                "summary": "\n\n".join(summary_lines),
            }
        )
