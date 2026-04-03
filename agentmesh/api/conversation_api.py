from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..service.conversation_service import conversation_service
from ..service.compression_service import compression_service


router = APIRouter(prefix="/api/v1", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None)


class CreateConversationResponse(BaseModel):
    conversation_id: str


class ConversationInfoResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    summary: Optional[Dict[str, Any]] = None


class ConversationOverviewResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    message_count: int = 0
    preview: str = ""
    last_message_at: Optional[str] = None
    latest_task_id: Optional[str] = None
    latest_team: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)


class AppendMessageRequest(BaseModel):
    role: str = Field(..., description="user/assistant/system/tool")
    content: str = Field(default="")
    meta: Dict[str, Any] = Field(default_factory=dict)
    ts: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    ts: str
    seq: int
    meta: Dict[str, Any]


class CompressRequest(BaseModel):
    start_seq: int = Field(..., ge=1)
    end_seq: int = Field(..., ge=1)
    instructions: str = Field(default="")


class SummaryResponse(BaseModel):
    conversation_id: str
    summary: str
    window_start_seq: int
    window_end_seq: int
    updated_at: Optional[str] = None


@router.post("/conversations", response_model=CreateConversationResponse)
async def create_conversation(req: CreateConversationRequest) -> CreateConversationResponse:
    conversation_id = conversation_service.create_conversation(title=req.title)
    return CreateConversationResponse(conversation_id=conversation_id)


@router.get("/conversations", response_model=List[ConversationOverviewResponse])
async def list_conversations(
    status: Optional[str] = Query(default="active"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[ConversationOverviewResponse]:
    rows = conversation_service.list_conversations(status=status or "", limit=limit, offset=offset)
    return [ConversationOverviewResponse(**row) for row in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationInfoResponse)
async def get_conversation(conversation_id: str) -> ConversationInfoResponse:
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    summary = conversation_service.get_summary(conversation_id)
    return ConversationInfoResponse(
        conversation_id=conv["conversation_id"],
        title=conv.get("title"),
        status=conv.get("status") or "active",
        created_at=str(conv.get("created_at")),
        updated_at=str(conv.get("updated_at")),
        summary=summary.__dict__ if summary else None,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationInfoResponse)
async def update_conversation(conversation_id: str, req: UpdateConversationRequest) -> ConversationInfoResponse:
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    next_status = req.status
    if next_status is not None and next_status not in ("active", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    updated = conversation_service.update_conversation(
        conversation_id=conversation_id,
        title=req.title,
        status=next_status,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    summary = conversation_service.get_summary(conversation_id)
    return ConversationInfoResponse(
        conversation_id=updated["conversation_id"],
        title=updated.get("title"),
        status=updated.get("status") or "active",
        created_at=str(updated.get("created_at")),
        updated_at=str(updated.get("updated_at")),
        summary=summary.__dict__ if summary else None,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    deleted = conversation_service.delete_conversation(conversation_id=conversation_id)
    return {
        "code": 200,
        "message": "success",
        "data": deleted,
    }


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def append_message(conversation_id: str, req: AppendMessageRequest) -> MessageResponse:
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if req.role not in ("user", "assistant", "system", "tool"):
        raise HTTPException(status_code=400, detail="Invalid role")
    row = conversation_service.append_message(
        conversation_id=conversation_id,
        role=req.role,
        content=req.content or "",
        meta=req.meta or {},
        ts_iso=req.ts,
    )
    # Auto compression: only triggers when thresholds exceeded.
    try:
        compression_service.maybe_auto_compress(conversation_id)
    except Exception as e:
        # Avoid breaking message append; caller can manually compress later.
        print(f"Auto compress failed for conversation {conversation_id}: {e}")
    return MessageResponse(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        ts=row.ts,
        seq=row.seq,
        meta=row.meta,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: str,
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> List[MessageResponse]:
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = conversation_service.list_messages(conversation_id=conversation_id, limit=limit, offset=offset)
    return [
        MessageResponse(
            id=r.id,
            conversation_id=r.conversation_id,
            role=r.role,
            content=r.content,
            ts=r.ts,
            seq=r.seq,
            meta=r.meta,
        )
        for r in rows
    ]


@router.post("/conversations/{conversation_id}/compress", response_model=SummaryResponse)
async def compress_conversation(conversation_id: str, req: CompressRequest) -> SummaryResponse:
    conv = conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if req.start_seq > req.end_seq:
        raise HTTPException(status_code=400, detail="start_seq must be <= end_seq")
    try:
        out = compression_service.summarize_range(
            conversation_id=conversation_id,
            start_seq=req.start_seq,
            end_seq=req.end_seq,
            instructions=req.instructions or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compression failed: {e}")
    return SummaryResponse(
        conversation_id=out["conversation_id"],
        summary=out["summary"],
        window_start_seq=int(out.get("window_start_seq") or 0),
        window_end_seq=int(out.get("window_end_seq") or 0),
        updated_at=str(out.get("updated_at") or ""),
    )
