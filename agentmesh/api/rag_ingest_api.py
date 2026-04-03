from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..service.rag_ingest_service import rag_ingest_service
from ..service.rag_ops_service import rag_ops_service
from ..service.unified_memory_service import unified_memory_service


router = APIRouter(prefix="/api/v1/rag", tags=["rag-ingest"])


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Dict[str, Any]] = None


class AnnotatePayload(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    paragraph_marks: List[Dict[str, Any]] = Field(default_factory=list)


class IngestPayload(BaseModel):
    chunk_size: int = Field(default=700, ge=200, le=2000)
    overlap: int = Field(default=100, ge=0, le=500)


class RebuildPayload(BaseModel):
    chunk_size: int = Field(default=700, ge=200, le=2000)
    overlap: int = Field(default=100, ge=0, le=500)
    skip_reindex: bool = False


@router.post("/upload", response_model=ApiResponse)
async def upload_rag_file(file: UploadFile = File(...)) -> ApiResponse:
    try:
        content = await file.read()
        doc = rag_ingest_service.save_upload(
            filename=file.filename or "unknown.txt",
            mime_type=file.content_type or "application/octet-stream",
            content=content,
        )
        return ApiResponse(data=doc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.get("/ops/overview", response_model=ApiResponse)
async def get_rag_ops_overview(
    document_id: Optional[int] = Query(default=None, ge=1),
    history_limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse:
    try:
        data = rag_ops_service.get_overview(history_document_id=document_id, history_limit=int(history_limit))
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load RAG ops overview failed: {e}")


@router.post("/ops/rebuild", response_model=ApiResponse)
async def rebuild_rag_indices(payload: RebuildPayload) -> ApiResponse:
    try:
        data = rag_ops_service.rebuild_indices(
            chunk_size=int(payload.chunk_size),
            overlap=int(payload.overlap),
            skip_reindex=bool(payload.skip_reindex),
        )
        return ApiResponse(data=data)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rebuild RAG indices failed: {e}")


@router.get("/documents", response_model=ApiResponse)
async def list_rag_documents(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse:
    try:
        out = rag_ingest_service.list_documents(limit=int(limit), offset=int(offset))
        return ApiResponse(data=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List documents failed: {e}")


@router.get("/{document_id}/history", response_model=ApiResponse)
async def get_rag_document_history(
    document_id: int,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse:
    try:
        data = rag_ops_service.get_document_history(document_id=int(document_id), limit=int(limit))
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get document history failed: {e}")


@router.post("/{document_id}/annotate", response_model=ApiResponse)
async def annotate_rag_document(document_id: int, payload: AnnotatePayload) -> ApiResponse:
    try:
        rag_ingest_service.set_annotation(
            document_id=int(document_id),
            metadata=payload.metadata or {},
            paragraph_marks=payload.paragraph_marks or [],
        )
        doc = rag_ingest_service.get_document(int(document_id), include_paragraphs=True, include_raw_text=False)
        return ApiResponse(data=doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Annotate failed: {e}")


@router.post("/{document_id}/ingest", response_model=ApiResponse)
async def ingest_rag_document(document_id: int, payload: IngestPayload) -> ApiResponse:
    try:
        result = unified_memory_service.ingest_document(
            document_id=int(document_id),
            chunk_size=int(payload.chunk_size),
            overlap=int(payload.overlap),
        )
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")


@router.get("/{document_id}", response_model=ApiResponse)
async def get_rag_document(document_id: int, include_paragraphs: bool = Query(default=True)) -> ApiResponse:
    try:
        doc = rag_ingest_service.get_document(
            int(document_id),
            include_paragraphs=bool(include_paragraphs),
            include_raw_text=False,
        )
        return ApiResponse(data=doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get document failed: {e}")


@router.get("/{document_id}/chunks", response_model=ApiResponse)
async def list_rag_chunks(
    document_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse:
    try:
        out = rag_ingest_service.list_chunks(int(document_id), limit=int(limit), offset=int(offset))
        return ApiResponse(data=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List chunks failed: {e}")


@router.delete("/{document_id}", response_model=ApiResponse)
async def delete_rag_document(document_id: int) -> ApiResponse:
    try:
        out = rag_ingest_service.delete_document(int(document_id))
        return ApiResponse(data=out)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete document failed: {e}")
