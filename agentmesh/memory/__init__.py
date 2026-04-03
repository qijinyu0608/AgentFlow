"""
Memory module for AgentMesh.

Exposes the unified memory manager and configuration utilities used by the runtime.
"""

from agentmesh.memory.config import MemoryConfig, get_default_memory_config, set_global_memory_config
from agentmesh.memory.manager import MemoryManager, memory_manager

__all__ = [
    "MemoryConfig",
    "MemoryManager",
    "memory_manager",
    "get_default_memory_config",
    "set_global_memory_config",
]
