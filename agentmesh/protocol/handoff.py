from __future__ import annotations

from typing import Any, Dict, List, Optional


class HandoffValidationError(ValueError):
    """Raised when a handoff payload is invalid."""


class HandoffEnvelope:
    """Semi-structured handoff payload between agents."""

    def __init__(
        self,
        next_agent_id: int,
        goal: str,
        done: Optional[List[str]] = None,
        todo: Optional[List[str]] = None,
        notes: str = "",
        handoff_summary: str = "",
        legacy_subtask: str = "",
        task_short_name: Optional[str] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
        validation_status: str = "validated",
        fallback_used: bool = False,
    ):
        self.next_agent_id = int(next_agent_id)
        self.goal = str(goal or "").strip()
        self.done = [str(x).strip() for x in (done or []) if str(x).strip()]
        self.todo = [str(x).strip() for x in (todo or []) if str(x).strip()]
        self.notes = str(notes or "").strip()
        self.handoff_summary = str(handoff_summary or "").strip()
        self.legacy_subtask = str(legacy_subtask or "").strip()
        self.task_short_name = (
            str(task_short_name or "").strip() if task_short_name is not None else None
        )
        self.raw_payload = dict(raw_payload or {})
        self.validation_status = str(validation_status or "validated")
        self.fallback_used = bool(fallback_used)

    @property
    def subtask(self) -> str:
        """Backward-compatible text view for agent execution."""
        pieces: List[str] = []
        if self.goal:
            pieces.append(self.goal)
        if self.todo:
            pieces.append("待完成事项：\n" + "\n".join(f"- {item}" for item in self.todo))
        if self.notes:
            pieces.append("补充说明：\n" + self.notes)
        if self.legacy_subtask:
            pieces.append("原始交接文本：\n" + self.legacy_subtask)
        return "\n\n".join(piece for piece in pieces if piece.strip()).strip()

    def render_for_prompt(self) -> str:
        done_lines = "\n".join(f"- {item}" for item in self.done) if self.done else "- 暂无"
        todo_lines = "\n".join(f"- {item}" for item in self.todo) if self.todo else "- 暂无"
        notes = self.notes or "无"
        legacy = self.legacy_subtask or "无"
        return (
            "## Structured handoff\n"
            f"Goal:\n{self.goal or '无'}\n\n"
            f"Done:\n{done_lines}\n\n"
            f"Todo:\n{todo_lines}\n\n"
            f"Notes:\n{notes}\n\n"
            f"Legacy subtask text:\n{legacy}"
        )

    def summary_text(self) -> str:
        if self.handoff_summary:
            return self.handoff_summary
        todo_head = self.todo[0] if self.todo else self.goal
        return (todo_head or self.legacy_subtask or "已生成交接").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "next_agent_id": self.next_agent_id,
            "goal": self.goal,
            "done": list(self.done),
            "todo": list(self.todo),
            "notes": self.notes,
            "handoff_summary": self.handoff_summary,
            "legacy_subtask": self.legacy_subtask,
            "task_short_name": self.task_short_name,
            "validation_status": self.validation_status,
            "fallback_used": self.fallback_used,
        }

    @classmethod
    def from_payload(
        cls,
        payload: Dict[str, Any],
        *,
        allow_stop: bool = False,
        current_agent_id: Optional[int] = None,
        valid_agent_ids: Optional[List[int]] = None,
        task_short_name: Optional[str] = None,
    ) -> "HandoffEnvelope":
        if not isinstance(payload, dict):
            raise HandoffValidationError("handoff payload must be a JSON object")

        candidate_next_id = payload.get("next_agent_id", payload.get("id"))
        if candidate_next_id is None:
            raise HandoffValidationError("missing next_agent_id")
        try:
            next_agent_id = int(candidate_next_id)
        except Exception as exc:
            raise HandoffValidationError("next_agent_id must be an integer") from exc

        if next_agent_id < 0:
            if allow_stop and next_agent_id == -1:
                return cls(
                    next_agent_id=-1,
                    goal="",
                    done=[],
                    todo=[],
                    notes=str(payload.get("notes") or "").strip(),
                    handoff_summary=str(payload.get("handoff_summary") or "").strip(),
                    legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
                    task_short_name=task_short_name or payload.get("task_short_name"),
                    raw_payload=payload,
                    validation_status="validated",
                    fallback_used=False,
                )
            raise HandoffValidationError("next_agent_id must be >= 0")

        if valid_agent_ids is not None and next_agent_id not in valid_agent_ids:
            raise HandoffValidationError("next_agent_id is not a valid agent")
        if current_agent_id is not None and next_agent_id == current_agent_id:
            raise HandoffValidationError("next_agent_id cannot equal current agent")

        goal = str(payload.get("goal") or payload.get("subtask") or "").strip()
        if not goal:
            raise HandoffValidationError("goal is required")

        done = payload.get("done", [])
        todo = payload.get("todo", [])
        if isinstance(done, str):
            done = [done]
        if isinstance(todo, str):
            todo = [todo]
        if not isinstance(done, list):
            raise HandoffValidationError("done must be a list of strings")
        if not isinstance(todo, list):
            raise HandoffValidationError("todo must be a list of strings")

        cleaned_todo = [str(x).strip() for x in todo if str(x).strip()]
        if not cleaned_todo:
            raise HandoffValidationError("todo must contain at least one item")

        return cls(
            next_agent_id=next_agent_id,
            goal=goal,
            done=done,
            todo=cleaned_todo,
            notes=str(payload.get("notes") or "").strip(),
            handoff_summary=str(payload.get("handoff_summary") or "").strip(),
            legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
            task_short_name=task_short_name or payload.get("task_short_name"),
            raw_payload=payload,
            validation_status="validated",
            fallback_used=False,
        )

    @classmethod
    def fallback(
        cls,
        *,
        next_agent_id: int,
        legacy_subtask: str,
        task_short_name: Optional[str] = None,
        reason: str = "",
    ) -> "HandoffEnvelope":
        legacy = str(legacy_subtask or "").strip()
        goal = legacy or "继续处理当前任务"
        todo = [legacy] if legacy else ["继续根据当前上下文完成任务"]
        notes = str(reason or "").strip()
        return cls(
            next_agent_id=next_agent_id,
            goal=goal,
            done=[],
            todo=todo,
            notes=notes,
            handoff_summary=legacy[:200] if legacy else "fallback handoff",
            legacy_subtask=legacy,
            task_short_name=task_short_name,
            raw_payload={
                "next_agent_id": next_agent_id,
                "legacy_subtask": legacy,
                "reason": notes,
            },
            validation_status="fallback",
            fallback_used=True,
        )
