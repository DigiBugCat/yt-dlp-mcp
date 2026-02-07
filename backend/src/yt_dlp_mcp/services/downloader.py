from __future__ import annotations

import json
import subprocess
from pathlib import Path

from yt_dlp_mcp.types import DownloadResult


class Downloader:
    def __init__(self, work_root: Path) -> None:
        self.work_root = work_root
        self.work_root.mkdir(parents=True, exist_ok=True)

    def download(self, *, url: str, job_id: str) -> DownloadResult:
        job_dir = self.work_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(job_dir / "%(id)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--print-json",
            "--no-playlist",
            "--no-warnings",
            "-f",
            "bestaudio",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "-o",
            output_template,
            url,
        ]

        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "yt-dlp failed"
            raise RuntimeError(stderr)

        metadata = self._parse_last_json_line(completed.stdout)
        video_id = str(metadata.get("id", "")).strip()
        if not video_id:
            raise RuntimeError("yt-dlp did not return video ID")

        audio_path = job_dir / f"{video_id}.mp3"
        if not audio_path.exists():
            candidates = sorted(job_dir.glob("*.mp3"))
            if not candidates:
                raise RuntimeError("Audio file was not produced by yt-dlp")
            audio_path = candidates[0]

        return DownloadResult(metadata=metadata, audio_path=str(audio_path))

    @staticmethod
    def _parse_last_json_line(stdout: str) -> dict[str, object]:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("{") and line.endswith("}"):
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        return value
                except json.JSONDecodeError:
                    continue
        raise RuntimeError("Could not parse yt-dlp metadata JSON")
