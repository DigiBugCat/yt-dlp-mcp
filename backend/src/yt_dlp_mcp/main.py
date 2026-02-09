from __future__ import annotations

import atexit
import logging

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


def create_app(runtime: AppRuntime) -> FastMCP:
    mcp = FastMCP(name="yt-dlp-mcp")

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
