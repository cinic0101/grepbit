"""Synthetic MCP child for web lifecycle tests. Never touches a DB/model."""

import asyncio
import os
from uuid import uuid4

from mcp.server.mcpserver import MCPServer

from grepbit.adapters.mcp_server import result_payload
from grepbit.application.ask import AskResult

server = MCPServer("web-lifecycle-fixture")


@server.tool(name="ask")
async def ask(datasource_id: str, question: str, as_of: str) -> dict[str, object]:
    if question == "die":
        os._exit(7)
    if question == "slow":
        await asyncio.sleep(20)
    return result_payload(
        AskResult(question=question, status="answered", rows=[{"n": 0}], row_count=1),
        max_rows=200,
    ) | {"request_id": str(uuid4())}


if __name__ == "__main__":
    server.run(transport="stdio")
