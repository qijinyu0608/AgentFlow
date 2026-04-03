"""Backward-compatible import shim for the browser tool module path."""

try:
    from agentmesh.tools.browser.browser_tool import BrowserTool
except ImportError:
    class BrowserTool:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "The 'browser-use' package is required to use BrowserTool. "
                "Please install it with 'pip install browser-use>=0.1.40' or "
                "'pip install agentmesh-sdk[full]'."
            )

__all__ = ["BrowserTool"]
