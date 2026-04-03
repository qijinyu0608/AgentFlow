from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..common import load_config, config, ModelFactory
from ..models.llm.base_model import LLMRequest
from .conversation_service import ConversationMessageRow, conversation_service


def estimate_tokens(text: str) -> int:
    # Cheap heuristic: ~4 chars per token for mixed zh/en is imperfect but stable.
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class CompressionConfig:
    max_context_tokens: int = 6000
    keep_recent_messages: int = 20
    auto_message_gap: int = 40  # messages since last summary end
    summarizer_model: str = "gpt-4.1"


class CompressionService:
    def __init__(self):
        self.model_factory = ModelFactory()
        load_config()

    def _get_cfg(self) -> CompressionConfig:
        # Allow override through config.yaml (optional)
        raw = (config() or {}).get("memory", {}).get("compression", {}) if isinstance(config(), dict) else {}
        return CompressionConfig(
            max_context_tokens=int(raw.get("max_context_tokens", 6000)),
            keep_recent_messages=int(raw.get("keep_recent_messages", 20)),
            auto_message_gap=int(raw.get("auto_message_gap", 40)),
            summarizer_model=str(raw.get("summarizer_model", "gpt-4.1")),
        )

    def _format_messages(self, messages: List[ConversationMessageRow]) -> str:
        lines: List[str] = []
        for m in messages:
            role = m.role
            lines.append(f"[{m.seq}] {role}: {m.content}".strip())
        return "\n".join(lines).strip()

    def summarize_range(
        self,
        conversation_id: str,
        start_seq: int,
        end_seq: int,
        instructions: str = "",
    ) -> Dict[str, Any]:
        existing = conversation_service.get_summary(conversation_id)
        msgs = conversation_service.get_messages_range(conversation_id, start_seq=start_seq, end_seq=end_seq)
        if not msgs:
            return {
                "conversation_id": conversation_id,
                "summary": existing.summary if existing else "",
                "window_start_seq": existing.window_start_seq if existing else 0,
                "window_end_seq": existing.window_end_seq if existing else 0,
                "skipped": True,
                "reason": "empty_range",
            }

        base_summary = existing.summary.strip() if existing and existing.summary else ""
        transcript = self._format_messages(msgs)
        user_instructions = (instructions or "").strip()

        prompt = f"""你是“会话滚动摘要器”。你要把对话压缩成一个可持续更新的摘要，帮助后续对话保持上下文一致。\n\n要求：\n- 只保留对未来有用的信息，避免无关闲聊\n- 明确记录：Facts / Preferences / Constraints / Decisions / OpenQuestions / TODOs\n- 如遇到新信息推翻旧信息，要在摘要中以“最新为准”更新，不要并列堆叠\n- 输出使用中文，格式为 Markdown 小标题\n\n{('附加指令：' + user_instructions) if user_instructions else ''}\n\n已有摘要（若为空表示首次）：\n{base_summary or '(空)'}\n\n需要压缩的新增对话片段：\n{transcript}\n\n请输出新的“滚动摘要”（完整替换旧摘要）："""

        cfg = self._get_cfg()
        model = self.model_factory.get_model(cfg.summarizer_model)
        resp = model.call(
            LLMRequest(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        )
        if resp.is_error:
            raise RuntimeError(resp.get_error_msg())
        summary_text = (
            (((resp.data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()

        # window_start_seq should be stable (first summarized seq)
        window_start = existing.window_start_seq if existing else int(start_seq)
        window_end = max(int(end_seq), existing.window_end_seq if existing else 0)
        row = conversation_service.upsert_summary(
            conversation_id=conversation_id,
            summary=summary_text,
            window_start_seq=int(window_start),
            window_end_seq=int(window_end),
            meta={"updated_by": "compress"},
        )
        return {
            "conversation_id": row.conversation_id,
            "summary": row.summary,
            "window_start_seq": row.window_start_seq,
            "window_end_seq": row.window_end_seq,
            "updated_at": row.updated_at,
        }

    def maybe_auto_compress(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        cfg = self._get_cfg()
        max_seq = conversation_service.get_max_seq(conversation_id)
        existing = conversation_service.get_summary(conversation_id)
        last_end = existing.window_end_seq if existing else 0
        gap = max_seq - last_end
        if gap < cfg.auto_message_gap:
            return None

        # Compress older range, keep last N messages raw
        keep_from_seq = max(1, max_seq - cfg.keep_recent_messages + 1)
        end_seq = min(keep_from_seq - 1, max_seq)
        if end_seq <= last_end:
            return None
        start_seq = last_end + 1 if last_end > 0 else 1
        if start_seq > end_seq:
            return None
        return self.summarize_range(conversation_id, start_seq=start_seq, end_seq=end_seq, instructions="自动压缩")


compression_service = CompressionService()

