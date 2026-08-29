import os
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
import logging
import asyncio


def make_app(server_factory):
    """Create an ASGI app that mounts the Streamable HTTP MCP app at /mcp.

    server_factory: a callable that returns a configured `mcp.server.Server` instance.
    """
    app = FastAPI()

    # Create the manager with the server instance
    server = server_factory()
    # Use stateless mode so plain POST requests without an `mcp-session-id`
    # header are accepted. Stateful session tracking requires clients to
    # include the session ID header and is not necessary for basic
    # Streamable HTTP usage by Claude when using simple POST flows.
    manager = StreamableHTTPSessionManager(server, stateless=True)

    # Ensure manager run lifecycle is tied to the FastAPI lifespan
    # Use manager.run() as an async context manager tied to lifespan
    @app.on_event("startup")
    async def _start_manager():
        # Enter the manager context so it begins accepting streamable sessions
        app.state._mcp_manager_cm = manager.run()
        await app.state._mcp_manager_cm.__aenter__()

    @app.on_event("shutdown")
    async def _stop_manager():
        # Exit the manager context to shutdown cleanly
        cm = getattr(app.state, "_mcp_manager_cm", None)
        if cm is not None:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                logging.exception("Error shutting down MCP manager")

    # Mount the Streamable HTTP ASGI app at /mcp/ (use trailing slash to
    # avoid Starlette redirect from `/mcp` -> `/mcp/` which breaks
    # streamable clients that don't follow 307 redirects.
    mcp_app = StreamableHTTPASGIApp(manager)
    app.mount("/mcp/", mcp_app)

    # Optionally expose a health endpoint at root
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


# Import the user's Server factory from src.main (assumes src/main.py defines `make_server`)
from src.main import make_server


app = make_app(make_server)


@app.get("/manifest")
async def manifest(request: Request):
    # Expose the same HTTP manifest but do not use this endpoint for the MCP protocol
    return JSONResponse({"name": "youtube-connector-mcp", "auth": {"type": "none"}})
