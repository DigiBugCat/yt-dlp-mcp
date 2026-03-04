from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

import torch

from yt_dlp_mcp.services.transcriber import UnsupportedLanguageError
from yt_dlp_mcp.types import TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)

# Parakeet TDT 0.6b v3 supported languages (ISO 639-1 codes).
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
    "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de",
    "el", "hu", "it", "lv", "lt", "mt", "pl", "pt", "ro", "sk",
    "sl", "es", "sv", "ru", "uk",
})

# Unicode script categories used by Parakeet-supported languages.
_EUROPEAN_SCRIPTS: frozenset[str] = frozenset({"LATIN", "CYRILLIC", "GREEK"})

_PARAKEET_MODEL = "nvidia/parakeet-tdt-0.6b-v3"
_PYANNOTE_PIPELINE = "pyannote/speaker-diarization-community-1"


class LocalTranscriber:
    """GPU-accelerated transcription using Parakeet ASR + pyannote diarization."""

    def __init__(self, *, huggingface_token: str | None = None) -> None:
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("LocalTranscriber using device: %s", self._device)

        self._asr_model = self._load_asr_model()
        self._diarization_pipeline = self._load_diarization_pipeline(huggingface_token)

    def _load_asr_model(self) -> object:
        import nemo.collections.asr as nemo_asr  # noqa: PLC0415

        logger.info("Loading Parakeet model: %s", _PARAKEET_MODEL)
        model = nemo_asr.models.ASRModel.from_pretrained(model_name=_PARAKEET_MODEL)
        # Enable local attention for long audio (up to ~3 hours).
        model.change_attention_model(
            self_attention_model="rel_pos_local_attn",
            att_context_size=[256, 256],
        )
        model.eval()
        return model

    def _load_diarization_pipeline(self, huggingface_token: str | None) -> object:
        from pyannote.audio import Pipeline  # noqa: PLC0415

        logger.info("Loading pyannote pipeline: %s", _PYANNOTE_PIPELINE)
        kwargs: dict[str, str] = {}
        if huggingface_token:
            kwargs["use_auth_token"] = huggingface_token
        pipeline = Pipeline.from_pretrained(_PYANNOTE_PIPELINE, **kwargs)
        pipeline.to(self._device)
        return pipeline

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not audio_path.exists():
            raise RuntimeError(f"Audio file not found: {audio_path}")

        audio_str = str(audio_path)
        logger.info("Transcribing with Parakeet: %s", audio_path.name)

        # Run ASR with timestamps.
        asr_output = self._asr_model.transcribe([audio_str], timestamps=True)
        hypothesis = asr_output[0]

        text = str(hypothesis.text).strip()
        detected_lang = self._detect_language(hypothesis, text)
        if detected_lang and detected_lang not in SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(detected_lang)
        if not detected_lang and not self._text_uses_european_scripts(text):
            raise UnsupportedLanguageError("unknown")

        # Run speaker diarization.
        logger.info("Running pyannote diarization: %s", audio_path.name)
        diarization = self._diarization_pipeline(audio_str)

        # Build speaker timeline for alignment.
        speaker_turns = self._extract_speaker_turns(diarization)

        # Extract ASR segments with timestamps.
        raw_segments = hypothesis.timestamp.get("segment", []) if hypothesis.timestamp else []
        segments = self._align_segments(raw_segments, speaker_turns)

        language = detected_lang or "en"
        return TranscriptResult(text=text, segments=segments, language=language)

    @staticmethod
    def _detect_language(hypothesis: object, text: str) -> str | None:
        """Try to extract the detected language from the NeMo hypothesis."""
        # NeMo multilingual models may expose language on the hypothesis object.
        lang = getattr(hypothesis, "lang", None) or getattr(hypothesis, "language", None)
        if lang and isinstance(lang, str):
            code = lang.strip().lower()[:2]
            return code if code else None
        return None

    @staticmethod
    def _text_uses_european_scripts(text: str) -> bool:
        """Heuristic: check if the transcribed text primarily uses European scripts."""
        if not text:
            return True  # Empty text — don't block on it.

        european = 0
        total = 0
        for ch in text:
            if not ch.isalpha():
                continue
            total += 1
            try:
                script = unicodedata.name(ch, "").split()[0]
            except (ValueError, IndexError):
                continue
            if script in _EUROPEAN_SCRIPTS:
                european += 1

        if total == 0:
            return True
        return (european / total) >= 0.7

    @staticmethod
    def _extract_speaker_turns(diarization: object) -> list[tuple[float, float, str]]:
        """Extract (start, end, speaker) tuples from pyannote annotation."""
        turns: list[tuple[float, float, str]] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append((turn.start, turn.end, str(speaker)))
        return turns

    @staticmethod
    def _align_segments(
        raw_segments: list[dict[str, object]],
        speaker_turns: list[tuple[float, float, str]],
    ) -> list[TranscriptSegment]:
        """Align ASR segments with diarization speaker turns by maximum overlap."""
        segments: list[TranscriptSegment] = []
        for seg in raw_segments:
            text = str(seg.get("segment") or seg.get("text") or "").strip()
            if not text:
                continue

            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            speaker = _find_best_speaker(start, end, speaker_turns)
            segments.append(TranscriptSegment(start=start, end=end, text=text, speaker=speaker))

        return segments


def _find_best_speaker(
    seg_start: float,
    seg_end: float,
    speaker_turns: list[tuple[float, float, str]],
) -> str | None:
    """Find the speaker with maximum overlap for a given time range."""
    if not speaker_turns:
        return None

    best_speaker: str | None = None
    best_overlap = 0.0

    for turn_start, turn_end, speaker in speaker_turns:
        overlap_start = max(seg_start, turn_start)
        overlap_end = min(seg_end, turn_end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = speaker

    return best_speaker
