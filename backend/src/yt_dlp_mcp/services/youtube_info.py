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
            "--print",
            "%(id)s\t%(title)s\t%(uploader)s\t%(duration)s\t%(view_count)s",
            "--no-download",
            "--no-warnings",
            "--quiet",
        ]
        completed = self._run_ytdlp(cmd, timeout=30)

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

    def get_metadata(self, url: str) -> dict[str, Any]:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
            "--no-download",
            "--no-playlist",
            url,
        ]
        completed = self._run_ytdlp(cmd, timeout=30)
        return json.loads(completed.stdout)

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
