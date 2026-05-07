"""
MultiMCPServer — fan-out wrapper over two MCPStdioServer instances.

Merges tool lists from both servers and routes call_tool to whichever
server registered that tool name. Used to run filesystem + context-mode
side-by-side in the same agent session.
"""

from contextlib import AsyncExitStack
from typing import Any, Dict, List

from .stdio_server import MCPStdioServer


class MultiMCPServer:
    """Combines two MCPStdioServer instances into a single server interface."""

    def __init__(self, primary: MCPStdioServer, secondary: MCPStdioServer):
        self._primary = primary
        self._secondary = secondary
        self._tool_owner: Dict[str, MCPStdioServer] = {}
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.enter_async_context(self._primary)
        await self._stack.enter_async_context(self._secondary)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()
        self._stack = None
        self._tool_owner.clear()

    async def list_tools(self) -> List[Dict[str, Any]]:
        primary_tools = await self._primary.list_tools()
        secondary_tools = await self._secondary.list_tools()

        self._tool_owner.clear()
        for t in primary_tools:
            self._tool_owner[t["name"]] = self._primary
        for t in secondary_tools:
            self._tool_owner[t["name"]] = self._secondary

        return primary_tools + secondary_tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        server = self._tool_owner.get(name, self._primary)
        return await server.call_tool(name, arguments)
