"""HTTP wrapper for youtube-connector-mcp tools using FastAPI."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio
import logging

from src.tools.search import youtube_search
from src.tools.video import youtube_get_video
from src.tools.transcript import youtube_get_transcript
from src.tools.channel import youtube_get_channel
from src.tools.comments import youtube_get_comments
from src.tools.playlist import youtube_get_playlist, youtube_list_playlists


app = FastAPI(title="YouTube Connector HTTP API")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/search")
async def search(q: str, max_results: int = 10, order: str = "relevance", type: str = "video"):
    result = await youtube_search(query=q, max_results=max_results, order=order, type=type)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return JSONResponse(result)


@app.get("/video/{video_id}")
async def get_video(video_id: str):
    result = await youtube_get_video(video_id=video_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(result)


@app.get("/transcript/{video_id}")
async def get_transcript(video_id: str, language: Optional[str] = None):
    result = await youtube_get_transcript(video_id=video_id, language=language)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(result)


@app.get("/channel/{channel_id}")
async def get_channel(channel_id: str):
    result = await youtube_get_channel(channel_id=channel_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(result)


@app.get("/comments/{video_id}")
async def get_comments(video_id: str, max_results: int = 20, page_token: Optional[str] = None):
    result = await youtube_get_comments(video_id=video_id, max_results=max_results, page_token=page_token)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return JSONResponse(result)


@app.get("/playlist/{playlist_id}")
async def get_playlist(playlist_id: str, max_results: int = 50):
    result = await youtube_get_playlist(playlist_id=playlist_id, max_results=max_results)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(result)


@app.get("/playlists/{channel_id}")
async def list_playlists(channel_id: str, max_results: int = 50):
    result = await youtube_list_playlists(channel_id=channel_id, max_results=max_results)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return JSONResponse(result)


@app.get("/manifest")
async def manifest():
    """Simple manifest describing available HTTP endpoints."""
    # Include explicit auth declaration so MCP clients (Claude) know no sign-in is required
    return {
        "name": "youtube-connector-http",
        "description": "HTTP wrapper for youtube-connector-mcp providing search, video, transcript, comments, and playlists.",
        "auth": {"type": "none"},
        "endpoints": {
            "search": "/search?q=...",
            "video": "/video/{video_id}",
            "transcript": "/transcript/{video_id}",
            "channel": "/channel/{channel_id}",
            "comments": "/comments/{video_id}",
            "playlist": "/playlist/{playlist_id}",
            "playlists": "/playlists/{channel_id}"
        }
    }


# Some MCP clients probe for an OAuth server discovery document at the
# well-known path. Return a harmless 200 JSON to avoid false-positive
# sign-in registration warnings when no OAuth is supported.
@app.get("/.well-known/oauth-authorization-server")
async def oauth_well_known(request: Request):
    host = request.headers.get("host", "")
    issuer = f"https://{host}" if host else ""
    # Minimal OAuth metadata (empty endpoints indicate no OAuth configured)
    return JSONResponse({
        "issuer": issuer,
        "authorization_endpoint": "",
        "token_endpoint": "",
    })


# Some MCP clients attempt to POST to /register to register an OAuth
# sign-in service. Return a harmless 200 response indicating no OAuth
# is configured so the connector UI won't surface a registration error.
@app.post("/register")
async def register_probe(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = None
    return JSONResponse({
        "status": "ok",
        "message": "no_oauth_configured",
        "received": body,
    })


# Some clients probe for a protected-resource discovery path. Return a
# harmless 200 so the connector UI won't show a sign-in/register warning.
@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request):
    host = request.headers.get("host", "")
    issuer = f"https://{host}" if host else ""
    return JSONResponse({
        "issuer": issuer,
        "resource": "none",
        "message": "no_oauth_configured",
    })


@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_mcp(request: Request):
    host = request.headers.get("host", "")
    issuer = f"https://{host}" if host else ""
    return JSONResponse({
        "issuer": issuer,
        "resource": "mcp",
        "message": "no_oauth_configured",
    })


# Catch-all for other well-known paths that mention oauth. Return a harmless
# 200 JSON for oauth-related probes, otherwise 404 so we don't accidentally
# respond to unrelated well-known requests.
@app.get("/.well-known/{rest:path}")
async def well_known_catchall(rest: str, request: Request):
    if "oauth" in rest:
        host = request.headers.get("host", "")
        issuer = f"https://{host}" if host else ""
        return JSONResponse({
            "issuer": issuer,
            "path": rest,
            "message": "no_oauth_configured",
        })
    raise HTTPException(status_code=404)


# The real MCP endpoint is provided by the ASGI adapter `src.http_mcp` which
# mounts the Streamable HTTP MCP app at `/mcp`. Keep the HTTP-only manifest
# and health routes here, but do not implement the MCP protocol over this
# regular FastAPI app because that would not be Streamable HTTP/SSE.
