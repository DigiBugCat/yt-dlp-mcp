from __future__ import annotations

import json
import subprocess
from typing import Any


class YouTubeInfoService:
    """Stateless service wrapping yt-dlp for search, metadata, and comments."""

    @staticmethod
    def _run_ytdlp(cmd: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=timeout
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "yt-dlp failed"
            raise RuntimeError(stderr)
        return completed

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        cmd = [
            "yt-dlp",
            f"ytsearch{limit}:{query}",
            "--flat-playlist",
            "--print",
            "%(id)s\t%(title)s\t%(uploader)s\t%(duration)s\t%(view_count)s",
            "--no-download",
            "--no-warnings",
            "--quiet",
        ]
        completed = self._run_ytdlp(cmd, timeout=15)

        results: list[dict[str, Any]] = []
        for line in completed.stdout.strip().splitlines():
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            video_id, title, channel, duration, view_count = parts
            results.append({
                "video_id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": channel,
                "duration": _safe_int(duration),
                "view_count": _safe_int(view_count),
            })
        return results

    _METADATA_KEYS = [
        "id", "title", "description", "channel", "channel_id", "channel_url",
        "uploader", "upload_date", "duration", "view_count", "like_count",
        "comment_count", "age_limit", "categories", "tags", "thumbnail",
        "webpage_url", "original_url", "language", "subtitles",
    ]

    def get_metadata(self, url: str) -> dict[str, Any]:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
            "--no-download",
            "--no-playlist",
            "--no-check-formats",
            url,
        ]
        completed = self._run_ytdlp(cmd, timeout=15)
        raw = json.loads(completed.stdout)
        return {k: raw[k] for k in self._METADATA_KEYS if k in raw}

    def extract_playlist(self, url: str) -> list[dict[str, Any]]:
        """Extract video entries from a playlist URL using --flat-playlist."""
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--print",
            "%(id)s\t%(title)s\t%(uploader)s\t%(duration)s\t%(url)s",
            "--no-download",
            "--no-warnings",
            "--quiet",
            url,
        ]
        completed = self._run_ytdlp(cmd, timeout=30)

        entries: list[dict[str, Any]] = []
        for line in completed.stdout.strip().splitlines():
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            video_id, title, uploader, duration, video_url = parts
            if not video_id or video_id == "NA":
                continue
            entries.append({
                "video_id": video_id,
                "title": title if title != "NA" else None,
                "channel": uploader if uploader != "NA" else None,
                "duration": _safe_int(duration),
                "url": video_url if video_url != "NA" else f"https://www.youtube.com/watch?v={video_id}",
            })
        return entries

    def get_comments(
        self, url: str, limit: int = 20, sort: str = "top"
    ) -> list[dict[str, Any]]:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
            "--skip-download",
            "--no-playlist",
            "--write-comments",
            "--extractor-args",
            f"youtube:comment_sort={sort};max_comments={limit},all,all",
            url,
        ]
        completed = self._run_ytdlp(cmd, timeout=120)
        data = json.loads(completed.stdout)

        raw_comments = data.get("comments") or []
        comments: list[dict[str, Any]] = []
        for c in raw_comments:
            comments.append({
                "id": c.get("id"),
                "text": c.get("text"),
                "author": c.get("author"),
                "author_id": c.get("author_id"),
                "like_count": c.get("like_count", 0),
                "is_pinned": c.get("is_pinned", False),
                "is_favorited": c.get("is_favorited", False),
                "parent": c.get("parent", "root"),
                "timestamp": c.get("timestamp"),
            })
        return comments


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
