from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmesh.memory import memory_manager
from agentmesh.tools.base_tool import BaseTool, ToolResult


class MemoryGet(BaseTool):
    name = "memory_get"
    description = "Read a memory item or a path/line snippet for a search hit. File snippets are returned with source comments."
    params = {
        "type": "object",
        "properties": {
            "memory_item_id": {"type": "integer", "description": "Memory item id to inspect"},
            "path": {"type": "string", "description": "Optional source file path to read directly"},
            "start_line": {"type": "integer", "description": "Start line for path reads (1-indexed)", "default": 1},
            "end_line": {"type": "integer", "description": "End line for path reads (inclusive)"},
        },
        "required": [],
    }

    @staticmethod
    def _read_path_lines(path: Path, start_line: int, end_line: Optional[int]) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        start = max(1, int(start_line))
        end = min(total, int(end_line or min(total, start + 29)))
        if start > total:
            raise ValueError(f"start_line {start} exceeds file length {total}")

        selected = lines[start - 1 : end]
        annotated: List[str] = [
            f"# Source: {path}",
            f"# Lines: {start}-{end}",
        ]
        for idx, line in enumerate(selected, start=start):
            annotated.append(f"{idx}: {line}")
        return {
            "path": str(path),
            "start_line": start,
            "end_line": end,
            "content": "\n".join(annotated),
        }

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        memory_item_id = params.get("memory_item_id")
        raw_path = str(params.get("path") or "").strip()
        start_line = int(params.get("start_line") or 1)
        end_line = params.get("end_line")

        if memory_item_id is None and not raw_path:
            return ToolResult.fail("memory_item_id or path is required")

        if raw_path:
            try:
                snippet = self._read_path_lines(Path(raw_path).expanduser(), start_line=start_line, end_line=end_line)
            except Exception as exc:
                return ToolResult.fail(str(exc))
            return ToolResult.success(snippet)

        item = memory_manager.get_memory_item(int(memory_item_id))
        if not item:
            return ToolResult.fail(f"Memory item not found: {memory_item_id}")

        source = dict(item.get("source") or {})
        annotated = [
            f"# memory_item_id: {item['id']}",
            f"# scope: {item.get('scope')}",
            f"# kind: {item.get('kind')}",
        ]
        if source.get("file_name"):
            annotated.append(
                f"# source_document: {source.get('file_name')} (document_id={source.get('document_id')}, chunk_index={source.get('chunk_index')})"
            )
        annotated.append(str(item.get("content") or "").strip())

        result = {
            "memory_item": item,
            "content": "\n".join(annotated),
        }
        return ToolResult.success(result)
