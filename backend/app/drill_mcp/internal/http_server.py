import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from app.drill_mcp.internal.proxy import DrillProxyService
from app.drill_mcp.internal.server import build_server

LOOPBACK_HOST = "127.0.0.1"
MCP_PATH = "/mcp"
STARTUP_POLL_SECONDS = 0.01


class HttpServerStartError(RuntimeError):
    pass


@asynccontextmanager
async def serve_streamable_http(proxy: DrillProxyService, run_id: str) -> AsyncIterator[str]:
    sessions = StreamableHTTPSessionManager(
        app=build_server(proxy, run_id),
        stateless=True,
        json_response=True,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            sessions.handle_request,
            interface="asgi3",
            lifespan="off",
            log_config=None,
            access_log=False,
        )
    )
    listener = socket.create_server((LOOPBACK_HOST, 0))
    async with sessions.run():
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise HttpServerStartError("The Drill MCP HTTP server stopped while starting")
                await asyncio.sleep(STARTUP_POLL_SECONDS)
            yield f"http://{LOOPBACK_HOST}:{listener.getsockname()[1]}{MCP_PATH}"
        finally:
            server.should_exit = True
            await serving
            listener.close()
