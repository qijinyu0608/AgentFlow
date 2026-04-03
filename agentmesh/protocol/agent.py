import json
import time
from typing import Optional

from agentmesh.common import LoadingIndicator
from agentmesh.common.utils import string_util
from agentmesh.common.utils.log import logger
from agentmesh.models import LLMRequest, LLMModel
from agentmesh.protocol.agent_stream import AgentStreamExecutor
from agentmesh.protocol.context import TeamContext, AgentOutput
from agentmesh.protocol.handoff import HandoffEnvelope, HandoffValidationError
from agentmesh.protocol.result import AgentAction, AgentActionType, ToolResult, AgentResult
from agentmesh.tools.base_tool import BaseTool
from agentmesh.tools.base_tool import ToolStage


class Agent:
    def __init__(self, name: str, system_prompt: str, description: str, model: LLMModel = None, team_context=None,
                 tools=None, output_mode="print", max_steps=100, max_context_tokens=None, context_reserve_tokens=None,
                 memory_manager=None):
        self.name = name
        self.system_prompt = system_prompt
        self.model: LLMModel = model
        self.description = description
        self.team_context: TeamContext = team_context
        self.subtask: str = ""
        self.current_handoff: Optional[HandoffEnvelope] = None
        self.tools: list = []
        self.skills: list = []
        self.max_steps = max_steps
        self.max_context_tokens = max_context_tokens
        self.context_reserve_tokens = context_reserve_tokens
        self.conversation_history = []
        self.action_history = []
        self.captured_actions = []
        self.ext_data = ""
        self.output_mode = output_mode
        self.last_usage = None
        self.messages = []
        self.memory_manager = memory_manager
        if tools:
            for tool in tools:
                self.add_tool(tool)

    def add_tool(self, tool: BaseTool):
        tool.model = self.model
        self.tools.append(tool)

    def _get_model_context_window(self) -> int:
        if self.model and hasattr(self.model, 'model'):
            model_name = self.model.model.lower()
            if 'claude-3' in model_name or 'claude-sonnet' in model_name:
                return 200000
            elif 'gpt-4' in model_name:
                if 'turbo' in model_name or '128k' in model_name:
                    return 128000
                elif '32k' in model_name:
                    return 32000
                else:
                    return 8000
            elif 'gpt-3.5' in model_name:
                if '16k' in model_name:
                    return 16000
                else:
                    return 4000
            elif 'deepseek' in model_name:
                return 64000
        return 10000

    def _get_context_reserve_tokens(self) -> int:
        if self.context_reserve_tokens is not None:
            return self.context_reserve_tokens
        context_window = self._get_model_context_window()
        return max(4000, int(context_window * 0.2))

    def _estimate_message_tokens(self, message: dict) -> int:
        content = message.get('content', '')
        if isinstance(content, str):
            return max(1, len(content) // 4)
        elif isinstance(content, list):
            total_chars = 0
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    total_chars += len(part.get('text', ''))
                elif isinstance(part, dict) and part.get('type') == 'image':
                    total_chars += 4800
            return max(1, total_chars // 4)
        return 1

    def _calculate_context_tokens(self) -> int:
        if not self.conversation_history:
            return 0
        if self.last_usage:
            return self.last_usage.get('prompt_tokens', 0) + self.last_usage.get('completion_tokens', 0)
        total_tokens = 0
        for msg in self.conversation_history:
            total_tokens += self._estimate_message_tokens(msg)
        return total_tokens

    def _trim_conversation_history(self):
        if not self.conversation_history:
            return

        context_window = self._get_model_context_window()
        reserve_tokens = self._get_context_reserve_tokens()
        max_tokens = context_window - reserve_tokens
        current_tokens = self._calculate_context_tokens()
        if current_tokens <= max_tokens:
            return

        system_messages = []
        other_messages = []
        for msg in self.conversation_history:
            if msg.get('role') == 'system':
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        system_tokens = sum(self._estimate_message_tokens(msg) for msg in system_messages)
        available_tokens = max_tokens - system_tokens
        kept_messages = []
        accumulated_tokens = 0

        for msg in reversed(other_messages):
            msg_tokens = self._estimate_message_tokens(msg)
            if accumulated_tokens + msg_tokens <= available_tokens:
                kept_messages.insert(0, msg)
                accumulated_tokens += msg_tokens
            else:
                break

        old_count = len(self.conversation_history)
        self.conversation_history = system_messages + kept_messages
        new_count = len(self.conversation_history)
        if old_count > new_count:
            logger.info(
                f"Context trimmed: {old_count} -> {new_count} messages "
                f"(~{current_tokens} -> ~{system_tokens + accumulated_tokens} tokens, "
                f"limit: {max_tokens})"
            )

    def _build_task_prompt(self) -> str:
        if not self.team_context:
            return self.subtask

        timestamp = time.time()
        local_time = time.localtime(timestamp)
        formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        ext_data_prompt = self.ext_data if self.ext_data else ""
        handoff_prompt = self.current_handoff.render_for_prompt() if self.current_handoff else ""

        prompt = f"""## Role
Your role: {self.name}
Your role description: {self.description}
You are handling the subtask as a member of the {self.team_context.name} team. Please answer in the same language as the user's original task.

## Current task context:
Current time: {formatted_time}
Team description: {self.team_context.description}

## Other agents output:
{self._fetch_agents_outputs()}

{handoff_prompt}

{ext_data_prompt}

## Your sub task
{self.subtask}"""

        return prompt

    def _find_tool(self, tool_name: str):
        for tool in self.tools:
            if tool.name == tool_name:
                if tool.stage == ToolStage.PRE_PROCESS:
                    tool.model = self.model
                    tool.context = self
                    return tool
                else:
                    logger.warning(f"Tool {tool_name} is a post-process tool and cannot be called directly.")
                    return None
        return None

    def output(self, message="", end="\n"):
        if self.output_mode == "print":
            print(message, end=end)
        elif message:
            logger.info(message)

    def step(self):
        self.final_answer = ""
        self.captured_actions = []

        self.output(f"🤖 {self.name.strip()}: {self.subtask}")
        task_prompt = self._build_task_prompt()

        def step_event_handler(event):
            event_type = event["type"]
            data = event.get("data", {})

            if event_type == "turn_start":
                turn = data.get('turn', 0)
                if self.team_context and self.team_context.current_steps >= self.team_context.max_steps:
                    logger.warning(f"Team's max steps ({self.team_context.max_steps}) reached.")
                    raise Exception("Team's max steps reached")

                if self.team_context:
                    self.team_context.current_steps += 1

                if self.output_mode == "print":
                    print(f"\nStep {turn}:")

            elif event_type == "message_update":
                if self.output_mode == "print":
                    print(data.get("delta", ""), end="", flush=True)

            elif event_type == "tool_execution_start":
                tool_name = data.get('tool_name')
                args = data.get('arguments', {})
                if self.output_mode == "print":
                    print(f"\n🛠️ {tool_name}: {json.dumps(args, ensure_ascii=False)}")
                else:
                    logger.info(f"🛠️ {tool_name}: {json.dumps(args, ensure_ascii=False)}")

            elif event_type == "tool_execution_end":
                status = data.get('status')
                result = data.get('result')
                if status == "error":
                    logger.error(f"Tool execution error: {result}")

            elif event_type == "error":
                logger.error(f"Error: {data.get('error')}")

        try:
            final_answer = self.run_stream(
                user_message=task_prompt,
                on_event=step_event_handler,
                clear_history=True
            )

            self.final_answer = final_answer
            if self.team_context:
                self.team_context.agent_outputs.append(
                    AgentOutput(
                        agent_name=self.name,
                        output=final_answer,
                        handoff=self.current_handoff.to_dict() if self.current_handoff else None,
                    )
                )

            self._execute_post_process_tools()
            step_count = len([a for a in self.captured_actions if a.action_type == AgentActionType.TOOL_USE])
            return AgentResult.success(final_answer=final_answer, step_count=step_count)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Step execution error: {error_msg}")
            return AgentResult.error(error_msg, 0)

    def _execute_post_process_tools(self):
        post_process_tools = [tool for tool in self.tools if tool.stage == ToolStage.POST_PROCESS]

        for tool in post_process_tools:
            tool.context = self
            start_time = time.time()
            result = tool.execute({})
            execution_time = time.time() - start_time

            self.capture_tool_use(
                tool_name=tool.name,
                input_params={},
                output=result.result,
                status=result.status,
                error_message=str(result.result) if result.status == "error" else None,
                execution_time=execution_time
            )

            if result.status == "success":
                self.output(f"\n🛠️ {tool.name}: {json.dumps(result.result)}")
            else:
                self.output(f"\n🛠️ {tool.name}: {json.dumps({'status': 'error', 'message': str(result.result)})}")

    @staticmethod
    def _call_model_json(model_to_use: LLMModel, prompt: str):
        request = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            json_format=True
        )
        return model_to_use.call(request)

    def _parse_next_handoff(
        self,
        decision_text: str,
        *,
        current_agent_id: int,
        allow_stop: bool = True,
    ) -> Optional[HandoffEnvelope]:
        try:
            decision_res = string_util.json_loads(decision_text)
            return HandoffEnvelope.from_payload(
                decision_res,
                allow_stop=allow_stop,
                current_agent_id=current_agent_id,
                valid_agent_ids=list(range(len(self.team_context.agents))),
            )
        except (json.JSONDecodeError, HandoffValidationError, ValueError) as e:
            logger.warning("Failed to determine next handoff: %s", e)
            return None

    def _fallback_next_handoff(
        self,
        decision_text: str,
        *,
        current_agent_id: int,
        reason: str = "",
    ) -> Optional[HandoffEnvelope]:
        try:
            payload = string_util.json_loads(decision_text)
        except Exception:
            return None

        raw_next_agent_id = payload.get("next_agent_id", payload.get("id"))
        try:
            next_agent_id = int(raw_next_agent_id)
        except Exception:
            return None

        if next_agent_id < 0:
            return HandoffEnvelope(
                next_agent_id=-1,
                goal="",
                done=[],
                todo=[],
                notes=reason,
                handoff_summary=str(payload.get("handoff_summary") or "").strip(),
                legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
                raw_payload=payload,
                validation_status="fallback",
                fallback_used=True,
            )

        if next_agent_id >= len(self.team_context.agents) or next_agent_id == current_agent_id:
            return None

        return HandoffEnvelope.fallback(
            next_agent_id=next_agent_id,
            legacy_subtask=str(payload.get("legacy_subtask") or payload.get("subtask") or "").strip(),
            reason=reason,
        )

    def should_invoke_next_agent(self, current_agent_id: int) -> Optional[HandoffEnvelope]:
        model_to_use = self.team_context.model
        agents_str = ', '.join(
            f'{{"id": {i}, "name": "{agent.name}", "description": "{agent.description}", "system_prompt": "{agent.system_prompt}"}}'
            for i, agent in enumerate(self.team_context.agents)
            if i != current_agent_id
        )

        if not agents_str:
            return None

        agent_outputs_list = self._fetch_agents_outputs()
        prompt = AGENT_DECISION_PROMPT.format(
            group_name=self.team_context.name,
            group_description=self.team_context.description,
            current_agent_name=self.name,
            group_rules=self.team_context.rule,
            agent_outputs_list=agent_outputs_list,
            agents_str=agents_str,
            user_task=self.team_context.user_task
        )

        loading = None
        if self.output_mode == "print":
            self.output()
            loading = LoadingIndicator(message="Select agent in team...", animation_type="spinner")
            loading.start()

        try:
            response = self._call_model_json(model_to_use, prompt)
            if response.is_error:
                logger.error(f"Error: {response.get_error_msg()}")
                return None

            decision_text = response.data["choices"][0]["message"]["content"]
            handoff = self._parse_next_handoff(
                decision_text,
                current_agent_id=current_agent_id,
                allow_stop=True,
            )
            if handoff is not None:
                return handoff

            retry_prompt = prompt + HANDOFF_RETRY_PROMPT.format(
                validation_error="schema validation failed or required fields were missing",
                last_response=decision_text,
            )
            retry_response = self._call_model_json(model_to_use, retry_prompt)
            if retry_response.is_error:
                logger.error(f"Error: {retry_response.get_error_msg()}")
                return self._fallback_next_handoff(
                    decision_text,
                    current_agent_id=current_agent_id,
                    reason="retry request failed",
                )

            retry_text = retry_response.data["choices"][0]["message"]["content"]
            handoff = self._parse_next_handoff(
                retry_text,
                current_agent_id=current_agent_id,
                allow_stop=True,
            )
            if handoff is not None:
                return handoff

            return self._fallback_next_handoff(
                retry_text or decision_text,
                current_agent_id=current_agent_id,
                reason="handoff validation failed twice",
            )
        finally:
            if loading:
                loading.stop()
                if self.output_mode == "print":
                    print()

    def _fetch_agents_outputs(self) -> str:
        agent_outputs_list = []
        for agent_output in self.team_context.agent_outputs:
            handoff_summary = ""
            if getattr(agent_output, "handoff", None):
                summary = str((agent_output.handoff or {}).get("handoff_summary") or "").strip()
                if summary:
                    handoff_summary = f"handoff summary: {summary}\n"
            agent_outputs_list.append(
                f"member name: {agent_output.agent_name}\n"
                f"{handoff_summary}"
                f"output content: {agent_output.output}\n\n"
            )
        return "\n".join(agent_outputs_list)

    def capture_tool_use(self, tool_name, input_params, output, status, thought=None, error_message=None,
                         execution_time=0.0):
        tool_result = ToolResult(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            status=status,
            error_message=error_message,
            execution_time=execution_time
        )

        action = AgentAction(
            agent_id=self.id if hasattr(self, 'id') else str(id(self)),
            agent_name=self.name,
            action_type=AgentActionType.TOOL_USE,
            tool_result=tool_result,
            thought=thought
        )

        self.captured_actions.append(action)
        return action

    def run_stream(self, user_message: str, on_event=None, clear_history: bool = False) -> str:
        if clear_history:
            self.messages = []

        model_to_use = self.model if self.model else self.team_context.model if self.team_context else None
        if not model_to_use:
            raise ValueError("No model available for agent")

        executor = AgentStreamExecutor(
            agent=self,
            model=model_to_use,
            system_prompt=self.system_prompt,
            tools=self.tools,
            max_turns=self.max_steps,
            on_event=on_event,
            messages=self.messages
        )

        response = executor.run_stream(user_message)
        self.messages = executor.messages
        return response

    def clear_history(self):
        self.messages = []
        self.captured_actions = []
        self.conversation_history = []
        self.action_history = []
        self.current_handoff = None


AGENT_REPLY_PROMPT = """You are part of the team, you only need to reply the part of user question related to your responsibilities

## Team
Team Name: {group_name}
Team Description: {group_description}
Team Rules: {group_rules}
Your Role: {current_agent_name}

## Team members have already output
{agent_outputs_list}

User Original Task: 
{user_task}

Your Subtask:
{subtask}"""


AGENT_DECISION_PROMPT = """## Role
You are a team decision expert. Decide whether another member is needed to complete the user task. If another member is needed, select the most suitable member and produce a semi-structured handoff payload. If not, return {{"next_agent_id": -1}} directly.

## Team
Team Name: {group_name}
Team Description: {group_description}
Team Rules: {group_rules}

## Current Member
Current member name: {current_agent_name}

## List of available members:
{agents_str}

## Members have replied
{agent_outputs_list}

## Attention
1. Decide whether another member is still needed based on the user's task, the team rules, and the outputs that already exist.
2. If the current outputs are enough, return {{"next_agent_id": -1}} immediately.
3. If another member is needed, return JSON with these fields:
   - next_agent_id
   - goal
   - done
   - todo
   - notes
   - handoff_summary
   - legacy_subtask
4. Always reply in JSON that can be parsed directly by json.loads().
5. Use the same language as the user's task for goal, todo, notes, handoff_summary, and legacy_subtask.

## User Original Task:
{user_task}"""


HANDOFF_RETRY_PROMPT = """

## Validation Error
The previous JSON handoff was invalid.
Error:
{validation_error}

Previous response:
{last_response}

Please return corrected JSON only. Keep the same intent, but make sure the payload satisfies the schema exactly."""
