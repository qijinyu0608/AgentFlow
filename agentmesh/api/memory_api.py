from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import agentmesh
from agentmesh.memory import get_default_memory_config
from ..service.unified_memory_service import unified_memory_service


router = APIRouter(prefix="/api/v1/memory", tags=["memory"])

YamlValue = Union[str, List[str], Dict[str, str]]


class LongTermMemoryPayload(BaseModel):
    meta: Dict[str, Any] = Field(default_factory=dict)
    content: str = Field(default="")


class LongTermMemoryResponse(BaseModel):
    workspace_root: str
    path: str
    meta: Dict[str, Any]
    content: str
    updated_at: str


class MemoryItemCreatePayload(BaseModel):
    conversation_id: Optional[str] = None
    scope: str = Field(default="conversation")
    kind: str = Field(default="fact")
    content: str = Field(default="")
    source_message_id: Optional[int] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    deprecate_previous: bool = Field(default=True)


class MemoryItemResponse(BaseModel):
    id: int
    conversation_id: Optional[str] = None
    scope: str
    kind: str
    content: str
    status: str
    source_message_id: Optional[int] = None
    confidence: float
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _get_workspace_root() -> Path:
    # Prefer global workspace if user set it
    try:
        return Path(agentmesh.get_workspace()).expanduser()
    except Exception:
        # Fallback to default memory config
        return get_default_memory_config().get_workspace()


def _get_memory_file() -> Path:
    # Keep response compatibility: this is now a logical source marker.
    return Path("data/sqlite/memory.db::memory_items(long_term/long_term_profile)")


def _parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse a minimal YAML front-matter:
      ---
      key: value
      tags:
        - a
        - b
      ---
      body...
    """
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
            # list, mapping, or block scalar
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

            # list block
            items: List[str] = []
            j = i
            while j < len(raw) and raw[j].startswith("  - "):
                items.append(raw[j][4:].strip())
                j += 1
            if items:
                i = j
                meta[key] = items
                continue

            # mapping block (custom_kv)
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

    # normalize legacy fields
    if "custom_kv" in meta and "custom" not in meta:
        meta["custom"] = meta.pop("custom_kv")  # type: ignore[assignment]
    return dict(meta), body.lstrip("\n")


def _render_front_matter(meta: Dict[str, Any], body: str) -> str:
    lines: List[str] = ["---"]
    # stable ordering for common fields; keep the rest appended
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
                if not s:
                    continue
                lines.append(f"  - {s}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for mk, mv in v.items():
                mk_s = str(mk).strip()
                if not mk_s:
                    continue
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
    fm = "\n".join(lines)
    body = body or ""
    body = body.rstrip() + "\n"
    return f"{fm}\n\n{body}"


@router.get("/long-term", response_model=LongTermMemoryResponse)
async def get_long_term_memory() -> LongTermMemoryResponse:
    snapshot = unified_memory_service.get_long_term_memory()
    text = snapshot.raw_text
    meta, content = _parse_front_matter(text)
    workspace_root = str(_get_workspace_root())
    updated_at = meta.get("updated_at") or snapshot.updated_at or datetime.now().isoformat()

    return LongTermMemoryResponse(
        workspace_root=workspace_root,
        path=str(_get_memory_file()),
        meta=meta,
        content=content,
        updated_at=str(updated_at),
    )


@router.put("/long-term", response_model=LongTermMemoryResponse)
async def put_long_term_memory(
    payload: LongTermMemoryPayload,
    reindex: bool = Query(default=False, description="Whether to reindex memory after saving"),
) -> LongTermMemoryResponse:
    meta = dict(payload.meta or {})
    snapshot = unified_memory_service.put_long_term_memory(meta=meta, content=payload.content or "")
    if reindex:
        snapshot = unified_memory_service.reindex_long_term_memory()

    return LongTermMemoryResponse(
        workspace_root=str(_get_workspace_root()),
        path=str(_get_memory_file()),
        meta=snapshot.meta,
        content=snapshot.body_text,
        updated_at=snapshot.updated_at,
    )


@router.post("/items", response_model=MemoryItemResponse)
async def create_memory_item(payload: MemoryItemCreatePayload) -> MemoryItemResponse:
    if not (payload.content or "").strip():
        raise HTTPException(status_code=400, detail="content is required")
    try:
        item_id = unified_memory_service.create_memory_item(
            content=payload.content.strip(),
            scope=payload.scope,
            kind=payload.kind,
            conversation_id=payload.conversation_id,
            source_message_id=payload.source_message_id,
            confidence=float(payload.confidence),
            tags=payload.tags,
            deprecate_previous=bool(payload.deprecate_previous),
            with_embedding=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    item = unified_memory_service.get_memory_item(item_id)
    if not item:
        raise HTTPException(status_code=500, detail="Failed to create memory item")
    return MemoryItemResponse(**item)


@router.get("/items", response_model=List[MemoryItemResponse])
async def list_memory_items(
    conversation_id: Optional[str] = None,
    scope: Optional[str] = None,
    kind: Optional[str] = None,
    status: str = "active",
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> List[MemoryItemResponse]:
    items = unified_memory_service.list_memory_items(
        conversation_id=conversation_id,
        scope=scope,
        kind=kind,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [MemoryItemResponse(**it) for it in items]


@router.get("/search")
async def search_memory_items(
    q: str,
    conversation_id: Optional[str] = None,
    scope: Optional[str] = None,
    kind: Optional[str] = None,
    k: int = Query(default=10, ge=1, le=50),
):
    if not (q or "").strip():
        raise HTTPException(status_code=400, detail="q is required")
    hits = unified_memory_service.search_text(
        q=q.strip(),
        conversation_id=conversation_id,
        scope=scope,
        kind=kind,
        k=k,
    )
    return {"code": 200, "message": "success", "data": {"q": q, "hits": hits}}


@router.get("/vector-search")
async def vector_search_memory_items(
    q: str,
    conversation_id: Optional[str] = None,
    scope: Optional[str] = None,
    kind: Optional[str] = None,
    k: int = Query(default=10, ge=1, le=50),
    min_score: Optional[float] = Query(default=0.35, ge=0.0),
):
    if not (q or "").strip():
        raise HTTPException(status_code=400, detail="q is required")
    try:
        hits = unified_memory_service.search_vector(
            q=q.strip(),
            conversation_id=conversation_id,
            k=int(k),
            min_score=min_score,
            scope=scope,
            kind=kind,
        )
        data = [
            {"memory_item_id": h.memory_item_id, "score": h.score, "content": h.content, "meta": h.meta}
            for h in hits
        ]
        return {
            "code": 200,
            "message": "success",
            "data": {
                "q": q,
                "scope": scope,
                "kind": kind,
                "k": k,
                "min_score": min_score,
                "hits": data,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")
