from __future__ import annotations

import logging
from pathlib import Path

import httpx

from yt_dlp_mcp.types import TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)

DEFAULT_PARAKEET_URL = "http://parakeet:8000"


class LocalTranscriber:
    """Transcription client that delegates to an external Parakeet + pyannote service.

    Expects an OpenAI Whisper-compatible API (parakeet-v3-diarized or similar)
    running at the configured URL.
    """

    def __init__(self, *, parakeet_url: str = DEFAULT_PARAKEET_URL) -> None:
        self._base_url = parakeet_url.rstrip("/")
        logger.info("LocalTranscriber targeting %s", self._base_url)

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not audio_path.exists():
            raise RuntimeError(f"Audio file not found: {audio_path}")

        logger.info("Sending %s to parakeet service at %s", audio_path.name, self._base_url)

        url = f"{self._base_url}/v1/audio/transcriptions"
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {
                "response_format": "verbose_json",
                "timestamp_granularities": "segment",
                "diarize": "true",
            }
            with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
                response = client.post(url, files=files, data=data)

        if response.status_code >= 400:
            body = response.text[:500]
            raise RuntimeError(f"Parakeet service error ({response.status_code}): {body}")

        payload = response.json()
        text = str(payload.get("text", "")).strip()
        language = payload.get("language")

        segments: list[TranscriptSegment] = []
        for seg in payload.get("segments") or []:
            seg_text = str(seg.get("text", "")).strip()
            if not seg_text:
                continue
            segments.append(
                TranscriptSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=seg_text,
                    speaker=seg.get("speaker"),
                )
            )

        logger.info(
            "Parakeet returned %d chars, %d segments, language=%s",
            len(text), len(segments), language,
        )
        return TranscriptResult(text=text, segments=segments, language=language)
