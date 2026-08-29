"""MCP Server entry point - YouTube MCP Server."""
import asyncio
import mcp.types as types
# Use the low-level Server implementation for runtime (required by the
# StreamableHTTPSessionManager which expects the `.lifespan` attribute).
from mcp.server.lowlevel.server import Server

# Create the runtime Server instance used by the Streamable manager.
server = Server("youtube-connector-mcp")


def make_server():
    """Return the configured MCP Server instance.

    This factory is used by the ASGI adapter to obtain the fully-configured
    server with all tools, prompts, and resources registered. Avoids creating
    a new empty Server which would hide registration/import errors.
    """
    # Register module-based tools once so the server's ToolManager is populated
    # and `tools/list` reflects available tools. Import register helpers here
    # to avoid import-time side-effects when the module is imported.
    if not getattr(server, "_tools_registered", False):
        try:
            from src.tools.search import register_search_tools
            register_search_tools(server)
        except Exception:
            pass

        try:
            from src.tools.video import register_video_tools
            register_video_tools(server)
        except Exception:
            pass

        try:
            from src.tools.transcript import register_transcript_tools
            register_transcript_tools(server)
        except Exception:
            pass

        try:
            from src.tools.playlist import register_playlist_tools
            register_playlist_tools(server)
        except Exception:
            pass

        try:
            from src.tools.comments import register_comments_tools
            register_comments_tools(server)
        except Exception:
            pass

        try:
            from src.tools.channel import register_channel_tools
            register_channel_tools(server)
        except Exception:
            pass

        setattr(server, "_tools_registered", True)

    # Register low-level request handlers so the Server exposes MCP methods
    # even when decorator factories are not present. This wraps the
    # higher-level helper functions declared above into the low-level
    # request handler shape: (ctx, params) -> ResultModel
    if not getattr(server, "_handlers_registered", False):
        # tools/list
        async def _tools_list_handler(ctx, params):
            tools = await list_tools()
            return types.ListToolsResult(tools=tools)

        server.add_request_handler("tools/list", types.PaginatedRequestParams, _tools_list_handler)

        # tools/call
        async def _tools_call_handler(ctx, params):
            # params is a CallToolRequestParams pydantic model
            name = getattr(params, "name", None)
            arguments = getattr(params, "arguments", {}) or {}
            result = await call_tool(name, arguments)
            return types.CallToolResult(content=[types.TextContent(type="text", text=str(result))])

        server.add_request_handler("tools/call", types.CallToolRequestParams, _tools_call_handler)

        # resources/list
        async def _resources_list_handler(ctx, params):
            resources = await list_resources()
            return types.ListResourcesResult(resources=resources)

        server.add_request_handler("resources/list", types.PaginatedRequestParams, _resources_list_handler)

        # resources/read
        async def _resources_read_handler(ctx, params):
            # params.uri
            contents = await read_resource(params.uri)
            # Convert list of Resource -> ListResourceResult expected shape
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri=str(params.uri), text=c.content) for c in contents])

        server.add_request_handler("resources/read", types.ReadResourceRequestParams, _resources_read_handler)

        # prompts/list
        async def _prompts_list_handler(ctx, params):
            prompts = await list_prompts()
            return types.ListPromptsResult(prompts=prompts)

        server.add_request_handler("prompts/list", types.PaginatedRequestParams, _prompts_list_handler)

        # prompts/get
        async def _prompts_get_handler(ctx, params):
            result = await get_prompt(params.name, params.arguments if hasattr(params, "arguments") else None)
            return result

        server.add_request_handler("prompts/get", types.GetPromptRequestParams, _prompts_get_handler)

        setattr(server, "_handlers_registered", True)

    return server


# Compatibility: some mcp.Server versions may not provide the decorator
# methods used below (list_resources, read_resource, list_prompts, etc.).
# Provide a helper that returns a no-op decorator when the server lacks
# the method so importing this module won't raise AttributeError and crash
# the ASGI process. This preserves startup while signalling reduced
# MCP capability when the SDK is incompatible.
def _maybe_decorator(method_name: str):
    import inspect

    if hasattr(server, method_name):
        attr = getattr(server, method_name)
        # Some MCPServer versions implement these as coroutine handler
        # methods (e.g. `async def list_resources`) rather than returning
        # decorator factories. If the attribute is a coroutine function,
        # it is not a decorator factory — return a noop decorator so
        # module-level handler definitions remain import-safe.
        if inspect.iscoroutinefunction(attr):
            def _noop(func):
                return func

            return _noop

        try:
            return attr()
        except Exception:
            # If calling the decorator factory raises, fall through to noop
            pass

    def _noop(func):
        return func

    return _noop

# Import all tools
from src.tools.search import youtube_search, SearchArgs
from src.tools.video import youtube_get_video, GetVideoArgs
from src.tools.transcript import youtube_get_transcript, GetTranscriptArgs
from src.tools.playlist import youtube_get_playlist, youtube_list_playlists, GetPlaylistArgs, ListPlaylistsArgs
from src.tools.comments import youtube_get_comments, GetCommentsArgs
from src.tools.channel import youtube_get_channel, GetChannelArgs


