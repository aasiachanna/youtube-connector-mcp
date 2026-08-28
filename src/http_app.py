"""HTTP wrapper for youtube-connector-mcp tools using FastAPI."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio

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
        """Minimal MCP POST endpoint for connector validation.

        Claude will POST to the MCP URL during connector setup. This handler
        accepts any JSON body and returns a simple success response so Claude
        can verify the server is reachable. Implement full MCP semantics later.
        """
        try:
            body = await request.json()
        except Exception:
            body = None

        return {"status": "ok", "message": "mcp endpoint reachable", "received": body}
