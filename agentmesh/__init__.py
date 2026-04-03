# First, set environment variables before any imports
import os

os.environ["BROWSER_USE_LOGGING_LEVEL"] = "error"

# Then import logging and configure it
import logging

logging.getLogger("browser_use").setLevel(logging.ERROR)
logging.getLogger("root").setLevel(logging.ERROR)

# Now import the rest
from agentmesh.protocol import Agent, AgentTeam
from agentmesh.protocol.task import Task
from agentmesh.protocol.result import TeamResult
from agentmesh.models import LLMModel
from agentmesh.common.utils.log import setup_logging

# Setup logging when the package is imported
setup_logging()

__all__ = ['AgentTeam', 'Agent', 'LLMModel', 'Task', 'TeamResult', 'set_workspace', 'get_workspace']

# Global workspace configuration
_global_workspace_root = None


def set_workspace(workspace_root: str):
    """
    Set global workspace root for all agents

    This should be called once at the start of your application.
    All agents will use this workspace unless overridden.

    Args:
        workspace_root: Path to workspace root (e.g., "~/my_agents")

    Example:
        >>> import agentmesh
        >>> agentmesh.set_workspace("~/my_agents")
        >>> # Now all agents will use ~/my_agents as workspace root
    """
    global _global_workspace_root
    _global_workspace_root = os.path.expanduser(workspace_root)

    # Also update memory config
    from agentmesh.memory import MemoryConfig, set_global_memory_config
    config = MemoryConfig(workspace_root=_global_workspace_root)
    set_global_memory_config(config)


def get_workspace() -> str:
    """
    Get current global workspace root

    Returns:
        Current workspace root path, or default "~/agentmesh"
    """
    global _global_workspace_root
    if _global_workspace_root is None:
        return os.path.expanduser("~/agentmesh")
    return _global_workspace_root
