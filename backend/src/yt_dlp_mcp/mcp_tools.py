from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.services.youtube_info import YouTubeInfoService
from yt_dlp_mcp.utils.url import normalize_url


class ToolRegistry:
    def __init__(self, jobs: JobsRepository, transcripts: TranscriptsRepository) -> None:
        self.jobs = jobs
        self.transcripts = transcripts

    def register(self, mcp: FastMCP) -> None:
        yt_info = YouTubeInfoService()

        @mcp.tool
        def transcribe(url: str) -> dict[str, Any]:
            normalized_url = normalize_url(url)

            existing = self.transcripts.get_by_normalized_url(normalized_url)
            if existing is not None:
                return {
                    "status": "completed",
                    "deduplicated": True,
                    "video_id": existing["video_id"],
                    "transcript_path": existing["path"],
                }

            active = self.jobs.find_active_by_normalized_url(normalized_url)
            if active is not None:
                return {
                    "job_id": active["id"],
                    "status": active["status"],
                    "deduplicated": True,
                }

            job = self.jobs.enqueue(url=url, normalized_url=normalized_url)
            return {
                "job_id": job["id"],
                "status": job["status"],
                "deduplicated": False,
            }

        @mcp.tool
        def job_status(job_id: str) -> dict[str, Any]:
            job = self.jobs.get(job_id)
            if job is None:
                return {"error": "job_not_found", "job_id": job_id}
            return job

        @mcp.tool
        def search(query: str, limit: int = 10) -> dict[str, Any]:
            return {
                "query": query,
                "results": self.transcripts.search(query=query, limit=limit),
            }

        @mcp.tool
        def list_transcripts(
            platform: str | None = None,
            channel: str | None = None,
            limit: int = 20,
        ) -> dict[str, Any]:
            items = self.transcripts.list_transcripts(platform=platform, channel=channel, limit=limit)
            return {
                "count": len(items),
                "items": items,
            }

        @mcp.tool
        def read_transcript(video_id: str, format: str = "markdown") -> dict[str, Any]:
            transcript = self.transcripts.get_by_video_id(video_id)
            if transcript is None:
                return {"error": "transcript_not_found", "video_id": video_id}

            base = Path(str(transcript["path"]))
            if format == "markdown":
                file_path = base / "transcript.md"
                content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
                return {
                    "video_id": video_id,
                    "format": "markdown",
                    "content": content,
                    "metadata": transcript,
                }

            if format == "text":
                file_path = base / "transcript.txt"
                content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
                return {
                    "video_id": video_id,
                    "format": "text",
                    "content": content,
                    "metadata": transcript,
                }

            if format == "json":
                file_path = base / "transcript.json"
                payload = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else {}
                return {
                    "video_id": video_id,
                    "format": "json",
                    "content": payload,
                    "metadata": transcript,
                }

            return {
                "error": "unsupported_format",
                "supported_formats": ["markdown", "json", "text"],
            }

        @mcp.tool
        def yt_search(query: str, limit: int = 10) -> dict[str, Any]:
            """Search YouTube for videos.

            Args:
                query: Search query string
                limit: Maximum number of results (default: 10)

            Returns:
                Matching YouTube videos with title, channel, duration, and view count.
            """
            try:
                results = yt_info.search(query=query, limit=limit)
                return {"query": query, "count": len(results), "results": results}
            except RuntimeError as exc:
                return {"error": "search_failed", "message": str(exc)}

        @mcp.tool
        def get_metadata(url: str) -> dict[str, Any]:
            """Get full metadata for a video.

            Args:
                url: The video URL (YouTube, etc.)

            Returns:
                Complete video metadata from yt-dlp.
            """
            try:
                metadata = yt_info.get_metadata(url=url)
                return {"url": url, "metadata": metadata}
            except RuntimeError as exc:
                return {"error": "metadata_failed", "message": str(exc)}

        @mcp.tool
        def get_comments(url: str, limit: int = 20, sort: str = "top") -> dict[str, Any]:
            """Get comments for a video.

            Args:
                url: The video URL (YouTube, etc.)
                limit: Maximum number of comments (default: 20)
                sort: Sort order - "top" or "new" (default: "top")

            Returns:
                Video comments with author, text, likes, and timestamps.
            """
            try:
                comments = yt_info.get_comments(url=url, limit=limit, sort=sort)
                return {"url": url, "count": len(comments), "sort": sort, "comments": comments}
            except RuntimeError as exc:
                return {"error": "comments_failed", "message": str(exc)}
