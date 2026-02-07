from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    host: str
    port: int
    mcp_path: str
    health_path: str
    poll_interval_seconds: int
    data_dir: Path
    database_path: Path
    assemblyai_api_key: str
    google_client_id: str | None
    google_client_secret: str | None
    public_base_url: str | None
    api_key: str | None



def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _normalized_path(path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def load_settings() -> Settings:
    load_dotenv()
    data_dir = Path(os.getenv("DATA_DIR", "/data")).resolve()
    database_path = Path(os.getenv("DATABASE_PATH", str(data_dir / "yt_dlp_mcp.sqlite3"))).resolve()

    assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    if not assemblyai_api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is required")

    return Settings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=_as_int("PORT", 3000),
        mcp_path=_normalized_path(os.getenv("MCP_PATH", "/mcp")),
        health_path=_normalized_path(os.getenv("HEALTH_PATH", "/healthz")),
        poll_interval_seconds=_as_int("POLL_INTERVAL_SECONDS", 5),
        data_dir=data_dir,
        database_path=database_path,
        assemblyai_api_key=assemblyai_api_key,
        google_client_id=os.getenv("GOOGLE_CLIENT_ID") or None,
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET") or None,
        public_base_url=os.getenv("PUBLIC_BASE_URL") or None,
        api_key=os.getenv("API_KEY") or None,
    )
