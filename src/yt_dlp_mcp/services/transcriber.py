from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from yt_dlp_mcp.types import TranscriptResult, TranscriptSegment


class AssemblyAITranscriber:
    def __init__(
        self,
        api_key: str,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 600.0,
        max_wait_seconds: float = 3600.0,
    ) -> None:
        self.api_key = api_key
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.max_wait_seconds = max_wait_seconds
        self.base_url = "https://api.assemblyai.com/v2"

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not audio_path.exists():
            raise RuntimeError(f"Audio file not found: {audio_path}")

        headers = {"authorization": self.api_key}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            audio_url = self._upload_audio(client, headers, audio_path)
            transcript_id = self._start_transcript(client, headers, audio_url)
            payload = self._poll_transcript(client, headers, transcript_id)

        text = str(payload.get("text") or "").strip()
        utterances = payload.get("utterances")
        segments = self._extract_segments(utterances)
        if not text and segments:
            text = "\n".join(segment.text for segment in segments).strip()

        language = payload.get("language_code") or payload.get("language")
        language_value = str(language) if language is not None else None

        return TranscriptResult(text=text, segments=segments, language=language_value)

    def _upload_audio(self, client: httpx.Client, headers: dict[str, str], audio_path: Path) -> str:
        upload_url = f"{self.base_url}/upload"
        with audio_path.open("rb") as audio_stream:
            response = client.post(upload_url, headers=headers, content=audio_stream)
        if response.status_code >= 400:
            raise RuntimeError(
                f"AssemblyAI upload failed ({response.status_code}): {response.text[:400]}"
            )

        payload = response.json()
        uploaded = payload.get("upload_url")
        if not uploaded:
            raise RuntimeError("AssemblyAI upload response missing upload_url")
        return str(uploaded)

    def _start_transcript(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        audio_url: str,
    ) -> str:
        transcript_url = f"{self.base_url}/transcript"
        request_payload = {
            "audio_url": audio_url,
            "speaker_labels": True,
            "punctuate": True,
            "format_text": True,
        }
        response = client.post(transcript_url, headers=headers, json=request_payload)
        if response.status_code >= 400:
            raise RuntimeError(
                f"AssemblyAI transcript create failed ({response.status_code}): {response.text[:400]}"
            )

        payload = response.json()
        transcript_id = payload.get("id")
        if not transcript_id:
            raise RuntimeError("AssemblyAI transcript response missing id")
        return str(transcript_id)

    def _poll_transcript(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        transcript_id: str,
    ) -> dict[str, Any]:
        transcript_url = f"{self.base_url}/transcript/{transcript_id}"
        started = time.monotonic()
        while True:
            response = client.get(transcript_url, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"AssemblyAI transcript poll failed ({response.status_code}): {response.text[:400]}"
                )

            payload = response.json()
            status = str(payload.get("status") or "").lower()
            if status == "completed":
                return dict(payload)
            if status == "error":
                message = payload.get("error") or "AssemblyAI reported error status"
                raise RuntimeError(str(message))

            if time.monotonic() - started >= self.max_wait_seconds:
                raise RuntimeError("AssemblyAI transcription polling timed out")

            time.sleep(self.poll_interval_seconds)

    def _extract_segments(self, utterances: object) -> list[TranscriptSegment]:
        if not isinstance(utterances, list):
            return []

        segments: list[TranscriptSegment] = []
        for item in utterances:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = self._ms_to_seconds(item.get("start"))
            end = self._ms_to_seconds(item.get("end"))
            speaker = item.get("speaker")
            speaker_label = str(speaker) if speaker is not None else None
            segments.append(
                TranscriptSegment(start=start, end=end, text=text, speaker=speaker_label)
            )
        return segments

    @staticmethod
    def _ms_to_seconds(value: object) -> float:
        try:
            return float(str(value)) / 1000.0 if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
