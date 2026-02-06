from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

JobStatus = Literal["queued", "downloading", "transcribing", "completed", "failed"]
TranscriptFormat = Literal["markdown", "json", "text"]


@dataclass(slots=True)
class DownloadResult:
    metadata: dict[str, object]
    audio_path: str


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(slots=True)
class TranscriptResult:
    text: str
    segments: list[TranscriptSegment]
    language: str | None = None
