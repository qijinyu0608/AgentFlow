from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..service.task_service import task_service
from ..common.models import TaskQueryRequest, ApiResponse, TaskQueryResponse
from ..service.workflow_event_store import workflow_event_store

# Create router
router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.post("/tasks/query", response_model=ApiResponse)
async def query_tasks(request: TaskQueryRequest) -> ApiResponse:
    """
    Query task list with pagination and filters
    
    Returns:
        ApiResponse: Standard API response with task list data
    """
    try:
        # Call service layer to get tasks
        result = task_service.query_tasks(request)
        
        return ApiResponse(
            code=200,
            message="success",
            data=result
        )
    
    except Exception as e:
        # Log the error (you can add proper logging here)
        print(f"Error querying tasks: {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error while querying tasks"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Task API is running"} 


@router.get("/tasks/{task_id}/workflow")
async def get_task_workflow(task_id: str, limit: int = 2000, offset: int = 0):
    """
    获取任务协作事件时间线（用于回放/详情页首屏加载）。
    """
    try:
        events = workflow_event_store.list_events(task_id=task_id, limit=limit, offset=offset)
        return {"code": 200, "message": "success", "data": {"task_id": task_id, "limit": limit, "offset": offset, "events": events}}
    except Exception as e:
        print(f"Error getting workflow for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting workflow events")


@router.get("/tasks/{task_id}/graph")
async def get_task_graph(task_id: str):
    """
    获取任务协作图（nodes/edges）。
    """
    try:
        graph = workflow_event_store.compute_graph(task_id=task_id)
        return {"code": 200, "message": "success", "data": graph}
    except Exception as e:
        print(f"Error getting graph for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting workflow graph")


@router.get("/tasks/{task_id}/metrics")
async def get_task_metrics(task_id: str):
    """
    获取任务聚合指标（按 agent 聚合）。
    """
    try:
        metrics = workflow_event_store.compute_metrics(task_id=task_id)
        return {"code": 200, "message": "success", "data": metrics}
    except Exception as e:
        print(f"Error getting metrics for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting workflow metrics")