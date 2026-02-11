from __future__ import annotations

import uuid
from typing import Any

from yt_dlp_mcp.db.database import Database

ACTIVE_STATUSES = ("queued", "downloading", "transcribing")


class JobsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def enqueue(self, url: str, normalized_url: str) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        with self.db.lock:
            self.db.conn.execute(
                """
                INSERT INTO jobs(id, url, normalized_url, status)
                VALUES (?, ?, ?, 'queued')
                """,
                (job_id, url, normalized_url),
            )
            self.db.conn.commit()

        job = self.get(job_id)
        if job is None:
            raise RuntimeError("Failed to create job")
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = self.db.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row is not None else None

    def find_active_by_normalized_url(self, normalized_url: str) -> dict[str, Any] | None:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        row = self.db.conn.execute(
            f"""
            SELECT * FROM jobs
            WHERE normalized_url = ? AND status IN ({placeholders})
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (normalized_url, *ACTIVE_STATUSES),
        ).fetchone()
        return dict(row) if row is not None else None

    def claim_next(self) -> dict[str, Any] | None:
        with self.db.lock:
            self.db.conn.execute("BEGIN IMMEDIATE")
            row = self.db.conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                self.db.conn.commit()
                return None

            job_id = row["id"]
            self.db.conn.execute(
                """
                UPDATE jobs
                SET status = 'downloading', started_at = datetime('now')
                WHERE id = ?
                """,
                (job_id,),
            )
            self.db.conn.commit()

        return self.get(str(job_id))

    def set_status(self, job_id: str, status: str) -> None:
        with self.db.lock:
            self.db.conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
            self.db.conn.commit()

    def mark_completed(self, job_id: str, video_id: str, result_path: str) -> None:
        with self.db.lock:
            self.db.conn.execute(
                """
                UPDATE jobs
                SET status = 'completed', completed_at = datetime('now'), video_id = ?, result_path = ?, error = NULL
                WHERE id = ?
                """,
                (video_id, result_path, job_id),
            )
            self.db.conn.commit()

    def increment_poll_count(self, job_id: str) -> int:
        """Increment poll_count and return the new value."""
        with self.db.lock:
            self.db.conn.execute(
                "UPDATE jobs SET poll_count = poll_count + 1 WHERE id = ?",
                (job_id,),
            )
            self.db.conn.commit()
        row = self.db.conn.execute(
            "SELECT poll_count FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return int(row["poll_count"]) if row else 0

    def mark_failed(self, job_id: str, error: str) -> None:
        with self.db.lock:
            self.db.conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', completed_at = datetime('now'), error = ?
                WHERE id = ?
                """,
                (error, job_id),
            )
            self.db.conn.commit()
