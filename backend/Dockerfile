FROM python:3.12-slim

ARG YTDLP_CHANNEL=nightly
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp from channel-specific release artifacts.
RUN set -eux; \
    if [ "$YTDLP_CHANNEL" = "nightly" ]; then \
      YTDLP_URL="https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp"; \
    elif [ "$YTDLP_CHANNEL" = "stable" ]; then \
      YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"; \
    else \
      echo "Unsupported YTDLP_CHANNEL: $YTDLP_CHANNEL"; \
      exit 1; \
    fi; \
    curl -fsSL "$YTDLP_URL" -o /usr/local/bin/yt-dlp; \
    chmod +x /usr/local/bin/yt-dlp; \
    yt-dlp --version

RUN groupadd -g 1001 app && useradd -u 1001 -g app -s /bin/bash -m app

WORKDIR /app

# Install deps first (layer cached unless pyproject.toml changes).
COPY pyproject.toml README.md ./
RUN mkdir -p src/yt_dlp_mcp && touch src/yt_dlp_mcp/__init__.py \
 && pip install --no-cache-dir . \
 && rm -rf src/yt_dlp_mcp

# Copy real source and reinstall (fast, deps already cached).
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

RUN mkdir -p /data && chown -R app:app /app /data

USER app

ENV PYTHONUNBUFFERED=1 \
    PORT=3000 \
    HOST=0.0.0.0 \
    DATA_DIR=/data \
    DATABASE_PATH=/data/yt_dlp_mcp.sqlite3 \
    MCP_PATH=/mcp \
    HEALTH_PATH=/healthz \
    POLL_INTERVAL_SECONDS=5 \
    PARAKEET_URL=http://parakeet:8000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null || exit 1

CMD ["yt-dlp-mcp"]
