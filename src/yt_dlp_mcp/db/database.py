from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def lock(self) -> Lock:
        return self._lock

    def _initialize(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY,
                  url TEXT NOT NULL,
                  normalized_url TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'queued',
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  started_at TEXT,
                  completed_at TEXT,
                  error TEXT,
                  video_id TEXT,
                  result_path TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at
                ON jobs(status, created_at);

                CREATE INDEX IF NOT EXISTS idx_jobs_normalized_url_status
                ON jobs(normalized_url, status);

                CREATE TABLE IF NOT EXISTS transcripts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  video_id TEXT UNIQUE NOT NULL,
                  normalized_url TEXT UNIQUE,
                  url TEXT,
                  title TEXT,
                  channel TEXT,
                  platform TEXT,
                  duration REAL,
                  upload_date TEXT,
                  description TEXT,
                  thumbnail TEXT,
                  view_count INTEGER,
                  speaker_count INTEGER,
                  word_count INTEGER,
                  confidence REAL,
                  transcribed_at TEXT NOT NULL DEFAULT (datetime('now')),
                  path TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_transcripts_platform_channel
                ON transcripts(platform, channel, transcribed_at DESC);

                CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
                  video_id UNINDEXED,
                  title,
                  channel,
                  description,
                  transcript_text
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
