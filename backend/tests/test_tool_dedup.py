from pathlib import Path
from typing import Any

from yt_dlp_mcp.db.database import Database
from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.mcp_tools import ToolRegistry


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, fn: Any) -> Any:
        self.tools[fn.__name__] = fn
        return fn


def test_transcribe_returns_existing_transcript(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.sqlite3")
    jobs = JobsRepository(db)
    transcripts = TranscriptsRepository(db)

    transcripts.upsert(
        video_id="abc",
        normalized_url="https://youtube.com/watch?v=abc",
        url="https://youtube.com/watch?v=abc",
        path="/tmp/transcript/abc",
        transcript_text="sample",
        title="A",
        channel="B",
        platform="YouTube",
        duration=None,
        upload_date=None,
        description=None,
        thumbnail=None,
        view_count=None,
        speaker_count=None,
        word_count=1,
        confidence=None,
    )

    mcp = DummyMCP()
    ToolRegistry(jobs, transcripts).register(mcp)  # type: ignore[arg-type]

    response = mcp.tools["transcribe"]("https://youtube.com/watch?v=abc")
    assert response["deduplicated"] is True
    assert response["status"] == "completed"
    assert response["video_id"] == "abc"
