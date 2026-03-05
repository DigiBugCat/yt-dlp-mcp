import os
import logging
import tempfile
from typing import List, Optional, Dict, Any, Union, Tuple

import torch
import numpy as np

from models import WhisperSegment, TranscriptionResponse

logger = logging.getLogger(__name__)

def load_model(model_id: str = "nvidia/parakeet-tdt-0.6b-v3"):
    try:
        from nemo.collections.asr.models import EncDecCTCModelBPE

        logger.info("Loading model %s", model_id)
        model = EncDecCTCModelBPE.from_pretrained(model_id)

        if torch.cuda.is_available():
            model = model.cuda()
            logger.info("Model loaded on GPU: %s", torch.cuda.get_device_name(0))
        else:
            logger.warning("CUDA not available, running on CPU (will be slow)")

        # Disable CUDA graph-based decoding — the cu_call API in cuda-python 12.9+
        # returns 5 values from cudaStreamGetCaptureInfo instead of the 6 that
        # NeMo 2.7's tdt_label_looping expects, causing a ValueError.
        from omegaconf import OmegaConf
        decoding_cfg = OmegaConf.create({
            "strategy": "greedy",
            "greedy": {"max_symbols": 10, "loop_labels": False},
        })
        model.change_decoding_strategy(decoding_cfg)
        logger.info("Decoding strategy set to greedy (loop_labels=False) to avoid CUDA graph bug")

        return model
    except Exception as e:
        logger.error("Error loading model: %s", e)
        raise

def _format_timestamp(seconds: float, always_include_hours: bool = False,
                     decimal_marker: str = '.') -> str:
    hours = int(seconds / 3600)
    seconds = seconds % 3600
    minutes = int(seconds / 60)
    seconds = seconds % 60

    hours_marker = f"{hours}:" if always_include_hours or hours > 0 else ""

    if decimal_marker == ',':
        return f"{hours_marker}{minutes:02d}:{seconds:06.3f}".replace('.', decimal_marker)
    else:
        return f"{hours_marker}{minutes:02d}:{seconds:06.3f}"

def format_srt(segments: List[WhisperSegment]) -> str:
    srt_content = ""
    for i, segment in enumerate(segments):
        segment_id = i + 1
        start = _format_timestamp(segment.start, always_include_hours=True, decimal_marker=',')
        end = _format_timestamp(segment.end, always_include_hours=True, decimal_marker=',')
        text = segment.text.strip().replace('-->', '->')
        speaker_prefix = f"[{segment.speaker}] " if hasattr(segment, "speaker") and segment.speaker else ""
        srt_content += f"{segment_id}\n{start} --> {end}\n{speaker_prefix}{text}\n\n"
    return srt_content.strip()

def format_vtt(segments: List[WhisperSegment]) -> str:
    vtt_content = "WEBVTT\n\n"
    for i, segment in enumerate(segments):
        start = _format_timestamp(segment.start, always_include_hours=True)
        end = _format_timestamp(segment.end, always_include_hours=True)
        text = segment.text.strip()
        speaker_prefix = f"<v {segment.speaker}>" if hasattr(segment, "speaker") and segment.speaker else ""
        vtt_content += f"{start} --> {end}\n{speaker_prefix}{text}\n\n"
    return vtt_content.strip()

def transcribe_audio_chunk(model, audio_path: str, language: Optional[str] = None,
                          word_timestamps: bool = False) -> Tuple[str, List[WhisperSegment]]:
    try:
        with torch.no_grad():
            transcription = model.transcribe([audio_path], timestamps=True)

        if not transcription or len(transcription) == 0:
            logger.warning("No transcription generated for %s", audio_path)
            return "", []

        result = transcription[0]
        text = result.text

        segments = []

        if hasattr(result, 'timestamp') and result.timestamp and 'segment' in result.timestamp:
            for i, stamp in enumerate(result.timestamp['segment']):
                # Handle both dict and tuple/list formats from different NeMo versions
                if isinstance(stamp, dict):
                    seg_start = stamp.get('start', 0.0)
                    seg_end = stamp.get('end', 0.0)
                    seg_text = stamp.get('segment', stamp.get('text', ''))
                else:
                    # Some NeMo versions return tuples/lists
                    try:
                        seg_start, seg_end, seg_text = stamp[0], stamp[1], stamp[-1]
                    except (IndexError, TypeError):
                        logger.warning("Unexpected segment format: %s", type(stamp))
                        continue

                segments.append(WhisperSegment(
                    id=i,
                    start=float(seg_start),
                    end=float(seg_end),
                    text=str(seg_text),
                ))
        else:
            segments.append(WhisperSegment(
                id=0,
                start=0.0,
                end=len(text.split()) / 2.0,
                text=text,
            ))

        return text, segments

    except Exception as e:
        logger.error("Error transcribing audio chunk: %s", e)
        return "", []
