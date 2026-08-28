"""ASGI adapter exposing the MCP server over Streamable HTTP (SSE).

This file creates a `StreamableHTTPSessionManager` for the MCP `server`
defined in `src/main.py` and mounts it at `/mcp` in a small FastAPI app.
Use this with `uvicorn src.http_mcp:app` (Procfile updated).
"""
import contextlib
from fastapi import FastAPI

from src.main import server  # the MCP Server instance defined in src/main.py
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager, StreamableHTTPASGIApp


# Create a StreamableHTTP session manager. Keep json_response=False so the
# transport uses SSE/event-stream by default. We don't enable resumability here.
manager = StreamableHTTPSessionManager(server, json_response=False, stateless=False)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with manager.run():
        yield


app = FastAPI(title="YouTube MCP (HTTP)", lifespan=lifespan)

# Mount the Streamable HTTP ASGI app at /mcp
streamable_app = StreamableHTTPASGIApp(manager)
app.mount("/mcp", streamable_app)


@app.get("/health")
async def health():
    return {"status": "ok", "mcp": True}
