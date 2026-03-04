from __future__ import annotations

import logging
from pathlib import Path

from yt_dlp_mcp.services.transcriber import AssemblyAITranscriber, UnsupportedLanguageError
from yt_dlp_mcp.types import TranscriptResult

logger = logging.getLogger(__name__)


class FallbackTranscriber:
    """Tries the local GPU transcriber first, falls back to AssemblyAI for unsupported languages."""

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
        except UnsupportedLanguageError as exc:
            if self.fallback is None:
                raise RuntimeError(
                    f"Detected unsupported language '{exc.language}' "
                    "but no ASSEMBLYAI_API_KEY configured for fallback"
                ) from exc
            logger.info(
                "Language '%s' not supported by Parakeet, falling back to AssemblyAI",
                exc.language,
            )
            return self.fallback.transcribe(audio_path)
