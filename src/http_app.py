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
    return {
        "name": "youtube-connector-http",
        "description": "HTTP wrapper for youtube-connector-mcp providing search, video, transcript, comments, and playlists.",
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


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP POST endpoint.

    Behavior:
    - If the POST body is empty or does not request a tool, return a discovery
      response including `auth.type: none` and the manifest (so Claude can
      auto-detect settings).
    - If the POST body contains a `tool` (or `action`) field, dispatch to the
      matching function and return its result.
    """
    logger = logging.getLogger("mcp")
    try:
        body = await request.json()
    except Exception:
        body = None

    # Log request headers and body for debugging of connector discovery
    try:
        headers = dict(request.headers)
    except Exception:
        headers = {}
    logger.info("MCP request headers: %s", headers)
    logger.info("MCP request body: %s", body)

    # If no body or no tool/action requested, return discovery manifest
    if not body or not isinstance(body, dict) or ("tool" not in body and "action" not in body):
        manifest_data = await manifest()
        response = {
            "status": "ok",
            "auth": {"type": "none"},
            "manifest": manifest_data,
            "received": body,
        }
        return JSONResponse(response)

    # Extract tool name and args (support both 'tool' and 'action')
    tool_name = body.get("tool") or body.get("action")
    args = body.get("args") or body.get("params") or {}

    try:
        if tool_name == "search":
            q = args.get("q") or args.get("query")
            max_results = int(args.get("max_results", 10))
            order = args.get("order", "relevance")
            t = args.get("type", "video")
            result = await youtube_search(query=q, max_results=max_results, order=order, type=t)

        elif tool_name in ("video", "get_video"):
            vid = args.get("video_id") or args.get("id")
            result = await youtube_get_video(video_id=vid)

        elif tool_name in ("transcript", "get_transcript"):
            vid = args.get("video_id") or args.get("id")
            lang = args.get("language")
            result = await youtube_get_transcript(video_id=vid, language=lang)

        elif tool_name in ("channel", "get_channel"):
            cid = args.get("channel_id") or args.get("id")
            result = await youtube_get_channel(channel_id=cid)

        elif tool_name in ("comments", "get_comments"):
            vid = args.get("video_id") or args.get("id")
            max_results = int(args.get("max_results", 20))
            page_token = args.get("page_token")
            result = await youtube_get_comments(video_id=vid, max_results=max_results, page_token=page_token)

        elif tool_name in ("playlist", "get_playlist"):
            pid = args.get("playlist_id") or args.get("id")
            max_results = int(args.get("max_results", 50))
            result = await youtube_get_playlist(playlist_id=pid, max_results=max_results)

        elif tool_name in ("playlists", "list_playlists"):
            cid = args.get("channel_id") or args.get("id")
            max_results = int(args.get("max_results", 50))
            result = await youtube_list_playlists(channel_id=cid, max_results=max_results)

        else:
            return JSONResponse({"status": "error", "error": f"unknown tool '{tool_name}'"}, status_code=400)

    except Exception as e:
        logger.exception("Error dispatching MCP tool %s", tool_name)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

    # Normalize and return the tool result
    return JSONResponse({"status": "ok", "tool": tool_name, "result": result})
