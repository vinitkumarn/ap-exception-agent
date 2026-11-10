"""Lets the (synchronous) agent loop call tools on the MCP server.

MCP clients are async, and the session must be opened and closed by the SAME async task.
So: one background thread runs an event loop; one long-lived task owns the session and
serves requests from a queue. The agent just calls runner(name, args) -> (ok, text).
"""
import asyncio
import json
import os
import sys
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpToolRunner:
    def __init__(self, timeout: float = 30):
        self.timeout = timeout
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.queue: asyncio.Queue = None
        self.owner = asyncio.run_coroutine_threadsafe(self._serve(), self.loop)
        if not self.ready.wait(timeout):
            raise RuntimeError("MCP server did not start")

    async def _serve(self):
        self.queue = asyncio.Queue()
        params = StdioServerParameters(command=sys.executable, args=["-m", "apagent.mcp_server"],
                                       env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.ready.set()
                while True:
                    item = await self.queue.get()
                    if item is None:            # shutdown signal
                        return
                    name, args, fut = item
                    try:
                        fut.set_result(await session.call_tool(name, args))
                    except Exception as e:      # hand the error back to the caller
                        fut.set_exception(e)

    async def _submit(self, name, args):
        fut = self.loop.create_future()
        await self.queue.put((name, args, fut))
        return await fut

    def __call__(self, name: str, args: dict) -> tuple[bool, str]:
        try:
            result = asyncio.run_coroutine_threadsafe(self._submit(name, args), self.loop).result(self.timeout)
        except Exception as e:
            return False, f"MCP call failed: {type(e).__name__}: {e}"
        text = "".join(getattr(c, "text", "") for c in result.content)
        if getattr(result, "is_error", False) or getattr(result, "isError", False):
            return False, text
        try:
            data = json.loads(text)
            if isinstance(data, dict) and set(data) == {"error"}:
                return False, data["error"]
        except json.JSONDecodeError:
            pass
        return True, text

    def close(self):
        asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop).result(5)
        self.owner.result(10)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
