from __future__ import annotations

import logging
from pathlib import Path

from yt_dlp_mcp.services.transcriber import AssemblyAITranscriber
from yt_dlp_mcp.types import TranscriptResult

logger = logging.getLogger(__name__)


class FallbackTranscriber:
    """Tries the local Parakeet service first, falls back to AssemblyAI on failure."""

    def __init__(
        self,
        *,
        local: object,
        fallback: AssemblyAITranscriber | None = None,
    ) -> None:
        self.local = local
        self.fallback = fallback

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        try:
            return self.local.transcribe(audio_path)
        except Exception as exc:
            if self.fallback is None:
                raise
            logger.warning(
                "Parakeet service failed (%s), falling back to AssemblyAI",
                exc,
            )
            return self.fallback.transcribe(audio_path)
