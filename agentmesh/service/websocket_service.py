import uuid
import json
import threading
import signal
import sys
from datetime import datetime
from typing import Dict, Set, Optional, Any

from ..common.models import (
    Task, TaskStatus, WebSocketMessage, TaskSubmitResponse, TaskResultMessage,
    WorkflowEventMessage
)
from ..service.task_service import task_service
from ..service.agent_executor import AgentExecutor
from ..service.workflow_event_store import workflow_event_store
from ..service.conversation_service import conversation_service
from ..service.context_builder import context_builder
from ..common.database import conversation_db_manager


class ThreadManager:
    """Thread manager for tracking and cleaning up threads"""
    
    def __init__(self):
        self.active_threads: Set[threading.Thread] = set()
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.shutdown()
    
    def add_thread(self, thread: threading.Thread):
        """Add a thread to tracking"""
        with self.lock:
            self.active_threads.add(thread)
    
    def remove_thread(self, thread: threading.Thread):
        """Remove a thread from tracking"""
        with self.lock:
            self.active_threads.discard(thread)
    
    def shutdown(self):
        """Gracefully shutdown all threads"""
        print("Shutting down thread manager...")
        self.shutdown_event.set()
        
        # Wait for all threads to complete (with timeout)
        with self.lock:
            threads_to_wait = list(self.active_threads)
        
        for thread in threads_to_wait:
            if thread.is_alive():
                print(f"Waiting for thread {thread.name} to complete...")
                thread.join(timeout=5.0)  # 5 second timeout
                if thread.is_alive():
                    print(f"Thread {thread.name} did not complete within timeout")
        
        print("Thread manager shutdown complete")


# Global thread manager
thread_manager = ThreadManager()


