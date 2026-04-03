from typing import Dict, Any, Optional, List

from ..common import load_config, config, ModelFactory, logger
from ..protocol import AgentTeam, Agent, Task as AgentTask
from ..skills import SkillManager
from ..tools.tool_manager import ToolManager
# Remove circular import - we'll pass websocket_manager as parameter
from ..common.models import (
    AgentDecisionMessage, AgentThinkingMessage, ToolDecisionMessage,
    ToolExecuteMessage, AgentResultMessage, TaskResultMessage, WorkflowEventMessage
)


class AgentExecutor:
    """Agent executor that integrates with AgentMesh core logic"""

    def __init__(self, websocket_manager=None):
        self.model_factory = ModelFactory()
        self.tool_manager = ToolManager()
        self.skill_manager = SkillManager()
        self.teams_cache = {}
        self.websocket_manager = websocket_manager

        # Load configuration and tools
        self.refresh_runtime_metadata()

    def refresh_runtime_metadata(self):
        load_config()
        self.tool_manager.load_tools()
        self.skill_manager.load_skills()

    @staticmethod
    def _get_teams_config() -> Dict[str, Any]:
        teams_config = config().get("teams", {})
        return teams_config if isinstance(teams_config, dict) else {}

    def list_available_teams(self) -> List[Dict[str, str]]:
        teams: List[Dict[str, str]] = []
        for team_name, team_config in self._get_teams_config().items():
            description = ""
            if isinstance(team_config, dict):
                description = str(team_config.get("description", "") or "")
            teams.append({"name": str(team_name), "description": description})
        return teams

    @staticmethod
    def _normalize_skill_names(skill_names: Optional[List[Any]]) -> List[str]:
        if not isinstance(skill_names, list):
            return []
        out: List[str] = []
        seen = set()
        for item in skill_names:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            out.append(name)
            seen.add(name)
        return out

    @staticmethod
    def _merge_tool_names(skill_tool_names: List[str], agent_tool_names: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for tool_name in list(skill_tool_names or []) + list(agent_tool_names or []):
            name = str(tool_name or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out

    @staticmethod
    def _append_skill_prompts(base_prompt: str, skill_specs: List[Any]) -> str:
        prompt = str(base_prompt or "").strip()
        sections = []
        for spec in skill_specs or []:
            skill_prompt = str(getattr(spec, "prompt", "") or "").strip()
            if not skill_prompt:
                continue
            sections.append(f"## Enabled skill: {spec.name}\n{skill_prompt}")

        if not sections:
            return prompt
        if not prompt:
            return "\n\n".join(sections)
        return f"{prompt}\n\n" + "\n\n".join(sections)

    @staticmethod
    def _normalize_runtime_tools(runtime_tools: Optional[List[Any]]) -> Optional[List[str]]:
        """
        Normalize runtime tool override list.
        - None => no override (use team config tools)
        - []   => explicit override to no tools
        """
        if runtime_tools is None:
            return None
        if not isinstance(runtime_tools, list):
            return []

        out: List[str] = []
        seen = set()
        for item in runtime_tools:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            out.append(name)
            seen.add(name)
        return out

    @staticmethod
    def _normalize_runtime_tool_configs(runtime_tool_configs: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        if not isinstance(runtime_tool_configs, dict):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for key, value in runtime_tool_configs.items():
            name = str(key or "").strip()
            if not name or not isinstance(value, dict):
                continue
            out[name] = value
        return out

    @staticmethod
    def _normalize_runtime_tools_by_agent(runtime_tools_by_agent: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        if not isinstance(runtime_tools_by_agent, dict):
            return {}
        out: Dict[str, List[str]] = {}
        for agent_name_raw, tools_raw in runtime_tools_by_agent.items():
            agent_name = str(agent_name_raw or "").strip()
            if not agent_name or not isinstance(tools_raw, list):
                continue
            seen = set()
            cleaned: List[str] = []
            for item in tools_raw:
                tool_name = str(item or "").strip()
                if not tool_name or tool_name in seen:
                    continue
                cleaned.append(tool_name)
                seen.add(tool_name)
            out[agent_name] = cleaned
        return out

    @staticmethod
    def _normalize_runtime_skills_by_agent(runtime_skills_by_agent: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        if not isinstance(runtime_skills_by_agent, dict):
            return {}
        out: Dict[str, List[str]] = {}
        for agent_name_raw, skills_raw in runtime_skills_by_agent.items():
            agent_name = str(agent_name_raw or "").strip()
            if not agent_name or not isinstance(skills_raw, list):
                continue
            seen = set()
            cleaned: List[str] = []
            for item in skills_raw:
                skill_name = str(item or "").strip()
                if not skill_name or skill_name in seen:
                    continue
                cleaned.append(skill_name)
                seen.add(skill_name)
            out[agent_name] = cleaned
        return out

    @staticmethod
    def _warn_missing_tool(tool_name: str, agent_name: str) -> None:
        if tool_name == "browser":
            logger.warning(
                "Tool 'Browser' loaded failed for agent '%s', "
                "please install the required dependency with: \n"
                "'pip install browser-use>=0.1.40' or 'pip install agentmesh-sdk[full]'\n",
                agent_name,
            )
            return
        logger.warning("Tool '%s' not found for agent '%s'\n", tool_name, agent_name)

    def create_team_from_config(
        self,
        team_name: str,
        runtime_tools: Optional[List[Any]] = None,
        runtime_tools_by_agent: Optional[Dict[str, Any]] = None,
        runtime_skills_by_agent: Optional[Dict[str, Any]] = None,
        runtime_tool_configs: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentTeam]:
        """Create a team from configuration"""
        normalized_runtime_tools = self._normalize_runtime_tools(runtime_tools)
        normalized_runtime_tools_by_agent = self._normalize_runtime_tools_by_agent(runtime_tools_by_agent)
        normalized_runtime_skills_by_agent = self._normalize_runtime_skills_by_agent(runtime_skills_by_agent)
        normalized_runtime_tool_configs = self._normalize_runtime_tool_configs(runtime_tool_configs)
        teams_config = self._get_teams_config()

        # Check if the specified team exists
        if team_name not in teams_config:
            print(f"Error: Team '{team_name}' not found in configuration.")
            return None

        # Get team configuration
        team_config = teams_config[team_name]

        # Get team's model
        team_model_name = team_config.get("model", "gpt-4o")
        team_model = self.model_factory.get_model(team_model_name)

        # Get team's max_steps
        team_max_steps = team_config.get("max_steps", 100)
        final_output_agents = team_config.get("final_output_agents", [])
        if not isinstance(final_output_agents, list):
            final_output_agents = []

        # Create team with the model
        team = AgentTeam(
            name=team_name,
            description=team_config.get("description", ""),
            rule=team_config.get("rule", ""),
            model=team_model,
            max_steps=team_max_steps,
            final_output_agents=final_output_agents
        )

        # Create and add agents to the team
        agents_config = team_config.get("agents", [])
        for agent_config in agents_config:
            # Check if agent has a specific model
            if agent_config.get("model"):
                agent_model = self.model_factory.get_model(agent_config.get("model"))
            else:
                agent_model = team_model

            # Get agent's max_steps
            agent_max_steps = agent_config.get("max_steps")

            agent = Agent(
                name=agent_config.get("name", ""),
                system_prompt=agent_config.get("system_prompt", ""),
                model=agent_model,
                description=agent_config.get("description", ""),
                max_steps=agent_max_steps
            )

            if agent.name in normalized_runtime_skills_by_agent:
                configured_skill_names = normalized_runtime_skills_by_agent.get(agent.name, [])
            else:
                configured_skill_names = self._normalize_skill_names(agent_config.get("skills", []))
            skill_specs, missing_skills = self.skill_manager.resolve_skills(configured_skill_names)
            if missing_skills:
                print(f"Warning: Skills {missing_skills} not found for agent '{agent.name}'")

            agent.skills = [spec.name for spec in skill_specs]
            agent.system_prompt = self._append_skill_prompts(agent.system_prompt, skill_specs)

            # Add tools to the agent.
            # 优先级：
            # 1) runtime_tools_by_agent[agent_name]（按智能体单独覆盖）
            # 2) runtime_tools（全体智能体统一覆盖）
            # 3) team config agent.tools（默认配置）
            agent_name = str(agent_config.get("name", "") or "")
            if agent_name in normalized_runtime_tools_by_agent:
                tool_names = normalized_runtime_tools_by_agent.get(agent_name, [])
            elif normalized_runtime_tools is None:
                tool_names = agent_config.get("tools", [])
            else:
                tool_names = normalized_runtime_tools

            merged_tool_names = self._merge_tool_names(
                [tool_name for spec in skill_specs for tool_name in spec.tools],
                tool_names,
            )

            for tool_name in merged_tool_names:
                config_override = normalized_runtime_tool_configs.get(str(tool_name or "").strip(), {})
                tool = self.tool_manager.create_tool(tool_name, config_override=config_override)
                if tool:
                    agent.add_tool(tool)
                else:
                    self._warn_missing_tool(str(tool_name or ""), agent.name)

            # Add agent to team
            team.add(agent)

        return team

    def execute_task_with_team_streaming(
        self,
        task_id: str,
        task_content: str,
        team_name: str = "general_team",
        runtime_tools: Optional[List[Any]] = None,
        runtime_tools_by_agent: Optional[Dict[str, Any]] = None,
        runtime_skills_by_agent: Optional[Dict[str, Any]] = None,
        runtime_tool_configs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a task using AgentMesh team with real streaming"""
        try:
            # Create team
            team = self.create_team_from_config(
                team_name,
                runtime_tools=runtime_tools,
                runtime_tools_by_agent=runtime_tools_by_agent,
                runtime_skills_by_agent=runtime_skills_by_agent,
                runtime_tool_configs=runtime_tool_configs,
            )
            if not team:
                self._send_task_result(task_id, "failed")
                return ""

            # Create task
            agent_task = AgentTask(content=task_content)

            # Execute task with real streaming using run_async
            # Remove signal-based timeout to avoid interfering with Ctrl+C
            return self._execute_task_with_run_async_streaming(team, agent_task, task_id)

        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
            self._send_task_result(task_id, "failed")
            return ""

    def _execute_task_with_run_async_streaming(self, team: AgentTeam, task: AgentTask, task_id: str) -> str:
        """Execute task using run_async for real streaming"""
        try:
            print(f"Starting streaming execution for task {task_id}")

            # For now, let's use the simpler synchronous approach to avoid issues
            print("Using synchronous execution for safety")
            result = team.run_async(task, output_mode="logger")
            seq = 100
            last_final: str = ""
            allowed_output_agents = set(getattr(team, "final_output_agents", set()) or set())
            saw_agent_output = False
            for agent_result in result:
                saw_agent_output = True
                agent_name = agent_result.get("agent_name") or agent_result.get("agent_id") or "agent"
                subtask = agent_result.get("subtask") or ""
                handoff = agent_result.get("handoff") or {}
                handoff_payload = handoff if isinstance(handoff, dict) else {}
                handoff_summary = str(handoff.get("handoff_summary") or handoff.get("goal") or subtask or "").strip()
                fallback_used = bool(handoff.get("fallback_used"))
                validation_status = str(handoff.get("validation_status") or ("fallback" if fallback_used else "validated"))
                next_agent_name = agent_name
                try:
                    next_agent_id = int(handoff.get("next_agent_id"))
                    if 0 <= next_agent_id < len(team.agents):
                        next_agent_name = team.agents[next_agent_id].name
                except Exception:
                    next_agent_id = None

                if handoff_summary and self.websocket_manager:
                    self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                        task_id=task_id,
                        data={
                            "seq": seq,
                            "agent": "system",
                            "phase": "handoff_generated",
                            "status": "running",
                            "content": f"已生成交接给 {next_agent_name}：{handoff_summary}",
                            "meta": {
                                "goal": handoff.get("goal"),
                                "todo_count": len(handoff.get("todo") or []),
                                "next_agent": next_agent_name,
                                "handoff_payload": handoff_payload,
                                "handoff_summary": handoff_summary,
                                "validation_status": validation_status,
                                "fallback_used": fallback_used,
                            }
                        }
                    ))
                seq += 1

                if handoff_summary and self.websocket_manager:
                    self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                        task_id=task_id,
                        data={
                            "seq": seq,
                            "agent": "system",
                            "phase": "handoff_fallback" if fallback_used else "handoff_validated",
                            "status": "error" if fallback_used else "ok",
                            "content": (
                                f"交接已回退为兼容文本：{handoff_summary}"
                                if fallback_used else
                                f"交接校验通过：{handoff_summary}"
                            ),
                            "meta": {
                                "goal": handoff.get("goal"),
                                "todo_count": len(handoff.get("todo") or []),
                                "next_agent": next_agent_name,
                                "handoff_payload": handoff_payload,
                                "handoff_summary": handoff_summary,
                                "validation_status": validation_status,
                                "fallback_used": fallback_used,
                            }
                        }
                    ))
                seq += 1

                if self.websocket_manager:
                    self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                        task_id=task_id,
                        data={
                            "seq": seq,
                            "agent": agent_name,
                            "phase": "agent_started",
                            "status": "running",
                            "content": f"{agent_name} 开始处理分配的子任务",
                            "meta": {
                                "sub_task": subtask,
                                "handoff_payload": handoff_payload,
                                "handoff_summary": handoff_summary,
                                "validation_status": validation_status,
                                "fallback_used": fallback_used,
                            }
                        }
                    ))
                seq += 10

                self._send_agent_decision(task_id, agent_result.get('agent_id'), agent_result.get('agent_name'),
                                          subtask)
                res_text = f"🤖 {agent_result.get('agent_name')}\n\n{agent_result.get('final_answer')}"
                print(res_text)
                current_answer = str(agent_result.get("final_answer") or "")
                can_emit_final = (not allowed_output_agents) or (agent_name in allowed_output_agents)
                if can_emit_final and current_answer.strip():
                    last_final = current_answer
                elif (not allowed_output_agents) and (not last_final) and current_answer.strip():
                    # Backward-compatible fallback when no final_output_agents are configured.
                    last_final = current_answer
                for action in (agent_result.get("actions") or []):
                    tool_result = action.get("tool_result") if isinstance(action, dict) else None
                    if not isinstance(tool_result, dict):
                        # Some action types do not carry tool_result payload.
                        continue
                    tool_name = tool_result.get("tool_name") or "unknown_tool"
                    tool_status = tool_result.get("status") or "unknown"
                    tool_params = tool_result.get("input_params")
                    tool_output = tool_result.get("output")

                    if self.websocket_manager:
                        self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                            task_id=task_id,
                            data={
                                "seq": seq,
                                "agent": agent_name,
                                "phase": "tool_decided",
                                "status": "running",
                                "content": f"{agent_name} 决定调用工具：{tool_name}",
                                "meta": {
                                    "tool_name": tool_name,
                                    "parameters": tool_params,
                                    "thought": action.get("thought"),
                                }
                            }
                        ))
                    seq += 1

                    self._send_tool_decision(task_id, agent_result.get("agent_name"),
                                             tool_name=tool_name,
                                             thought=action.get("thought"),
                                             parameters=tool_params)

                    self._send_tool_execute(task_id, agent_result.get("agent_name"),
                                            tool_name=tool_name,
                                            tool_result=tool_output, execution_time=0,
                                            status=tool_status)

                    if self.websocket_manager:
                        self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                            task_id=task_id,
                            data={
                                "seq": seq,
                                "agent": agent_name,
                                "phase": "tool_finished",
                                "status": "ok" if tool_status == "success" else "error",
                                "content": f"{agent_name} 工具执行完成：{tool_name}",
                                "meta": {
                                    "tool_name": tool_name,
                                    "status": tool_status,
                                }
                            }
                        ))
                    seq += 1

                # Send a simple success message
                self._send_agent_result(task_id, agent_result.get('agent_name'), agent_result.get('final_answer'))

                if self.websocket_manager:
                    self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                        task_id=task_id,
                        data={
                            "seq": seq,
                            "agent": agent_name,
                            "phase": "agent_finished",
                            "status": "ok",
                            "content": f"{agent_name} 完成子任务",
                            "meta": {
                                "sub_task": subtask,
                            }
                        }
                    ))
                seq += 10
            if not saw_agent_output or not (last_final or "").strip():
                self._send_task_result(task_id, "failed")
                print(f"Task execution finished without valid final answer for task {task_id}")
                return ""

            self._send_task_result(task_id, "success")

            print(f"Task execution completed")
            return last_final

        except Exception as e:
            print(f"Error in streaming execution: {e}")
            import traceback
            traceback.print_exc()
            self._send_task_result(task_id, "failed")
            return ""

    def _send_agent_decision(self, task_id: str, agent_id: str, agent_name: str, sub_task: str):
        """Send agent decision message"""
        if not self.websocket_manager:
            return

        message = AgentDecisionMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "agent_avatar": "",
                "sub_task": sub_task
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)

    def _send_task_result(self, task_id: str, status: str):
        """Send task completion message"""
        if not self.websocket_manager:
            return

        message = TaskResultMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "status": status
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)

    def _send_agent_thinking(self, task_id: str, agent_name: str, thought: str):
        """Send agent thinking message"""
        if not self.websocket_manager:
            return

        from ..common.models import AgentThinkingMessage

        message = AgentThinkingMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "agent_id": agent_name,
                "thought": thought
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)

    def _send_agent_result(self, task_id: str, agent_name: str, result: str):
        """Send agent result message"""
        if not self.websocket_manager:
            return

        from ..common.models import AgentResultMessage

        message = AgentResultMessage(
            task_id=task_id,
            data={
                "agent_id": agent_name,
                "result": result
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)

    def _send_tool_decision(self, task_id: str, agent_name: str, tool_name: str, thought: str, parameters: dict):
        """Send tool decision message"""
        if not self.websocket_manager:
            return

        from ..common.models import ToolDecisionMessage

        message = ToolDecisionMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "agent_id": agent_name,
                "tool_id": tool_name,
                "tool_name": tool_name,
                "thought": thought,
                "parameters": parameters
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)

    def _send_tool_execute(self, task_id: str, agent_name: str, tool_name: str, status: str,
                           execution_time: int, tool_result):
        """Send tool execution message"""
        if not self.websocket_manager:
            return

        from ..common.models import ToolExecuteMessage

        message = ToolExecuteMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "agent_id": agent_name,
                "tool_name": tool_name,
                "status": status,
                "execution_time": execution_time,
                "tool_result": tool_result
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)


# Global agent executor instance - will be initialized with websocket_manager later
agent_executor = None
