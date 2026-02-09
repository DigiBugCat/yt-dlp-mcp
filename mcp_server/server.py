"""FastMCP proxy frontend for yt-dlp-mcp.

This thin frontend handles OAuth authentication via fastmcp.cloud and
proxies all tool calls to the backend service protected by Cloudflare Access.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport

BACKEND_URL = os.environ.get("BACKEND_URL", "https://yt-cli.pantainos.net/mcp")
CF_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")


def _make_backend_client() -> Client:
    """Create a backend MCP client with Cloudflare Access headers."""
    headers = {}
    if CF_CLIENT_ID and CF_CLIENT_SECRET:
        headers["CF-Access-Client-Id"] = CF_CLIENT_ID
        headers["CF-Access-Client-Secret"] = CF_CLIENT_SECRET

    transport = StreamableHttpTransport(BACKEND_URL, headers=headers)
    return Client(transport)


@asynccontextmanager
async def _backend_session() -> AsyncIterator[Client]:
    """Context manager for backend client sessions."""
    client = _make_backend_client()
    async with client:
        yield client


mcp = FastMCP("yt-dlp-mcp")


@mcp.tool
async def transcribe(url: str) -> dict[str, Any]:
    """Queue a video for transcription.

    Args:
        url: The video URL to transcribe (YouTube, etc.)

    Returns:
        Job status with job_id for tracking, or completed transcript info if deduplicated.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool("transcribe", {"url": url})
        return _extract_result(result)


@mcp.tool
async def job_status(job_id: str) -> dict[str, Any]:
    """Get the status of a transcription job.

    Args:
        job_id: The job ID returned from transcribe()

    Returns:
        Current job status including: queued, downloading, transcribing, completed, or failed.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool("job_status", {"job_id": job_id})
        return _extract_result(result)


@mcp.tool
async def search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search transcripts by content.

    Args:
        query: Search query string
        limit: Maximum number of results (default: 10)

    Returns:
        Matching transcripts with relevance scores.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool("search", {"query": query, "limit": limit})
        return _extract_result(result)


@mcp.tool
async def list_transcripts(
    platform: str | None = None,
    channel: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List available transcripts.

    Args:
        platform: Filter by platform (e.g., "youtube")
        channel: Filter by channel name
        limit: Maximum number of results (default: 20)

    Returns:
        List of transcript metadata.
    """
    args: dict[str, Any] = {"limit": limit}
    if platform is not None:
        args["platform"] = platform
    if channel is not None:
        args["channel"] = channel

    async with _backend_session() as backend:
        result = await backend.call_tool("list_transcripts", args)
        return _extract_result(result)


@mcp.tool
async def read_transcript(
    video_id: str,
    format: str = "markdown",
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """Read a transcript by video ID.

    Args:
        video_id: The video ID to read
        format: Output format - "markdown", "text", or "json" (default: "markdown")
        offset: Number of lines (markdown/text) or segments (json) to skip (default: 0)
        limit: Max lines/segments to return. None returns all remaining.

    Returns:
        Transcript content in the requested format with pagination info.
    """
    args: dict[str, Any] = {"video_id": video_id, "format": format, "offset": offset}
    if limit is not None:
        args["limit"] = limit

    async with _backend_session() as backend:
        result = await backend.call_tool("read_transcript", args)
        return _extract_result(result)


@mcp.tool
async def yt_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search YouTube for videos.

    Args:
        query: Search query string
        limit: Maximum number of results (default: 10)

    Returns:
        Matching YouTube videos with title, channel, duration, and view count.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool("yt_search", {"query": query, "limit": limit})
        return _extract_result(result)


@mcp.tool
async def get_metadata(url: str) -> dict[str, Any]:
    """Get full metadata for a video.

    Args:
        url: The video URL (YouTube, etc.)

    Returns:
        Complete video metadata from yt-dlp.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool("get_metadata", {"url": url})
        return _extract_result(result)


@mcp.tool
async def get_comments(url: str, limit: int = 20, sort: str = "top") -> dict[str, Any]:
    """Get comments for a video.

    Args:
        url: The video URL (YouTube, etc.)
        limit: Maximum number of comments (default: 20)
        sort: Sort order - "top" or "new" (default: "top")

    Returns:
        Video comments with author, text, likes, and timestamps.
    """
    async with _backend_session() as backend:
        result = await backend.call_tool(
            "get_comments", {"url": url, "limit": limit, "sort": sort}
        )
        return _extract_result(result)


def _extract_result(result: Any) -> dict[str, Any]:
    """Extract the actual result from MCP tool response."""
    if isinstance(result, dict):
        return result
    if hasattr(result, "content") and result.content:
        first = result.content[0]
        if hasattr(first, "text"):
            import json

            try:
                return json.loads(first.text)
            except json.JSONDecodeError:
                return {"raw": first.text}
    return {"raw": str(result)}


def cli() -> None:
    """Run the MCP server."""
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    path = os.environ.get("MCP_PATH", "/mcp")

    logging.info("Starting yt-dlp-mcp frontend on %s:%s%s", host, port, path)
    logging.info("Backend URL: %s", BACKEND_URL)

    mcp.run(transport="http", host=host, port=port, path=path)


if __name__ == "__main__":
    cli()
