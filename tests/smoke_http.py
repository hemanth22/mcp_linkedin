"""Connect to a running HTTP server and check it speaks MCP.

Usage: python tests/smoke_http.py http://127.0.0.1:8000/mcp
"""

import asyncio
import sys

from fastmcp import Client


async def run(url: str) -> None:
    async with Client(url) as client:
        tools = sorted(t.name for t in await client.list_tools())
    print("tools:", tools)
    assert "search_latest_jobs" in tools, tools


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
