from __future__ import annotations

from typing import Any

from yt_dlp_mcp.db.database import Database


class TranscriptsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_by_video_id(self, video_id: str) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT * FROM transcripts WHERE video_id = ? LIMIT 1",
            (video_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def get_by_normalized_url(self, normalized_url: str) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT * FROM transcripts WHERE normalized_url = ? LIMIT 1",
            (normalized_url,),
        ).fetchone()
        return dict(row) if row is not None else None

    def upsert(
        self,
        *,
        video_id: str,
        normalized_url: str,
        url: str,
        path: str,
        transcript_text: str,
        title: str | None,
        channel: str | None,
        platform: str | None,
        duration: float | None,
        upload_date: str | None,
        description: str | None,
        thumbnail: str | None,
        view_count: int | None,
        speaker_count: int | None,
        word_count: int | None,
        confidence: float | None,
    ) -> None:
        with self.db.lock:
            self.db.conn.execute(
                """
                INSERT INTO transcripts(
                    video_id, normalized_url, url, title, channel, platform, duration,
                    upload_date, description, thumbnail, view_count,
                    speaker_count, word_count, confidence, transcribed_at, path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    normalized_url = excluded.normalized_url,
                    url = excluded.url,
                    title = excluded.title,
                    channel = excluded.channel,
                    platform = excluded.platform,
                    duration = excluded.duration,
                    upload_date = excluded.upload_date,
                    description = excluded.description,
                    thumbnail = excluded.thumbnail,
                    view_count = excluded.view_count,
                    speaker_count = excluded.speaker_count,
                    word_count = excluded.word_count,
                    confidence = excluded.confidence,
                    transcribed_at = datetime('now'),
                    path = excluded.path
                """,
                (
                    video_id,
                    normalized_url,
                    url,
                    title,
                    channel,
                    platform,
                    duration,
                    upload_date,
                    description,
                    thumbnail,
                    view_count,
                    speaker_count,
                    word_count,
                    confidence,
                    path,
                ),
            )
            self.db.conn.execute("DELETE FROM transcripts_fts WHERE video_id = ?", (video_id,))
            self.db.conn.execute(
                """
                INSERT INTO transcripts_fts(video_id, title, channel, description, transcript_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    title or "",
                    channel or "",
                    description or "",
                    transcript_text,
                ),
            )
            self.db.conn.commit()

    def list_transcripts(
        self,
        *,
        platform: str | None = None,
        channel: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM transcripts"
        clauses: list[str] = []
        params: list[Any] = []

        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        if channel:
            clauses.append("channel = ?")
            params.append(channel)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY transcribed_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))

        rows = self.db.conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.db.conn.execute(
            """
            SELECT
                t.video_id,
                t.title,
                t.channel,
                t.platform,
                t.path,
                t.transcribed_at,
                snippet(transcripts_fts, 4, '[', ']', ' ... ', 20) AS snippet,
                bm25(transcripts_fts) AS score
            FROM transcripts_fts
            JOIN transcripts AS t ON t.video_id = transcripts_fts.video_id
            WHERE transcripts_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, max(1, min(limit, 50))),
        ).fetchall()
        return [dict(row) for row in rows]