class WebSocketManager:
    """WebSocket connection manager for any WebSocket implementation"""
    
    def __init__(self):
        self.active_connections: Dict[str, Any] = {}
        self.task_connections: Dict[str, Set[str]] = {}  # task_id -> set of connection_ids
        self.connections_lock = threading.Lock()  # For active_connections
        self.task_lock = threading.Lock()  # For task_connections
        self.shutdown_event = threading.Event()
    
    def connect(self, websocket: Any, connection_id: str):
        """Connect a new WebSocket client"""
        with self.connections_lock:
            self.active_connections[connection_id] = websocket
            print(f"Connection {connection_id} added. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, connection_id: str):
        """Disconnect a WebSocket client"""
        # Remove from active connections
        with self.connections_lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
        
        # Remove from task connections
        with self.task_lock:
            # iterate on a snapshot to avoid "dict changed size during iteration"
            for task_id, connections in list(self.task_connections.items()):
                if connection_id in connections:
                    connections.remove(connection_id)
                    if not connections:
                        del self.task_connections[task_id]
    
    def subscribe_to_task(self, connection_id: str, task_id: str):
        """Subscribe a connection to a specific task"""
        with self.task_lock:
            if task_id not in self.task_connections:
                self.task_connections[task_id] = set()
            self.task_connections[task_id].add(connection_id)
    
    def send_message(self, connection_id: str, message: WebSocketMessage):
        """Send message to a specific connection"""
        # Get connection safely
        connection = None
        with self.connections_lock:
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
        
        # Send message outside of lock
        if connection:
            try:
                connection.send(message.model_dump_json())
            except Exception as e:
                print(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    def broadcast_to_task(self, task_id: str, message: WebSocketMessage):
        """Broadcast message to all connections subscribed to a task"""
        # Persist workflow events for replay/metrics
        try:
            if getattr(message, "event", None) == "workflow_event":
                workflow_event_store.append_event(task_id=task_id, timestamp_iso=getattr(message, "timestamp", None), data=getattr(message, "data", None))
        except Exception as e:
            print(f"Error persisting workflow_event for task {task_id}: {e}")

        # Get connections to broadcast to (outside of lock)
        connections_to_broadcast = []
        with self.task_lock:
            if task_id in self.task_connections:
                connections_to_broadcast = list(self.task_connections[task_id])
        
        # Send messages to each connection (outside of lock)
        for connection_id in connections_to_broadcast:
            self.send_message(connection_id, message)
    
    def shutdown(self):
        """Gracefully shutdown all connections"""
        print("Shutting down WebSocket manager...")
        self.shutdown_event.set()
        
        # Close all active connections
        with self.connections_lock:
            connections_to_close = list(self.active_connections.keys())
        
        for connection_id in connections_to_close:
            try:
                self.disconnect(connection_id)
            except Exception as e:
                print(f"Error closing connection {connection_id}: {e}")
        
        print("WebSocket manager shutdown complete")


class TaskProcessor:
    """Task processor for handling task execution with real AgentMesh streaming"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.agent_executor = AgentExecutor(websocket_manager)
        self._task_conversation_map: Dict[str, str] = {}
    
    def process_user_input(self, connection_id: str, user_input: dict) -> str:
        """Process user input and create task"""
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create task in database
        task = Task(
            task_id=task_id,
            task_status=TaskStatus.RUNNING,
            task_name=user_input.get("text", "New Task")[:50],  # Truncate if too long
            task_content=user_input.get("text", ""),
            submit_time=datetime.now()
        )
        
        # Save task to database
        success = task_service.create_task(task)
        if not success:
            raise Exception("Failed to create task")
        
        # Subscribe connection to task
        self.websocket_manager.subscribe_to_task(connection_id, task_id)

        # Ensure conversation exists (or create one)
        conversation_id = user_input.get("conversation_id")
        requested_conversation_id = conversation_id
        conversation_recreated = False
        if conversation_id:
            conv = conversation_service.get_conversation(conversation_id)
            if not conv:
                print(
                    f"Conversation {conversation_id} not found, creating a new conversation for task {task_id}"
                )
                conversation_id = conversation_service.create_conversation(title=str(user_input.get("text", ""))[:50] or None)
                conversation_recreated = True
        else:
            conversation_id = conversation_service.create_conversation(title=str(user_input.get("text", ""))[:50] or None)
        self._task_conversation_map[task_id] = conversation_id

        # Persist user message (true source of history)
        user_msg_row = None
        try:
            user_msg_row = conversation_service.append_message(
                conversation_id=conversation_id,
                role="user",
                content=str(user_input.get("text", "") or ""),
                meta={"task_id": task_id},
            )
        except Exception as e:
            print(f"Failed to persist user message for conversation {conversation_id}: {e}")
        if user_msg_row:
            try:
                self.websocket_manager.broadcast_to_task(
                    task_id,
                    WorkflowEventMessage(
                        task_id=task_id,
                        data={
                            "seq": 2,
                            "agent": "user",
                            "phase": "message",
                            "status": "ok",
                            "content": str(user_input.get("text", "") or ""),
                            "meta": {
                                "conversation_id": conversation_id,
                                "message_id": user_msg_row.id,
                                "message_seq": user_msg_row.seq,
                                "role": "user",
                            },
                        },
                    ),
                )
            except Exception as e:
                print(f"Failed to broadcast user message event for task {task_id}: {e}")
        
        # Send task submission response
        submit_response = TaskSubmitResponse(
            task_id=task_id,
            data={
                "status": "success",
                "task_id": task_id,
                "conversation_id": conversation_id,
                "requested_conversation_id": requested_conversation_id,
                "conversation_recreated": conversation_recreated,
                "msg": "Task submitted successfully"
            }
        )
        self.websocket_manager.send_message(connection_id, submit_response)
        
        return task_id
    
    def execute_task(
        self,
        task_id: str,
        task_content: str,
        team_name: str = "general_team",
        runtime_tools: Optional[list] = None,
        runtime_tools_by_agent: Optional[Dict[str, Any]] = None,
        runtime_skills_by_agent: Optional[Dict[str, Any]] = None,
        runtime_tool_configs: Optional[Dict[str, Any]] = None,
    ):
        """Execute task with real AgentMesh logic and stream results"""
        conv_id: Optional[str] = self._task_conversation_map.get(task_id)
        try:
            # Check if shutdown is requested
            if thread_manager.shutdown_event.is_set():
                print(f"Shutdown requested, skipping task {task_id}")
                return
            
            # Update task status to running
            task_service.update_task_status(task_id, TaskStatus.RUNNING)

            # Emit workflow started
            if not conv_id:
                try:
                    rows = conversation_db_manager.execute_query(
                        """
                        SELECT conversation_id
                        FROM conversation_messages
                        WHERE meta_json LIKE ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (f'%\"task_id\": \"{task_id}\"%',),
                    )
                    if rows:
                        conv_id = rows[0]["conversation_id"]
                except Exception:
                    conv_id = None
            self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                task_id=task_id,
                data={
                    "seq": 1,
                    "agent": "system",
                    "phase": "task_started",
                    "status": "running",
                    "content": f"任务开始执行，team={team_name}",
                    "meta": {
                        **({"conversation_id": conv_id} if conv_id else {}),
                        "runtime_tools": runtime_tools if isinstance(runtime_tools, list) else None,
                        "runtime_tools_by_agent": runtime_tools_by_agent if isinstance(runtime_tools_by_agent, dict) else {},
                        "runtime_skills_by_agent": runtime_skills_by_agent if isinstance(runtime_skills_by_agent, dict) else {},
                        "runtime_tool_configs": runtime_tool_configs if isinstance(runtime_tool_configs, dict) else {},
                    },
                }
            ))
            
            # Execute task with real AgentMesh team using run_async for streaming.
            # Build enriched content with long-term memory + vector evidence first.
            enriched = task_content
            context_bundle = {}
            try:
                # If client sent conversation_id, it was persisted in conversation message meta;
                # we can infer conversation by searching last user message with this task_id.
                # conv_id already inferred above
                _ = conv_id
            except Exception:
                conv_id = None
            try:
                context_bundle = context_builder.build_task_bundle(conversation_id=conv_id, user_text=task_content)
                enriched = str(context_bundle.get("task_content") or task_content)
            except Exception:
                enriched = task_content
                context_bundle = {}

            # Expose evidence precheck into workflow timeline for frontend visibility.
            try:
                memory_source = str(context_bundle.get("memory_source_path") or "")
                memory_keyline_hits = int(context_bundle.get("memory_keyline_hits") or 0)
                vector_hit_count = int(context_bundle.get("vector_hit_count") or 0)
                conversation_memory_hit_count = int(context_bundle.get("conversation_memory_hit_count") or 0)
                document_hit_count = int(context_bundle.get("document_hit_count") or 0)
                retrieval_mode = str(context_bundle.get("retrieval_mode") or "vector")
                active_embedding_profile = str(context_bundle.get("active_embedding_profile") or "")
                active_embedding_model = str(context_bundle.get("active_embedding_model") or "")
                memory_load_error = str(context_bundle.get("memory_load_error") or "")
                vector_search_error = str(context_bundle.get("vector_search_error") or "")
                memory_min_score = context_bundle.get("memory_min_score")
                precheck_status = "error" if memory_load_error else ("degraded" if vector_search_error else "ok")
                self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                    task_id=task_id,
                    data={
                        "seq": 3,
                        "agent": "system",
                        "phase": "memory_precheck",
                        "status": precheck_status,
                        "content": (
                            f"长期记忆预检完成：memory_keyline_hits={memory_keyline_hits}, "
                            f"conversation_memory_hit_count={conversation_memory_hit_count}, "
                            f"document_hit_count={document_hit_count}, "
                            f"vector_hit_count={vector_hit_count}"
                        ),
                        "meta": {
                            "memory_source_path": memory_source,
                            "memory_keyline_hits": memory_keyline_hits,
                            "conversation_memory_hit_count": conversation_memory_hit_count,
                            "document_hit_count": document_hit_count,
                            "vector_hit_count": vector_hit_count,
                            "memory_min_score": memory_min_score,
                            "retrieval_mode": retrieval_mode,
                            "active_embedding_profile": active_embedding_profile,
                            "active_embedding_model": active_embedding_model,
                            "memory_load_error": memory_load_error,
                            "vector_search_error": vector_search_error,
                            "conversation_id": conv_id,
                        },
                    }
                ))
            except Exception as e:
                print(f"Failed to broadcast memory_precheck event for task {task_id}: {e}")

            final_text = self.agent_executor.execute_task_with_team_streaming(
                task_id,
                enriched,
                team_name,
                runtime_tools=runtime_tools,
                runtime_tools_by_agent=runtime_tools_by_agent,
                runtime_skills_by_agent=runtime_skills_by_agent,
                runtime_tool_configs=runtime_tool_configs,
            )
            has_final_text = bool((final_text or "").strip())

            # Persist assistant final output
            if conv_id and has_final_text:
                try:
                    arow = conversation_service.append_message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=str(final_text),
                        meta={
                            "task_id": task_id,
                            "team": team_name,
                            "runtime_tools": runtime_tools if isinstance(runtime_tools, list) else None,
                            "runtime_tools_by_agent": runtime_tools_by_agent if isinstance(runtime_tools_by_agent, dict) else {},
                            "runtime_skills_by_agent": runtime_skills_by_agent if isinstance(runtime_skills_by_agent, dict) else {},
                        },
                    )
                    try:
                        self.websocket_manager.broadcast_to_task(
                            task_id,
                            WorkflowEventMessage(
                                task_id=task_id,
                                data={
                                    "seq": 9_999,
                                    "agent": "assistant",
                                    "phase": "message",
                                    "status": "ok",
                                    "content": str(final_text)[:2000],
                                    "meta": {
                                        "conversation_id": conv_id,
                                        "message_id": arow.id,
                                        "message_seq": arow.seq,
                                        "role": "assistant",
                                    },
                                },
                            ),
                        )
                    except Exception as e:
                        print(f"Failed to broadcast assistant message event for task {task_id}: {e}")
                except Exception as e:
                    print(f"Failed to persist assistant message for conversation {conv_id}: {e}")

            if has_final_text:
                # Update task status to success
                task_service.update_task_status(task_id, TaskStatus.SUCCESS)
                self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                    task_id=task_id,
                    data={
                        "seq": 10_000,
                        "agent": "system",
                        "phase": "task_finished",
                        "status": "ok",
                        "content": "任务执行完成",
                        "meta": {"conversation_id": conv_id} if conv_id else {},
                    }
                ))
            else:
                task_service.update_task_status(task_id, TaskStatus.FAILED)
                self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                    task_id=task_id,
                    data={
                        "seq": 10_000,
                        "agent": "system",
                        "phase": "task_finished",
                        "status": "error",
                        "content": "任务执行失败：未获取到模型有效输出，请检查模型配置、API Key、网络或代理设置",
                        "meta": {"conversation_id": conv_id} if conv_id else {},
                    }
                ))
                self._send_task_result(task_id, "failed")
            
        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
            # Update task status to failed
            task_service.update_task_status(task_id, TaskStatus.FAILED)
            self.websocket_manager.broadcast_to_task(task_id, WorkflowEventMessage(
                task_id=task_id,
                data={
                    "seq": 10_000,
                    "agent": "system",
                    "phase": "task_finished",
                    "status": "error",
                    "content": f"任务执行失败：{str(e)}"
                }
            ))
            self._send_task_result(task_id, "failed")
        finally:
            self._task_conversation_map.pop(task_id, None)
    
    def _send_task_result(self, task_id: str, status: str):
        """Send task completion message"""
        message = TaskResultMessage(
            task_id=task_id,
            data={
                "task_id": task_id,
                "status": status
            }
        )
        self.websocket_manager.broadcast_to_task(task_id, message)


# Global instances
websocket_manager = WebSocketManager()
task_processor = TaskProcessor(websocket_manager)
# Backward-compatible alias to the actual executor used by TaskProcessor.
agent_executor = task_processor.agent_executor


def cleanup_on_exit():
    """Cleanup function to be called on exit"""
    print("Cleaning up resources...")
    websocket_manager.shutdown()
    thread_manager.shutdown()


# Register cleanup function
import atexit
atexit.register(cleanup_on_exit) 
