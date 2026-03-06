from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from yt_dlp_mcp.db.jobs import ACTIVE_STATUSES, JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.services.youtube_info import YouTubeInfoService
from yt_dlp_mcp.utils.url import normalize_url, extract_youtube_video_id


class ToolRegistry:
    def __init__(self, jobs: JobsRepository, transcripts: TranscriptsRepository) -> None:
        self.jobs = jobs
        self.transcripts = transcripts

    def register(self, mcp: FastMCP) -> None:
        yt_info = YouTubeInfoService()
        _ro = ToolAnnotations(readOnlyHint=True)

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
        def transcribe(url: str) -> dict[str, Any]:
            normalized_url = normalize_url(url)

            existing = self.transcripts.get_by_normalized_url(normalized_url)
            if existing is None:
                # Also check by video_id — catches cases where the same video was
                # previously stored under a different URL form (e.g. /live/ vs /watch?v=)
                video_id = extract_youtube_video_id(normalized_url)
                if video_id:
                    existing = self.transcripts.get_by_video_id(video_id)
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

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
        def transcribe_playlist(url: str) -> dict[str, Any]:
            """Queue all videos in a playlist for transcription.

            Args:
                url: Playlist URL (YouTube playlist, channel, etc.)

            Returns:
                List of enqueued jobs (one per video), with dedup applied per-video.
            """
            try:
                entries = yt_info.extract_playlist(url)
            except RuntimeError as exc:
                return {"error": "playlist_extraction_failed", "message": str(exc)}

            if not entries:
                return {"error": "empty_playlist", "message": "No videos found in playlist"}

            results: list[dict[str, Any]] = []
            for entry in entries:
                video_url = entry["url"]
                normalized = normalize_url(video_url)

                existing = self.transcripts.get_by_normalized_url(normalized)
                if existing is None:
                    video_id = extract_youtube_video_id(normalized)
                    if video_id:
                        existing = self.transcripts.get_by_video_id(video_id)
                if existing is not None:
                    results.append({
                        "video_url": video_url,
                        "title": entry.get("title"),
                        "status": "completed",
                        "deduplicated": True,
                        "video_id": existing["video_id"],
                    })
                    continue

                active = self.jobs.find_active_by_normalized_url(normalized)
                if active is not None:
                    results.append({
                        "video_url": video_url,
                        "title": entry.get("title"),
                        "job_id": active["id"],
                        "status": active["status"],
                        "deduplicated": True,
                    })
                    continue

                job = self.jobs.enqueue(url=video_url, normalized_url=normalized)
                results.append({
                    "video_url": video_url,
                    "title": entry.get("title"),
                    "job_id": job["id"],
                    "status": job["status"],
                    "deduplicated": False,
                })

            return {
                "playlist_url": url,
                "total_videos": len(entries),
                "enqueued": sum(1 for r in results if not r.get("deduplicated") and r.get("job_id")),
                "already_completed": sum(1 for r in results if r.get("status") == "completed" and r.get("deduplicated")),
                "already_active": sum(1 for r in results if r.get("deduplicated") and r.get("job_id")),
                "videos": results,
            }

        @mcp.tool(annotations=_ro)
        def job_status(job_id: str) -> dict[str, Any]:
            job = self.jobs.get(job_id)
            if job is None:
                return {"error": "job_not_found", "job_id": job_id}
            if job["status"] in ACTIVE_STATUSES:
                self.jobs.increment_poll_count(job_id)
                job = self.jobs.get(job_id)
                poll_count = int(job.get("poll_count") or 0)
                poll_retry_after = min(5 * (2 ** (poll_count // 3)), 60)
                extras: dict[str, Any] = {"retry_after": poll_retry_after}
                if job.get("retry_after"):
                    extras["waiting_until"] = job["retry_after"]
                    extras["attempt"] = int(job.get("attempt") or 0)
                return {**job, **extras}
            return job

        @mcp.tool(annotations=_ro)
        def search(query: str, limit: int = 10) -> dict[str, Any]:
            return {
                "query": query,
                "results": self.transcripts.search(query=query, limit=limit),
            }

        @mcp.tool(annotations=_ro)
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

        @mcp.tool(annotations=_ro)
        def read_transcript(video_id: str) -> dict[str, Any]:
            """Read a transcript by video ID. Returns full speaker-diarized markdown.

            Args:
                video_id: The video ID to read

            Returns:
                Full markdown transcript with speaker labels and timestamps.
            """
            transcript = self.transcripts.get_by_video_id(video_id)
            if transcript is None:
                return {"error": "transcript_not_found", "video_id": video_id}

            base = Path(str(transcript["path"]))
            file_path = base / "transcript.md"
            content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            return {
                "video_id": video_id,
                "title": transcript.get("title"),
                "content": content,
            }

        @mcp.tool(annotations=_ro)
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

        @mcp.tool(annotations=_ro)
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

        @mcp.tool(annotations=_ro)
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
