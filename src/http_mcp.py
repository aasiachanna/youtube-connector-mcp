import os
from fastapi import FastAPI
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp


def make_app(server_factory):
    """Create an ASGI app that mounts the Streamable HTTP MCP app at /mcp.

    server_factory: a callable that returns a configured `mcp.server.Server` instance.
    """
    app = FastAPI()

    # Create the manager with the server instance
    server = server_factory()
    manager = StreamableHTTPSessionManager(server)

    # Mount the Streamable HTTP ASGI app at /mcp
    mcp_app = StreamableHTTPASGIApp(manager)
    app.mount("/mcp", mcp_app)

    # Optionally expose a health endpoint at root
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


# Import the user's Server factory from src.main (assumes src/main.py defines `make_server`)
try:
    from src.main import make_server
except Exception:
    # Fallback: import main and call Server creation function named `create_server` or `server`
    try:
        from src.main import create_server as make_server
    except Exception:
        # As a last resort, import the Server class and create a simple server
        from mcp.server.server import Server

        def make_server():
            return Server("youtube-connector-mcp")


app = make_app(make_server)
