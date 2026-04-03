from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import MemoryConfig, get_default_memory_config


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start_char: int
    end_char: int
    approx_tokens: int
    source_path: Optional[str] = None


class TextChunker:
    """Chunk text into overlapping windows for embedding/indexing."""

    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or get_default_memory_config()

    @staticmethod
    def _split_paragraphs(text: str) -> List[str]:
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []
        return [p.strip() for p in normalized.split("\n\n") if p.strip()]

    def chunk_text(
        self,
        text: str,
        source_path: Optional[str] = None,
        chunk_max_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
    ) -> List[TextChunk]:
        max_tokens = int(chunk_max_tokens or self.config.chunk_max_tokens)
        overlap_tokens = int(chunk_overlap_tokens or self.config.chunk_overlap_tokens)
        max_chars = max(1, max_tokens * 4)
        overlap_chars = max(0, overlap_tokens * 4)
        step = max(1, max_chars - overlap_chars)

        paragraphs = self._split_paragraphs(text)
        chunks: List[TextChunk] = []
        cursor = 0

        for paragraph in paragraphs:
            para = paragraph.strip()
            if not para:
                continue
            if len(para) <= max_chars:
                start_char = cursor
                end_char = cursor + len(para)
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        text=para,
                        start_char=start_char,
                        end_char=end_char,
                        approx_tokens=estimate_tokens(para),
                        source_path=source_path,
                    )
                )
                cursor = end_char + 2
                continue

            start = 0
            while start < len(para):
                piece = para[start : start + max_chars].strip()
                if piece:
                    absolute_start = cursor + start
                    chunks.append(
                        TextChunk(
                            index=len(chunks),
                            text=piece,
                            start_char=absolute_start,
                            end_char=absolute_start + len(piece),
                            approx_tokens=estimate_tokens(piece),
                            source_path=source_path,
                        )
                    )
                start += step
            cursor += len(para) + 2

        return chunks


text_chunker = TextChunker()
