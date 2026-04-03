from __future__ import annotations

from typing import Any, Dict, Optional

from ..service.compression_service import compression_service


class MemorySummarizer:
    """Flush conversation memory into rolling summaries before context compression."""

    def flush_conversation(
        self,
        conversation_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        instructions: str = "",
    ) -> Dict[str, Any]:
        if start_seq is not None and end_seq is not None:
            return compression_service.summarize_range(
                conversation_id=conversation_id,
                start_seq=int(start_seq),
                end_seq=int(end_seq),
                instructions=instructions,
            )
        result = compression_service.maybe_auto_compress(conversation_id)
        return result or {
            "conversation_id": conversation_id,
            "skipped": True,
            "reason": "auto_flush_not_needed",
        }


memory_summarizer = MemorySummarizer()
