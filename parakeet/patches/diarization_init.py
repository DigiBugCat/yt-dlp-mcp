from typing import List, Optional
import logging

import torch
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SORTFORMER_MODEL = "nvidia/diar_streaming_sortformer_4spk-v2.1"


class SpeakerSegment(BaseModel):
    start: float
    end: float
    speaker: str


class DiarizationResult(BaseModel):
    segments: List[SpeakerSegment]
    num_speakers: int


class Diarizer:
    """Speaker diarization using NVIDIA Streaming Sortformer v2.1."""

    def __init__(self, access_token: Optional[str] = None):
        self.model = None
        self._initialize()

    def _initialize(self):
        try:
            from nemo.collections.asr.models import SortformerEncLabelModel

            logger.info("Loading Sortformer model: %s", _SORTFORMER_MODEL)
            model = SortformerEncLabelModel.from_pretrained(_SORTFORMER_MODEL)
            model.eval()

            # Configure streaming — high-latency config is fine for offline batch use,
            # gives best accuracy with minimal compute.
            model.sortformer_modules.chunk_len = 340
            model.sortformer_modules.chunk_right_context = 40
            model.sortformer_modules.fifo_len = 40
            model.sortformer_modules.spkcache_update_period = 300

            self.model = model
            logger.info("Sortformer diarization model loaded")

        except Exception as e:
            logger.error("Failed to load Sortformer model: %s", e)

    def diarize(self, audio_path: str, num_speakers: Optional[int] = None) -> DiarizationResult:
        if self.model is None:
            logger.error("Diarization model not loaded")
            return DiarizationResult(segments=[], num_speakers=0)

        try:
            predicted_segments = self.model.diarize(
                audio=[audio_path], batch_size=1
            )

            segments = []
            speakers = set()

            for seg in predicted_segments[0]:
                # Sortformer returns strings like "0.240 16.240 speaker_0"
                parts = seg.strip().split()
                start = float(parts[0])
                end = float(parts[1])
                speaker_label = parts[2] if len(parts) > 2 else "speaker_0"
                segments.append(SpeakerSegment(
                    start=start,
                    end=end,
                    speaker=speaker_label,
                ))
                speakers.add(speaker_label)

            segments.sort(key=lambda x: x.start)
            logger.info("Sortformer found %d speakers, %d segments", len(speakers), len(segments))
            return DiarizationResult(segments=segments, num_speakers=len(speakers))

        except Exception as e:
            logger.error("Diarization failed: %s", e)
            return DiarizationResult(segments=[], num_speakers=0)

    def merge_with_transcription(self, diarization: DiarizationResult, transcription_segments: list) -> list:
        if not diarization.segments:
            return transcription_segments

        for segment in transcription_segments:
            start = segment.start
            end = segment.end

            overlapping = []
            for spk_segment in diarization.segments:
                overlap_start = max(start, spk_segment.start)
                overlap_end = min(end, spk_segment.end)
                if overlap_end > overlap_start:
                    overlapping.append((spk_segment.speaker, overlap_end - overlap_start))

            if overlapping:
                overlapping.sort(key=lambda x: x[1], reverse=True)
                setattr(segment, "speaker", overlapping[0][0])

        return transcription_segments
