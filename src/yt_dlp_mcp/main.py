from __future__ import annotations

import atexit
import inspect
import logging
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from yt_dlp_mcp.config import Settings, load_settings
from yt_dlp_mcp.db.database import Database
from yt_dlp_mcp.db.jobs import JobsRepository
from yt_dlp_mcp.db.transcripts import TranscriptsRepository
from yt_dlp_mcp.mcp.tools import ToolRegistry
from yt_dlp_mcp.services.downloader import Downloader
from yt_dlp_mcp.services.storage import StorageService
from yt_dlp_mcp.services.transcriber import AssemblyAITranscriber
from yt_dlp_mcp.worker import BackgroundWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


class AppRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.jobs = JobsRepository(self.database)
        self.transcripts = TranscriptsRepository(self.database)

        downloader_root = settings.data_dir / "_work"
        self.downloader = Downloader(downloader_root)
        self.storage = StorageService(settings.data_dir)
        self.transcriber = AssemblyAITranscriber(api_key=settings.assemblyai_api_key)

        self.worker = BackgroundWorker(
            jobs=self.jobs,
            transcripts=self.transcripts,
            downloader=self.downloader,
            transcriber=self.transcriber,
            storage=self.storage,
            poll_interval_seconds=settings.poll_interval_seconds,
        )

    def close(self) -> None:
        self.worker.stop()
        self.database.close()


def _build_auth(settings: Settings) -> Any:
    has_client_id = bool(settings.google_client_id)
    has_client_secret = bool(settings.google_client_secret)
    if not has_client_id and not has_client_secret:
        return None
    if not has_client_id or not has_client_secret:
        raise RuntimeError("Both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required for OAuth")
    if not settings.public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL is required when OAuth is enabled")

    try:
        from fastmcp.server.auth.providers.google import GoogleProvider
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError("Google OAuth provider is unavailable in this FastMCP build") from exc

    kwargs: dict[str, Any] = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
    }
    signature = inspect.signature(GoogleProvider)
    if "base_url" in signature.parameters:
        kwargs["base_url"] = settings.public_base_url
    if "allowed_client_redirect_uris" in signature.parameters:
        kwargs["allowed_client_redirect_uris"] = [
            "http://localhost:*",
            "https://claude.ai/api/mcp/auth_callback",
        ]

    return GoogleProvider(**kwargs)


def create_app(runtime: AppRuntime) -> FastMCP:
    auth = _build_auth(runtime.settings)
    if auth is None:
        mcp = FastMCP(name="yt-dlp-mcp")
    else:
        mcp = FastMCP(name="yt-dlp-mcp", auth=auth)

    tools = ToolRegistry(runtime.jobs, runtime.transcripts)
    tools.register(mcp)

    @mcp.custom_route(runtime.settings.health_path, methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "worker_running": runtime.worker.is_running,
                "db_path": str(runtime.settings.database_path),
                "mcp_path": runtime.settings.mcp_path,
            }
        )

    return mcp


def cli() -> None:
    settings = load_settings()
    runtime = AppRuntime(settings)
    runtime.worker.start()
    atexit.register(runtime.close)

    app = create_app(runtime)
    logger.info("Starting MCP server on %s:%s%s", settings.host, settings.port, settings.mcp_path)
    app.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        path=settings.mcp_path,
    )


if __name__ == "__main__":
    cli()
