from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enumeration"""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"


class Task(BaseModel):
    """Task entity model"""
    task_id: str = Field(..., description="Task ID")
    task_status: TaskStatus = Field(..., description="Task status")
    task_name: str = Field(..., description="Task name")
    task_content: str = Field(..., description="Task content description")
    submit_time: datetime = Field(..., description="Task submission time")


class TaskQueryRequest(BaseModel):
    """Task query request model"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size")
    status: Optional[TaskStatus] = Field(default=None, description="Task status filter")
    task_name: Optional[str] = Field(default=None, description="Task name search")


class TaskQueryResponse(BaseModel):
    """Task query response model"""
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    tasks: List[Task] = Field(..., description="List of tasks")


class ApiResponse(BaseModel):
    """Standard API response model"""
    code: int = Field(..., description="Response status code")
    message: str = Field(..., description="Response message")
    data: Optional[TaskQueryResponse] = Field(default=None, description="Response data")


# WebSocket Models
class WebSocketMessage(BaseModel):
    """Base WebSocket message model"""
    event: str = Field(..., description="Event type")
    task_id: Optional[str] = Field(default=None, description="Task ID")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp")
    data: dict = Field(default_factory=dict, description="Message data")


class UserInputMessage(WebSocketMessage):
    """User input message from frontend"""
    event: str = Field(default="user_input", description="Event type")
    data: dict = Field(..., description="User input data")


class TaskSubmitResponse(WebSocketMessage):
    """Task submission response"""
    event: str = Field(default="user_task_submit", description="Event type")
    data: dict = Field(..., description="Task submission result")


class AgentDecisionMessage(WebSocketMessage):
    """Agent decision message"""
    event: str = Field(default="agent_decision", description="Event type")
    data: dict = Field(..., description="Agent decision data")


class AgentThinkingMessage(WebSocketMessage):
    """Agent thinking process message"""
    event: str = Field(default="agent_thinking", description="Event type")
    data: dict = Field(..., description="Agent thinking data")


class ToolDecisionMessage(WebSocketMessage):
    """Tool decision message"""
    event: str = Field(default="tool_decision", description="Event type")
    data: dict = Field(..., description="Tool decision data")


class ToolExecuteMessage(WebSocketMessage):
    """Tool execution result message"""
    event: str = Field(default="tool_execute", description="Event type")
    data: dict = Field(..., description="Tool execution data")


class AgentResultMessage(WebSocketMessage):
    """Agent result message"""
    event: str = Field(default="agent_result", description="Event type")
    data: dict = Field(..., description="Agent result data")


class TaskResultMessage(WebSocketMessage):
    """Task completion message"""
    event: str = Field(default="task_result", description="Event type")
    data: dict = Field(..., description="Task result data") 


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class WorkflowPhase(str, Enum):
    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    AGENT_STARTED = "agent_started"
    AGENT_FINISHED = "agent_finished"
    MEMORY_PRECHECK = "memory_precheck"
    HANDOFF_GENERATED = "handoff_generated"
    HANDOFF_VALIDATED = "handoff_validated"
    HANDOFF_FALLBACK = "handoff_fallback"
    TOOL_DECIDED = "tool_decided"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    MESSAGE = "message"


class WorkflowEventData(BaseModel):
    """
    标准化工作流事件数据（用于前端可视化时间线/泳道、后端落库与回放）。
    """

    seq: int = Field(default=0, ge=0, description="Same task incremental sequence")
    agent: str = Field(default="system", description="Agent/role name")
    phase: WorkflowPhase = Field(default=WorkflowPhase.MESSAGE, description="Workflow phase")
    status: WorkflowStatus = Field(default=WorkflowStatus.RUNNING, description="Workflow status")
    content: str = Field(default="", description="Human-readable content for display")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Extensible metadata (tool, duration, error, etc.)")


def normalize_workflow_event_data(data: Any) -> Dict[str, Any]:
    """
    将历史/运行期产生的松散 dict 归一为 WorkflowEventData schema。
    - 兼容旧字段：phase/status 仍可为任意字符串；会尽量映射到枚举，否则降级为 MESSAGE/RUNNING。
    - 返回 dict，便于继续被 WebSocketMessage 序列化、以及后续落库。
    """
    if isinstance(data, WorkflowEventData):
        return data.model_dump()

    raw: Dict[str, Any] = data if isinstance(data, dict) else {}
    seq = raw.get("seq", 0)
    agent = raw.get("agent", "system")
    content = raw.get("content", "")
    meta = raw.get("meta", {}) or {}

    phase_raw = raw.get("phase", WorkflowPhase.MESSAGE.value)
    status_raw = raw.get("status", WorkflowStatus.RUNNING.value)

    try:
        phase = WorkflowPhase(phase_raw)
    except Exception:
        phase = WorkflowPhase.MESSAGE
        meta = {**meta, "_phase_raw": phase_raw}

    try:
        status = WorkflowStatus(status_raw)
    except Exception:
        status = WorkflowStatus.RUNNING
        meta = {**meta, "_status_raw": status_raw}

    try:
        seq_int = int(seq)
    except Exception:
        seq_int = 0
        meta = {**meta, "_seq_raw": seq}

    return WorkflowEventData(
        seq=seq_int,
        agent=str(agent) if agent is not None else "system",
        phase=phase,
        status=status,
        content=str(content) if content is not None else "",
        meta=meta if isinstance(meta, dict) else {"_meta_raw": meta},
    ).model_dump()


class WorkflowEventMessage(WebSocketMessage):
    """
    通用工作流事件（用于前端可视化时间线/泳道）

    data schema（建议字段）:
      - seq: int（同一 task 内递增）
      - agent: str（角色名，如 Planner/Executor/Reviewer）
      - phase: str（task_started/agent_started/agent_finished/tool_started/tool_finished/task_finished/...）
      - status: str（running/ok/error）
      - content: str（展示文本）
    """
    event: str = Field(default="workflow_event", description="Event type")
    data: dict = Field(default_factory=dict, description="Workflow event data")

    def model_post_init(self, __context: Any) -> None:
        # 兼容旧代码直接传 dict：统一归一化字段，保证后续落库/回放稳定
        object.__setattr__(self, "data", normalize_workflow_event_data(self.data))
