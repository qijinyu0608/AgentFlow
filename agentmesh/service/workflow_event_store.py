import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..common.database import conversation_db_manager
from ..common.models import normalize_workflow_event_data


class WorkflowEventStore:
    """
    事件持久化与查询（SQLite）。
    - 写入：用于实时执行期间落库
    - 查询：用于前端回放与指标聚合
    """

    def __init__(self):
        self.db_manager = conversation_db_manager

    def append_event(self, task_id: str, timestamp_iso: Optional[str], data: Any) -> None:
        normalized = normalize_workflow_event_data(data)
        ts = timestamp_iso or datetime.now().isoformat()
        raw_json = json.dumps(normalized, ensure_ascii=False)

        query = """
            INSERT INTO workflow_events (task_id, seq, agent, phase, status, content, ts, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task_id,
            int(normalized.get("seq", 0) or 0),
            str(normalized.get("agent", "system") or "system"),
            str(normalized.get("phase", "message") or "message"),
            str(normalized.get("status", "running") or "running"),
            str(normalized.get("content", "") or ""),
            ts,
            raw_json,
        )
        self.db_manager.execute_update(query, params)

    def list_events(
        self,
        task_id: str,
        limit: int = 2000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT task_id, seq, agent, phase, status, content, ts, raw_json
            FROM workflow_events
            WHERE task_id = ?
            ORDER BY seq ASC, ts ASC, id ASC
            LIMIT ? OFFSET ?
        """
        rows = self.db_manager.execute_query(query, (task_id, limit, offset))
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r["raw_json"])
            except Exception:
                payload = {
                    "seq": r["seq"],
                    "agent": r["agent"],
                    "phase": r["phase"],
                    "status": r["status"],
                    "content": r["content"],
                    "meta": {},
                }
            out.append(
                {
                    "task_id": r["task_id"],
                    "timestamp": r["ts"],
                    "data": payload,
                }
            )
        return out

    def list_agents(self, task_id: str) -> List[str]:
        query = """
            SELECT DISTINCT agent
            FROM workflow_events
            WHERE task_id = ?
            ORDER BY agent ASC
        """
        rows = self.db_manager.execute_query(query, (task_id,))
        return [row["agent"] for row in rows]

    def compute_graph(self, task_id: str) -> Dict[str, Any]:
        """
        以事件为基础构建协作图（简化版）：
        - nodes: agent 列表
        - edges: 依据 agent_started 的顺序构建相邻调用边（A->B）
          并尽量从 meta.sub_task 聚合“交接内容”片段，便于展示协作细节
        """
        events = self.list_events(task_id, limit=100000, offset=0)
        started_agents: List[str] = []
        started_meta: List[Dict[str, Any]] = []
        for ev in events:
            d = (ev.get("data") or {}) if isinstance(ev, dict) else {}
            if d.get("phase") == "agent_started":
                started_agents.append(d.get("agent", "system"))
                started_meta.append(d.get("meta") or {})

        nodes = sorted({a for a in started_agents if a})
        edge_counts: Dict[Tuple[str, str], int] = {}
        edge_samples: Dict[Tuple[str, str], List[str]] = {}
        for i in range(len(started_agents) - 1):
            a, b = started_agents[i], started_agents[i + 1]
            if not a or not b or a == b:
                continue
            edge_counts[(a, b)] = edge_counts.get((a, b), 0) + 1
            sub = (started_meta[i + 1].get("sub_task") or "").strip()
            if sub:
                arr = edge_samples.setdefault((a, b), [])
                if len(arr) < 3 and sub not in arr:
                    arr.append(sub[:200])

        edges = [
            {"source": s, "target": t, "count": c, "samples": edge_samples.get((s, t), [])}
            for (s, t), c in sorted(edge_counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
        ]
        return {"task_id": task_id, "nodes": [{"id": n} for n in nodes], "edges": edges}

    def compute_metrics(self, task_id: str) -> Dict[str, Any]:
        """
        简化指标：
        - 每 agent 的事件数、error 数、tool 相关事件数
        - 任务总事件数
        """
        events = self.list_events(task_id, limit=100000, offset=0)
        per: Dict[str, Dict[str, Any]] = {}
        for ev in events:
            d = ev.get("data") or {}
            agent = d.get("agent", "system") or "system"
            phase = d.get("phase", "message")
            status = d.get("status", "running")
            m = per.setdefault(agent, {"agent": agent, "event_count": 0, "error_count": 0, "tool_event_count": 0, "agent_turns": 0})
            m["event_count"] += 1
            if status == "error":
                m["error_count"] += 1
            if str(phase).startswith("tool_") or phase == "tool_decided":
                m["tool_event_count"] += 1
            if phase == "agent_started":
                m["agent_turns"] += 1

        return {"task_id": task_id, "total_events": len(events), "agents": list(per.values())}


workflow_event_store = WorkflowEventStore()

