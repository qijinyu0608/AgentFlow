from typing import Union, Literal, Generator, Dict, Any, Optional, Tuple, List
import json

from agentmesh.common import LoadingIndicator
from agentmesh.common.utils import string_util
from agentmesh.common.utils.log import logger
from agentmesh.models import LLMRequest, LLMModel
from agentmesh.protocol.agent import Agent
from agentmesh.protocol.context import TeamContext
from agentmesh.protocol.handoff import HandoffEnvelope, HandoffValidationError
from agentmesh.protocol.result import TeamResult, AgentExecutionResult
from agentmesh.protocol.task import Task, TaskStatus


class AgentTeam:
    def __init__(
            self,
            name: str,
            description: str,
            rule: str = "",
            model: LLMModel = None,
            max_steps: int = 100,
            final_output_agents: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.rule = rule
        self.agents = []
        self.context = TeamContext(name, description, rule, agents=self.agents, max_steps=max_steps)
        self.model: LLMModel = model
        self.max_steps = max_steps
        self.final_output_agent_order = [str(x).strip() for x in (final_output_agents or []) if str(x).strip()]
        self.final_output_agents = set(self.final_output_agent_order)
        self.task_short_name = ""

    def add(self, agent: Agent):
        agent.team_context = self.context
        if not agent.model and self.model:
            agent.model = self.model
        self.agents.append(agent)

    def _reset_run_state(self):
        self.context.agent_outputs = []
        self.context.handoff_events = []
        self.context.current_steps = 0
        self.context.task_short_name = None
        for agent in self.agents:
            agent.clear_history()
            agent.subtask = ""
            agent.current_handoff = None

    @staticmethod
    def _call_model_json(model: LLMModel, prompt: str):
        request = LLMRequest(
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0,
            json_format=True
        )
        return model.call(request)

    def _execute_handoff_prompt(
        self,
        prompt: str,
        *,
        loading_message: str,
        output_mode: str,
        allow_stop: bool = False,
        current_agent_id: Optional[int] = None,
    ) -> Optional[HandoffEnvelope]:
        loading = None
        if output_mode == "print":
            loading = LoadingIndicator(message=loading_message, animation_type="spinner")
            loading.start()

        try:
            first_response = self._call_model_json(self.model, prompt)
            if first_response.is_error:
                logger.error("Error: %s", first_response.get_error_msg())
                return None
            first_text = first_response.data["choices"][0]["message"]["content"]
            handoff = self._parse_handoff_payload(
                first_text,
                allow_stop=allow_stop,
                current_agent_id=current_agent_id,
            )
            if handoff:
                return handoff

            retry_prompt = prompt + HANDOFF_RETRY_PROMPT.format(
                validation_error="schema validation failed or required fields were missing",
                last_response=first_text,
            )
            retry_response = self._call_model_json(self.model, retry_prompt)
            if retry_response.is_error:
                logger.error("Error: %s", retry_response.get_error_msg())
                return self._fallback_handoff_from_text(
                    first_text,
                    allow_stop=allow_stop,
                    current_agent_id=current_agent_id,
                    reason="retry request failed",
                )

            retry_text = retry_response.data["choices"][0]["message"]["content"]
            handoff = self._parse_handoff_payload(
                retry_text,
                allow_stop=allow_stop,
                current_agent_id=current_agent_id,
            )
            if handoff:
                return handoff

            return self._fallback_handoff_from_text(
                retry_text or first_text,
                allow_stop=allow_stop,
                current_agent_id=current_agent_id,
                reason="handoff validation failed twice",
            )
        finally:
            if loading:
                loading.stop()

    def _parse_handoff_payload(
        self,
        reply_text: str,
        *,
        allow_stop: bool = False,
        current_agent_id: Optional[int] = None,
    ) -> Optional[HandoffEnvelope]:
        try:
            decision_res = string_util.json_loads(reply_text)
            handoff = HandoffEnvelope.from_payload(
                decision_res,
                allow_stop=allow_stop,
                current_agent_id=current_agent_id,
                valid_agent_ids=list(range(len(self.agents))),
                task_short_name=decision_res.get("task_short_name"),
            )
            if handoff.task_short_name:
                self.context.task_short_name = handoff.task_short_name
            return handoff
        except (json.JSONDecodeError, HandoffValidationError, ValueError) as e:
            logger.warning("Failed to parse handoff payload: %s", e)
            return None

    def _fallback_handoff_from_text(
        self,
        reply_text: str,
        *,
        allow_stop: bool = False,
        current_agent_id: Optional[int] = None,
        reason: str = "",
    ) -> Optional[HandoffEnvelope]:
        try:
            payload = string_util.json_loads(reply_text)
        except Exception:
            return None

        raw_next_agent_id = payload.get("next_agent_id", payload.get("id"))
        try:
            next_agent_id = int(raw_next_agent_id)
        except Exception:
            return None

        if next_agent_id < 0:
            if allow_stop and next_agent_id == -1:
                return HandoffEnvelope(
                    next_agent_id=-1,
                    goal="",
                    done=[],
                    todo=[],
                    notes=reason,
                    handoff_summary=str(payload.get("handoff_summary") or "").strip(),
                    legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
                    task_short_name=payload.get("task_short_name"),
                    raw_payload=payload,
                    validation_status="fallback",
                    fallback_used=True,
                )
            return None

        if next_agent_id >= len(self.agents):
            return None
        if current_agent_id is not None and next_agent_id == current_agent_id:
            return None

        handoff = HandoffEnvelope.fallback(
            next_agent_id=next_agent_id,
            legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
            task_short_name=payload.get("task_short_name"),
            reason=reason,
        )
        if handoff.task_short_name:
            self.context.task_short_name = handoff.task_short_name
        return handoff

    @staticmethod
    def _apply_handoff_to_agent(agent: Agent, handoff: HandoffEnvelope):
        agent.current_handoff = handoff
        agent.subtask = handoff.subtask

    def run(self, task: Union[str, Task], output_mode: Literal["print", "logger"] = "logger") -> TeamResult:
        self.context.output_mode = output_mode

        def output(message, end="\n"):
            if output_mode == "print":
                print(message, end=end)
            elif message:
                logger.info(message.strip())

        if isinstance(task, str):
            task = Task(content=task)

        self._reset_run_state()
        task.update_status(TaskStatus.PROCESSING)

        result = TeamResult(team_name=self.name, task=task)
        self.context.user_task = task.get_text()
        self.context.task = task
        self.context.model = self.model

        output("")
        output(f"Team {self.name} received the task and started processing")
        output("")

        try:
            selected_agent, selected_agent_id, handoff = self._select_initial_agent(task, output_mode)
            if selected_agent is None or handoff is None:
                result.complete("failed")
                return result

            selected_agent.output_mode = output_mode
            total_steps_used = 0

            agent_results = self._process_agent_chain(
                selected_agent,
                selected_agent_id,
                handoff,
                total_steps_used,
                output,
                stream=False
            )

            for agent_result in agent_results:
                result.add_agent_result(agent_result)

            task.update_status(TaskStatus.COMPLETED)
            result.final_output = self._select_final_output(result)
            result.complete("completed")
            output(f"\nTeam {self.name} completed the task")
            self.cleanup()
            return result

        except Exception as e:
            import traceback
            logger.error(f"Error during team execution: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            self.cleanup()
            result.complete("failed")
            return result

    def run_async(self, task: Union[str, Task], output_mode: Literal["print", "logger"] = "logger") -> \
            Generator[Dict[str, Any], None, TeamResult]:
        self.context.output_mode = output_mode

        def output(message, end="\n"):
            if output_mode == "print":
                print(message, end=end)
            elif message:
                logger.info(message.strip())

        if isinstance(task, str):
            task = Task(content=task)

        self._reset_run_state()
        task.update_status(TaskStatus.PROCESSING)

        result = TeamResult(team_name=self.name, task=task)
        self.context.user_task = task.get_text()
        self.context.task = task
        self.context.model = self.model

        output("")
        output(f"Team {self.name} received the task and started processing")
        output("")

        try:
            selected_agent, selected_agent_id, handoff = self._select_initial_agent(task, output_mode)
            if selected_agent is None or handoff is None:
                result.complete("failed")
                return result

            selected_agent.output_mode = output_mode
            total_steps_used = 0

            agent_result = AgentExecutionResult(
                agent_id=str(selected_agent_id),
                agent_name=selected_agent.name,
                subtask=handoff.subtask,
                handoff=handoff.to_dict(),
            )

            step_result = selected_agent.step()
            final_answer = step_result.final_answer
            step_count = step_result.step_count
            total_steps_used += step_count
            agent_result.final_answer = final_answer if final_answer else ""

            if hasattr(selected_agent, 'captured_actions') and selected_agent.captured_actions:
                for action in selected_agent.captured_actions:
                    agent_result.add_action(action)

            agent_result.complete()
            result.add_agent_result(agent_result)
            yield agent_result.to_dict()

            current_agent = selected_agent
            current_agent_id = selected_agent_id
            while True:
                if total_steps_used >= self.max_steps:
                    output(f"\nReached maximum total steps ({self.max_steps}). Stopping execution.")
                    break

                next_handoff = current_agent.should_invoke_next_agent(current_agent_id=current_agent_id)
                next_handoff = self._ensure_final_output_handoff(
                    next_handoff=next_handoff,
                    current_agent_id=current_agent_id,
                    agent_results=result.agent_results,
                )
                if next_handoff is None or next_handoff.next_agent_id < 0:
                    break

                next_agent_id = next_handoff.next_agent_id
                if next_agent_id >= len(self.agents):
                    break

                next_agent = self.agents[next_agent_id]
                self._apply_handoff_to_agent(next_agent, next_handoff)
                next_agent.output_mode = current_agent.output_mode

                next_agent_result = AgentExecutionResult(
                    agent_id=str(next_agent_id),
                    agent_name=next_agent.name,
                    subtask=next_handoff.subtask,
                    handoff=next_handoff.to_dict(),
                )

                step_result = next_agent.step()
                next_final_answer = step_result.final_answer
                step_count = step_result.step_count
                total_steps_used += step_count
                next_agent_result.final_answer = next_final_answer if next_final_answer else ""

                if hasattr(next_agent, 'captured_actions') and next_agent.captured_actions:
                    for action in next_agent.captured_actions:
                        next_agent_result.add_action(action)

                next_agent_result.complete()
                result.add_agent_result(next_agent_result)
                yield next_agent_result.to_dict()

                current_agent = next_agent
                current_agent_id = next_agent_id

            task.update_status(TaskStatus.COMPLETED)
            result.final_output = self._select_final_output(result)
            result.complete("completed")
            output(f"\nTeam {self.name} completed the task")
            self.cleanup()
            return result

        except Exception as e:
            import traceback
            logger.error(f"Error during team execution: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            self.cleanup()
            result.complete("failed")
            return result

    def _select_initial_agent(self, task: Task, output_mode: str) -> Tuple[
        Optional[Agent], Optional[int], Optional[HandoffEnvelope]]:
        agents_str = ', '.join(
            f'{{"id": {i}, "name": "{agent.name}", "description": "{agent.description}", "system_prompt": "{agent.system_prompt}"}}'
            for i, agent in enumerate(self.agents)
        )

        prompt = GROUP_DECISION_PROMPT.format(
            group_name=self.name,
            group_description=self.description,
            group_rules=self.rule,
            agents_str=agents_str,
            user_task=task.get_text()
        )

        handoff = self._execute_handoff_prompt(
            prompt,
            loading_message="Select an agent in the team...",
            output_mode=output_mode,
            allow_stop=False,
            current_agent_id=None,
        )
        if handoff is None:
            return None, None, None

        selected_agent_id = handoff.next_agent_id
        try:
            selected_agent = self.agents[selected_agent_id]
        except (IndexError, TypeError):
            logger.error("Invalid selected agent id: %s", selected_agent_id)
            return None, None, None

        self._apply_handoff_to_agent(selected_agent, handoff)
        return selected_agent, selected_agent_id, handoff

    def _process_agent_chain(
        self,
        initial_agent: Agent,
        initial_agent_id: int,
        initial_handoff: HandoffEnvelope,
        total_steps_used: int,
        output_func,
        stream: bool = False
    ) -> List[AgentExecutionResult]:
        agent_results = []

        agent_result = AgentExecutionResult(
            agent_id=str(initial_agent_id),
            agent_name=initial_agent.name,
            subtask=initial_handoff.subtask,
            handoff=initial_handoff.to_dict(),
        )

        step_result = initial_agent.step()
        final_answer = step_result.final_answer
        step_count = step_result.step_count
        total_steps_used += step_count
        agent_result.final_answer = final_answer if final_answer else ""

        if hasattr(initial_agent, 'captured_actions') and initial_agent.captured_actions:
            for action in initial_agent.captured_actions:
                agent_result.add_action(action)

        agent_result.complete()
        agent_results.append(agent_result)

        current_agent = initial_agent
        current_agent_id = initial_agent_id
        while True:
            if total_steps_used >= self.max_steps:
                output_func(f"\nReached maximum total steps ({self.max_steps}). Stopping execution.")
                break

            next_handoff = current_agent.should_invoke_next_agent(current_agent_id=current_agent_id)
            next_handoff = self._ensure_final_output_handoff(
                next_handoff=next_handoff,
                current_agent_id=current_agent_id,
                agent_results=agent_results,
            )
            if next_handoff is None or next_handoff.next_agent_id < 0:
                break

            next_agent_id = next_handoff.next_agent_id
            if next_agent_id >= len(self.agents):
                break

            next_agent = self.agents[next_agent_id]
            self._apply_handoff_to_agent(next_agent, next_handoff)
            next_agent.output_mode = current_agent.output_mode

            next_agent_result = AgentExecutionResult(
                agent_id=str(next_agent_id),
                agent_name=next_agent.name,
                subtask=next_handoff.subtask,
                handoff=next_handoff.to_dict(),
            )

            step_result = next_agent.step()
            next_final_answer = step_result.final_answer
            step_count = step_result.step_count
            total_steps_used += step_count
            next_agent_result.final_answer = next_final_answer if next_final_answer else ""

            if hasattr(next_agent, 'captured_actions') and next_agent.captured_actions:
                for action in next_agent.captured_actions:
                    next_agent_result.add_action(action)

            next_agent_result.complete()
            agent_results.append(next_agent_result)
            current_agent = next_agent
            current_agent_id = next_agent_id

        return agent_results

    def _pick_final_output_agent_id(self, current_agent_id: int) -> Optional[int]:
        if not self.final_output_agent_order:
            return None

        for agent_name in self.final_output_agent_order:
            for idx, agent in enumerate(self.agents):
                if agent.name == agent_name and idx != current_agent_id:
                    return idx
        return None

    def _has_final_output_agent_result(self, agent_results: List[AgentExecutionResult]) -> bool:
        if not self.final_output_agents:
            return False
        for agent_result in agent_results:
            if (
                agent_result.agent_name in self.final_output_agents
                and (agent_result.final_answer or "").strip()
            ):
                return True
        return False

    def _build_forced_final_output_handoff(
        self,
        target_agent_id: int,
        agent_results: List[AgentExecutionResult],
    ) -> HandoffEnvelope:
        done_members = [f"{item.agent_name} 已完成其阶段产出" for item in agent_results if item.agent_name]
        return HandoffEnvelope(
            next_agent_id=target_agent_id,
            goal="输出面向用户的最终汇总答案",
            done=done_members,
            todo=[
                "阅读并整合所有已完成成员的输出",
                "统一术语与结论，消除冲突",
                "给出结构化最终答复（以最终结论为主）",
            ],
            notes=(
                "系统强制执行最终汇总阶段：团队配置了 final_output_agents，"
                "但当前尚未由指定成员产出可用最终答案。"
            ),
            handoff_summary="系统触发最终汇总代理补齐流程",
            legacy_subtask="请基于所有已有输出，生成最终汇总后的用户答案。",
            validation_status="forced_final_output",
            fallback_used=True,
        )

    def _ensure_final_output_handoff(
        self,
        *,
        next_handoff: Optional[HandoffEnvelope],
        current_agent_id: int,
        agent_results: List[AgentExecutionResult],
    ) -> Optional[HandoffEnvelope]:
        if not self.final_output_agents:
            return next_handoff

        if next_handoff is not None and next_handoff.next_agent_id >= 0:
            return next_handoff

        if self._has_final_output_agent_result(agent_results):
            return next_handoff

        forced_agent_id = self._pick_final_output_agent_id(current_agent_id=current_agent_id)
        if forced_agent_id is None:
            return next_handoff
        return self._build_forced_final_output_handoff(
            target_agent_id=forced_agent_id,
            agent_results=agent_results,
        )

    def cleanup(self):
        for agent in self.agents:
            if hasattr(agent, 'tools'):
                for tool in agent.tools:
                    try:
                        tool.close()
                    except Exception as e:
                        logger.warning(f"Error closing tool {tool.name}: {str(e)}")

    def _select_final_output(self, result: TeamResult) -> str:
        if not result.agent_results:
            return ""

        if self.final_output_agents:
            for agent_result in reversed(result.agent_results):
                if (
                        agent_result.agent_name in self.final_output_agents
                        and (agent_result.final_answer or "").strip()
                ):
                    return agent_result.final_answer
            # In teams that explicitly set final_output_agents, do not fallback to
            # intermediate outputs from non-designated members.
            return ""

        for agent_result in reversed(result.agent_results):
            if (agent_result.final_answer or "").strip():
                return agent_result.final_answer

        return ""


GROUP_DECISION_PROMPT = """## Role
You are the coordinator for a team of AI agents. Your job is to analyze the user's task, choose the most suitable first member, and produce a semi-structured handoff payload for that member.

## Team Information
Team name: {group_name}
Team description: {group_description}
Team rules: {group_rules}

## Available Agents
{agents_str}

## User Task
{user_task}

## Output Format
Return your response in JSON format with the following fields:
- next_agent_id: The ID of the selected agent
- goal: The core objective this member should handle first (same language as the user)
- done: A list of already-known progress items, can be empty
- todo: A list of concrete next actions for the selected member, must contain at least one item
- notes: Flexible natural language notes with important context, constraints, tone, or nuances
- handoff_summary: A short summary for logs and UI
- legacy_subtask: A backward-compatible natural language subtask preserving key original details
- task_short_name: A descriptive name for the user's original task (lowercase with underscores, max 5 English words)

Please return only JSON that can be parsed directly by json.loads(), no extra content:
{{"next_agent_id": 0, "goal": "", "done": [], "todo": [""], "notes": "", "handoff_summary": "", "legacy_subtask": "", "task_short_name": ""}}"""


HANDOFF_RETRY_PROMPT = """

## Validation Error
The previous JSON handoff was invalid.
Error:
{validation_error}

Previous response:
{last_response}

Please return corrected JSON only. Keep the same intent, but make sure the payload satisfies the schema exactly."""
