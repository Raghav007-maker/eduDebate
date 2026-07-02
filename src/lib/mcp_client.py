import sys
import os
import asyncio
from mcp import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

import sys

# Absolute path of the MCP server script and Python interpreter
SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server.py"))
VENV_PYTHON = sys.executable  # Uses whatever Python is running the app

async def query_wikipedia_mcp(query: str) -> str:
    """Spawns the Wikipedia FastMCP server as a subprocess, calls the wikipedia_search tool, and returns results.

    Implements a robust try/except fallback block to handle subprocess failures or missing resources.
    """
    # Use the absolute path to virtual environment interpreter to ensure dependency isolation
    server_params = StdioServerParameters(
        command=VENV_PYTHON,
        args=[SERVER_PATH]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tool_result = await session.call_tool("wikipedia_search", arguments={"query": query})
                
                if tool_result and hasattr(tool_result, "content"):
                    for block in tool_result.content:
                        if hasattr(block, "text"):
                            return block.text
                        elif hasattr(block, "type") and block.type == "text":
                            return block.text
                return "Wikipedia search returned empty or unreadable content."
    except Exception as e:
        # Graceful degradation if the server dies or network times out
        return f"Wikipedia search is currently unverified due to source unavailability. Details: {str(e)}"
