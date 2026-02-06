from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from yt_dlp_mcp.types import TranscriptResult


def _sanitize_path_component(value: str, fallback: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    clean = clean.strip("._")
    return clean or fallback


def _format_timestamp(seconds: float) -> str:
    whole = int(max(seconds, 0))
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def to_markdown(result: TranscriptResult, title: str | None = None) -> str:
    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    if not result.segments:
        lines.append(result.text)
        return "\n".join(lines).strip() + "\n"

    for segment in result.segments:
        label = segment.speaker or "Speaker"
        timestamp = _format_timestamp(segment.start)
        lines.append(f"- [{timestamp}] **{label}**: {segment.text}")

    return "\n".join(lines).strip() + "\n"


class StorageService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.transcripts_root = data_dir / "transcripts"
        self.transcripts_root.mkdir(parents=True, exist_ok=True)

    def persist(
        self,
        *,
        metadata: dict[str, object],
        normalized_url: str,
        source_url: str,
        transcript: TranscriptResult,
        temp_audio_path: Path,
    ) -> dict[str, object]:
        video_id = str(metadata.get("id") or "unknown")
        platform = _sanitize_path_component(str(metadata.get("extractor_key") or "unknown"), "unknown")
        channel = _sanitize_path_component(str(metadata.get("channel") or "unknown"), "unknown")
        video_dir = self.transcripts_root / platform / channel / _sanitize_path_component(video_id, "unknown")
        video_dir.mkdir(parents=True, exist_ok=True)

        metadata_with_url = dict(metadata)
        metadata_with_url["normalized_url"] = normalized_url
        metadata_with_url["source_url"] = source_url

        metadata_path = video_dir / "metadata.json"
        transcript_json_path = video_dir / "transcript.json"
        transcript_md_path = video_dir / "transcript.md"
        transcript_txt_path = video_dir / "transcript.txt"
        audio_dest_path = video_dir / "audio.mp3"

        metadata_path.write_text(json.dumps(metadata_with_url, indent=2, sort_keys=True), encoding="utf-8")

        transcript_payload = {
            "text": transcript.text,
            "language": transcript.language,
            "segments": [
                {
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": segment.speaker,
                    "text": segment.text,
                }
                for segment in transcript.segments
            ],
        }
        transcript_json_path.write_text(
            json.dumps(transcript_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        title = str(metadata.get("title")) if metadata.get("title") else None
        markdown = to_markdown(transcript, title=title)
        transcript_md_path.write_text(markdown, encoding="utf-8")
        transcript_txt_path.write_text((transcript.text or "").strip() + "\n", encoding="utf-8")

        shutil.move(str(temp_audio_path), str(audio_dest_path))

        return {
            "video_id": video_id,
            "platform": platform,
            "channel": channel,
            "path": str(video_dir),
            "metadata_path": str(metadata_path),
            "transcript_md_path": str(transcript_md_path),
            "transcript_json_path": str(transcript_json_path),
            "transcript_txt_path": str(transcript_txt_path),
            "audio_path": str(audio_dest_path),
            "normalized_url": normalized_url,
            "source_url": source_url,
        }