@_maybe_decorator('list_resources')
async def list_resources():
    return [
        types.Resource(
            uri="youtube://config",
            name="Server Configuration",
            description="Current YouTube MCP server configuration and capabilities",
            mimeType="application/json"
        ),
        types.Resource(
            uri="youtube://help",
            name="Help Documentation",
            description="Documentation on how to use the YouTube MCP tools",
            mimeType="text/markdown"
        ),
        types.Resource(
            uri="youtube://quota",
            name="YouTube API Quota Guidelines",
            description="Information about YouTube Data API quota limits and best practices",
            mimeType="text/markdown"
        ),
    ]
@_maybe_decorator('read_resource')
async def read_resource(uri):
    uri_str = str(uri)

    if uri_str == "youtube://config":
        import json
        config = {
            "name": "youtube-connector-mcp",
            "version": "0.3.0",
            "capabilities": {
                "tools": [
                    "youtube_search",
                    "youtube_get_video",
                    "youtube_get_channel",
                    "youtube_get_transcript",
                    "youtube_get_playlist",
                    "youtube_list_playlists",
                    "youtube_get_comments",
                ],
                "resources": [
                    "youtube://config",
                    "youtube://help",
                    "youtube://quota",
                ],
            },
        }

        return json.dumps(config, indent=2)

    elif uri_str == "youtube://help":
        return """# YouTube MCP Server - Help Documentation

## Available Tools

### youtube_search
Search YouTube for videos, channels, or playlists.
- **query** (required): Search query string
- **max_results** (optional): Maximum results to return (default: 10)
- **order** (optional): Sort order - relevance, date, rating, viewCount, title
- **type** (optional): Filter by type - video, channel, playlist

### youtube_get_video
Get detailed information about a YouTube video.
- **video_id** (required): The YouTube video ID
- **part** (optional): Data parts to retrieve (snippet, statistics, contentDetails)

### youtube_get_channel
Get channel information.
- **channel_id** (optional): The YouTube channel ID
- **username** (optional): The channel username

### youtube_get_transcript
Get transcript/captions for a YouTube video.
- **video_id** (required): The YouTube video ID
- **language** (optional): Preferred language code (e.g., 'en', 'es')

### youtube_get_playlist
Get playlist details and video list.
- **playlist_id** (required): The YouTube playlist ID
- **max_results** (optional): Maximum videos to return

### youtube_list_playlists
List playlists for a channel.
- **channel_id** (required): The YouTube channel ID
- **max_results** (optional): Maximum playlists to return

### youtube_get_comments
Get comments for a YouTube video.
- **video_id** (required): The YouTube video ID
- **max_results** (optional): Maximum comments to return
- **page_token** (optional): Token for pagination

## Tips
- Video IDs can be extracted from URLs like youtube.com/watch?v=VIDEO_ID
- Channel IDs start with 'UC' followed by 22 characters
- Playlist IDs start with 'PL' for user playlists
"""

    elif uri_str == "youtube://quota":
        return """# YouTube Data API Quota Guidelines

## Overview
The YouTube Data API uses a quota system to ensure fair usage. Each project has a daily quota allocation.

## Quota Costs by Operation
- **Search**: ~100 units per request
- **Video details**: ~1 unit per request
- **Channel details**: ~1 unit per request
- **Playlist items**: ~1 unit per request
- **Comments**: ~1 unit per request

## Default Quota
- Default allocation: 10,000 units per day
- Resets at midnight Pacific Time

## Best Practices
1. **Cache results** when possible to reduce API calls
2. **Use specific queries** to get relevant results quickly
3. **Request only needed fields** using the 'part' parameter
4. **Implement pagination** instead of requesting large result sets
5. **Handle quota errors** gracefully with retry logic

## Quota Error Handling
When quota is exceeded, the API returns error code 403 with reason 'quotaExceeded'.
Implement exponential backoff and consider:
- Reducing request frequency
- Caching more aggressively
- Requesting quota increase from Google Cloud Console

## More Information
Visit: https://developers.google.com/youtube/v3/getting-started#quota
"""

    raise ValueError(f"Resource not found: {uri}")


