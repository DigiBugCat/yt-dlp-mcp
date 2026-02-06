from pathlib import Path

from yt_dlp_mcp.db.database import Database
from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.services.storage import StorageService
from yt_dlp_mcp.types import DownloadResult, TranscriptResult, TranscriptSegment
from yt_dlp_mcp.worker import BackgroundWorker


class FakeDownloader:
    def __init__(self, work_root: Path) -> None:
        self.work_root = work_root
        self.work_root.mkdir(parents=True, exist_ok=True)

    def download(self, *, url: str, job_id: str) -> DownloadResult:
        job_dir = self.work_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        audio_path = job_dir / "vid1.mp3"
        audio_path.write_bytes(b"fake-audio")
        return DownloadResult(
            metadata={
                "id": "vid1",
                "title": "Video 1",
                "channel": "Channel A",
                "extractor_key": "YouTube",
            },
            audio_path=str(audio_path),
        )


class FakeTranscriber:
    def transcribe(self, _: Path) -> TranscriptResult:
        return TranscriptResult(
            text="hello world",
            segments=[TranscriptSegment(start=0.0, end=1.0, text="hello world", speaker="A")],
            language="en",
        )


def test_worker_processes_job(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.sqlite3")
    jobs = JobsRepository(db)
    transcripts = TranscriptsRepository(db)
    downloader = FakeDownloader(tmp_path / "work")
    transcriber = FakeTranscriber()
    storage = StorageService(tmp_path / "data")

    worker = BackgroundWorker(
        jobs=jobs,
        transcripts=transcripts,
        downloader=downloader,  # type: ignore[arg-type]
        transcriber=transcriber,  # type: ignore[arg-type]
        storage=storage,
        poll_interval_seconds=5,
    )

    job = jobs.enqueue("https://example.com/video", "https://example.com/video")
    claimed = jobs.claim_next()
    assert claimed is not None

    worker._process_job(
        job_id=str(job["id"]),
        url="https://example.com/video",
        normalized_url="https://example.com/video",
    )

    status = jobs.get(str(job["id"]))
    assert status is not None
    assert status["status"] == "completed"

    saved = transcripts.get_by_video_id("vid1")
    assert saved is not None
    assert Path(str(saved["path"])).exists()
