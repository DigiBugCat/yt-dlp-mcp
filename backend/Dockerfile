FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ARG YTDLP_CHANNEL=nightly
ARG DEBIAN_FRONTEND=noninteractive

# System dependencies: Python 3.12, ffmpeg, libsndfile (for audio I/O), curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3-pip \
      ffmpeg libsndfile1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Make python3.12 the default python/python3.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

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
COPY pyproject.toml README.md ./
COPY src ./src

# Install PyTorch with CUDA support, then the rest of the project deps.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --break-system-packages \
      torch torchaudio --index-url https://download.pytorch.org/whl/cu126 \
 && pip install --no-cache-dir --break-system-packages .

RUN mkdir -p /data && chown -R app:app /app /data

USER app

ENV PYTHONUNBUFFERED=1 \
    PORT=3000 \
    HOST=0.0.0.0 \
    DATA_DIR=/data \
    DATABASE_PATH=/data/yt_dlp_mcp.sqlite3 \
    MCP_PATH=/mcp \
    HEALTH_PATH=/healthz \
    POLL_INTERVAL_SECONDS=5

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null || exit 1

CMD ["yt-dlp-mcp"]
