from pathlib import Path

from yt_dlp_mcp.db.database import Database
from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository


def test_job_lifecycle(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.sqlite3")
    jobs = JobsRepository(db)

    created = jobs.enqueue("https://example.com/v/1", "https://example.com/v/1")
    assert created["status"] == "queued"

    claimed = jobs.claim_next()
    assert claimed is not None
    assert claimed["status"] == "downloading"

    jobs.set_status(str(claimed["id"]), "transcribing")
    transcribing = jobs.get(str(claimed["id"]))
    assert transcribing is not None
    assert transcribing["status"] == "transcribing"

    jobs.mark_completed(str(claimed["id"]), "video1", "/tmp/video1")
    completed = jobs.get(str(claimed["id"]))
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["video_id"] == "video1"


def test_transcripts_search(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.sqlite3")
    repo = TranscriptsRepository(db)

    repo.upsert(
        video_id="vid1",
        normalized_url="https://example.com/1",
        url="https://example.com/1",
        path="/tmp/vid1",
        transcript_text="hello this is a transcription test",
        title="Demo title",
        channel="demo channel",
        platform="youtube",
        duration=12.3,
        upload_date="20250101",
        description="description text",
        thumbnail=None,
        view_count=1,
        speaker_count=1,
        word_count=6,
        confidence=None,
    )

    results = repo.search("transcription", limit=5)
    assert len(results) == 1
    assert results[0]["video_id"] == "vid1"
