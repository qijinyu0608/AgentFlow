"""Legacy long-term memory file access retained as a compatibility shim."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import agentmesh
from agentmesh.memory import MemoryConfig, get_default_memory_config


@dataclass(frozen=True)
class LongTermMemorySnapshot:
    path: Path
    raw_text: str
    body_text: str


class LongTermMemoryService:
    """
    Resolve and read long-term memory file with stable priority:
    1) AGENTMESH_MEMORY_FILE (explicit override)
    2) workspace memory dir (agentmesh/memory/MEMORY.md)
    3) legacy default path in home dir (~/agentmesh/memory/MEMORY.md)
    """

    def _workspace_memory_file(self) -> Path:
        try:
            workspace_root = Path(agentmesh.get_workspace()).expanduser()
        except Exception:
            workspace_root = get_default_memory_config().get_workspace()
        memory_dir = Path(MemoryConfig(workspace_root=str(workspace_root)).get_memory_dir())
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir / "MEMORY.md"

    @staticmethod
    def _legacy_memory_file() -> Path:
        return Path.home() / "agentmesh" / "memory" / "MEMORY.md"

    def resolve_memory_file(self) -> Path:
        override = (os.environ.get("AGENTMESH_MEMORY_FILE") or "").strip()
        if override:
            p = Path(override).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            return p

        workspace_file = self._workspace_memory_file()
        if workspace_file.exists():
            return workspace_file

        legacy_file = self._legacy_memory_file()
        if legacy_file.exists():
            return legacy_file
        return workspace_file

    @staticmethod
    def strip_front_matter(text: str) -> str:
        if not text.startswith("---\n"):
            return text
        end = text.find("\n---\n", 4)
        if end == -1:
            return text
        return text[end + 5 :].lstrip("\n")

    def load(self, max_chars: Optional[int] = None) -> LongTermMemorySnapshot:
        path = self.resolve_memory_file()
        if not path.exists():
            return LongTermMemorySnapshot(path=path, raw_text="", body_text="")
        raw = path.read_text(encoding="utf-8")
        body = self.strip_front_matter(raw).strip()
        if max_chars and max_chars > 0:
            body = body[: int(max_chars)].strip()
        return LongTermMemorySnapshot(path=path, raw_text=raw, body_text=body)


long_term_memory_service = LongTermMemoryService()