# Prompts
@_maybe_decorator('list_prompts')
async def list_prompts():
    """List all available YouTube MCP prompts."""
    return [
        types.Prompt(
            name="search_videos",
            title="Search YouTube Videos",
            description="Search for YouTube videos on a specific topic with customizable filters",
            arguments=[
                types.PromptArgument(
                    name="topic",
                    description="The topic or keywords to search for",
                    required=True
                ),
                types.PromptArgument(
                    name="max_results",
                    description="Maximum number of results to return (default: 10)",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="analyze_channel",
            title="Analyze YouTube Channel",
            description="Get a comprehensive analysis of a YouTube channel including statistics and recent content",
            arguments=[
                types.PromptArgument(
                    name="channel_id",
                    description="The YouTube channel ID to analyze",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="summarize_video",
            title="Summarize Video Content",
            description="Get a summary of a YouTube video based on its transcript",
            arguments=[
                types.PromptArgument(
                    name="video_id",
                    description="The YouTube video ID to summarize",
                    required=True
                ),
                types.PromptArgument(
                    name="language",
                    description="Preferred language for the transcript (default: en)",
                    required=False
                )
            ]
        )
    ]
@_maybe_decorator('get_prompt')
async def get_prompt(name: str, arguments: dict | None = None):
    """Get a specific prompt by name with the provided arguments."""
    args = arguments or {}

    if name == "search_videos":
        topic = args.get("topic", "")
        max_results = args.get("max_results", "10")
        return types.GetPromptResult(
            description="Search for YouTube videos",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""Search YouTube for videos about "{topic}".

Use the youtube_search tool with:
- query: "{topic}"
- max_results: {max_results}
- type: "video"

After getting the results, provide a summary of the most relevant videos found, including:
1. Video titles and channels
2. View counts and publish dates
3. Brief descriptions of what each video covers
4. Recommendations for which videos might be most useful"""
                    )
                )
            ]
        )

    elif name == "analyze_channel":
        channel_id = args.get("channel_id", "")
        return types.GetPromptResult(
            description="Analyze a YouTube channel",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""Analyze the YouTube channel with ID "{channel_id}".

Please perform these steps:
1. Use youtube_get_channel to get the channel's basic information and statistics
2. Use youtube_search with the channel filter to find their recent videos
3. Use youtube_list_playlists to see how they organize their content

Provide a comprehensive analysis including:
- Channel overview (name, description, creation date)
- Key statistics (subscribers, total views, video count)
- Content themes and topics they cover
- Upload frequency and consistency
- Notable or popular videos
- Overall assessment of the channel's focus and audience"""
                    )
                )
            ]
        )

    elif name == "summarize_video":
        video_id = args.get("video_id", "")
        language = args.get("language", "en")
        return types.GetPromptResult(
            description="Summarize a YouTube video",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""Summarize the YouTube video with ID "{video_id}".

Please perform these steps:
1. Use youtube_get_video to get the video's metadata (title, description, statistics)
2. Use youtube_get_transcript with language "{language}" to get the video's transcript
3. Use youtube_get_comments to see viewer reactions and discussions

Provide a comprehensive summary including:
- Video title and channel
- Main topics and key points covered
- Important timestamps or sections (if identifiable)
- Key takeaways and conclusions
- Notable viewer comments or discussions
- Overall assessment of the video's value and content quality"""
                    )
                )
            ]
        )

    else:
        raise ValueError(f"Unknown prompt: {name}")
@_maybe_decorator('list_tools')
async def list_tools():
    """List all available YouTube MCP tools."""
    return [
        types.Tool(
            name="youtube_search",
            description="Search YouTube for videos, channels, or playlists",
            inputSchema=SearchArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_get_video",
            description="Get detailed information about a YouTube video",
            inputSchema=GetVideoArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_get_channel",
            description="Get channel information",
            inputSchema=GetChannelArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_get_transcript",
            description="Get transcript/captions for a YouTube video",
            inputSchema=GetTranscriptArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_get_playlist",
            description="Get playlist details and video list",
            inputSchema=GetPlaylistArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_list_playlists",
            description="List playlists for a channel",
            inputSchema=ListPlaylistsArgs.model_json_schema()
        ),
        types.Tool(
            name="youtube_get_comments",
            description="Get comments for a YouTube video",
            inputSchema=GetCommentsArgs.model_json_schema()
        ),
    ]
@_maybe_decorator('call_tool')
async def call_tool(name, arguments):
    """Route tool calls to appropriate functions."""
    if name == "youtube_search":
        args = SearchArgs(**arguments)
        return await youtube_search(
            query=args.query,
            max_results=args.max_results,
            order=args.order,
            type=args.type
        )
    elif name == "youtube_get_video":
        args = GetVideoArgs(**arguments)
        return await youtube_get_video(
            video_id=args.video_id,
            part=args.part
        )
    elif name == "youtube_get_channel":
        args = GetChannelArgs(**arguments)
        return await youtube_get_channel(
            channel_id=args.channel_id,
            username=args.username
        )
    elif name == "youtube_get_transcript":
        args = GetTranscriptArgs(**arguments)
        return await youtube_get_transcript(
            video_id=args.video_id,
            language=args.language
        )
    elif name == "youtube_get_playlist":
        args = GetPlaylistArgs(**arguments)
        return await youtube_get_playlist(
            playlist_id=args.playlist_id,
            max_results=args.max_results
        )
    elif name == "youtube_list_playlists":
        args = ListPlaylistsArgs(**arguments)
        return await youtube_list_playlists(
            channel_id=args.channel_id,
            max_results=args.max_results
        )
    elif name == "youtube_get_comments":
        args = GetCommentsArgs(**arguments)
        return await youtube_get_comments(
            video_id=args.video_id,
            max_results=args.max_results,
            page_token=args.page_token
        )
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def cli_main():
    """Entry point for CLI - runs async main."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
