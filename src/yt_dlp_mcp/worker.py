from __future__ import annotations

import logging
import shutil
from pathlib import Path
from threading import Event, Thread

from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.services.downloader import Downloader
from yt_dlp_mcp.services.storage import StorageService
from yt_dlp_mcp.services.transcriber import AssemblyAITranscriber

logger = logging.getLogger(__name__)


class BackgroundWorker:
    def __init__(
        self,
        *,
        jobs: JobsRepository,
        transcripts: TranscriptsRepository,
        downloader: Downloader,
        transcriber: AssemblyAITranscriber,
        storage: StorageService,
        poll_interval_seconds: int,
    ) -> None:
        self.jobs = jobs
        self.transcripts = transcripts
        self.downloader = downloader
        self.transcriber = transcriber
        self.storage = storage
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = Event()
        self._thread = Thread(target=self._run_loop, name="yt-dlp-mcp-worker", daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self, timeout_seconds: float = 10.0) -> None:
        self._stop_event.set()
        self._thread.join(timeout=timeout_seconds)

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive() and not self._stop_event.is_set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.jobs.claim_next()
            if job is None:
                self._stop_event.wait(self.poll_interval_seconds)
                continue

            job_id = str(job["id"])
            try:
                logger.info("Processing job %s", job_id)
                self._process_job(job_id=job_id, url=str(job["url"]), normalized_url=str(job["normalized_url"]))
                logger.info("Completed job %s", job_id)
            except Exception as exc:  # pylint: disable=broad-except
                message = str(exc).strip() or "Unknown worker error"
                logger.exception("Job %s failed: %s", job_id, message)
                self.jobs.mark_failed(job_id, message[:2000])

    def _process_job(self, *, job_id: str, url: str, normalized_url: str) -> None:
        download = self.downloader.download(url=url, job_id=job_id)
        self.jobs.set_status(job_id, "transcribing")

        audio_path = Path(download.audio_path)
        transcript_result = self.transcriber.transcribe(audio_path)

        persisted = self.storage.persist(
            metadata=download.metadata,
            normalized_url=normalized_url,
            source_url=url,
            transcript=transcript_result,
            temp_audio_path=audio_path,
        )

        word_count = len(transcript_result.text.split())
        speakers = {segment.speaker for segment in transcript_result.segments if segment.speaker}

        self.transcripts.upsert(
            video_id=str(persisted["video_id"]),
            normalized_url=normalized_url,
            url=url,
            path=str(persisted["path"]),
            transcript_text=transcript_result.text,
            title=self._as_str(download.metadata.get("title")),
            channel=self._as_str(download.metadata.get("channel")),
            platform=self._as_str(download.metadata.get("extractor_key")),
            duration=self._as_float(download.metadata.get("duration")),
            upload_date=self._as_str(download.metadata.get("upload_date")),
            description=self._as_str(download.metadata.get("description")),
            thumbnail=self._as_str(download.metadata.get("thumbnail")),
            view_count=self._as_int(download.metadata.get("view_count")),
            speaker_count=len(speakers) if speakers else None,
            word_count=word_count,
            confidence=None,
        )
        self.jobs.mark_completed(job_id, str(persisted["video_id"]), str(persisted["path"]))

        work_dir = self.downloader.work_root / job_id
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def _as_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_float(value: object) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
