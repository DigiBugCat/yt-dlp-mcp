# yt-dlp-mcp

Async MCP service that downloads video audio with **yt-dlp** and transcribes it via **AssemblyAI** — exposed as MCP tools for Claude and other LLM clients.

```
                          ┌──────────────────────┐
                          │   Claude / LLM app    │
                          └──────────┬───────────┘
                                     │ MCP (SSE/HTTP)
                                     v
                          ┌──────────────────────┐
                          │  mcp_server/          │
                          │  FastMCP proxy        │
                          │  (fastmcp.cloud)      │
                          └──────────┬───────────┘
                                     │ CF Access service token
                                     v
┌────────────────────────────────────────────────────────────────┐
│  Cloudflare Tunnel  (terraform/)                               │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 v
┌────────────────────────────────────────────────────────────────┐
│  backend/  (Docker)                                            │
│                                                                │
│  ┌────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │ FastMCP    │──>│ Job Queue    │──>│ Background Worker   │  │
│  │ /mcp       │   │ (SQLite)     │   │                     │  │
│  └────────────┘   └──────────────┘   │  1. yt-dlp download │  │
│                                      │  2. AssemblyAI API  │  │
│                                      │  3. Write artifacts │  │
│                                      └──────────┬──────────┘  │
│                                                 │              │
│                                                 v              │
│                                      ┌─────────────────────┐  │
│                                      │ /data/transcripts/  │  │
│                                      │  {platform}/        │  │
│                                      │   {channel}/        │  │
│                                      │    {video_id}/      │  │
│                                      │     transcript.md   │  │
│                                      │     transcript.json │  │
│                                      │     transcript.txt  │  │
│                                      │     audio.mp3       │  │
│                                      │     metadata.json   │  │
│                                      └─────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `transcribe(url)` | Queue a video URL for download + transcription. Returns immediately with a `job_id`. |
| `job_status(job_id)` | Poll job progress: `queued` → `downloading` → `transcribing` → `completed` / `failed` |
| `search(query, limit)` | Full-text search across all transcripts |
| `list_transcripts(platform, channel, limit)` | Browse available transcripts with optional filters |
| `read_transcript(video_id, format)` | Read a transcript as `markdown`, `text`, or `json` |

Duplicate URLs are deduplicated automatically — if a transcript already exists or a job is in flight, the existing result is returned.

## Repo Structure

```
yt-dlp-mcp/
├── mcp_server/          # FastMCP proxy (deployed to fastmcp.cloud)
│   ├── server.py        #   OAuth + CF Access → proxies to backend
│   └── pyproject.toml
├── backend/             # Transcription service (Docker)
│   ├── src/yt_dlp_mcp/  #   MCP tools, worker, DB, services
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   └── scripts/         #   deploy.sh, destroy.sh, terraformw.sh
├── terraform/           # Cloudflare Tunnel + DNS
├── .github/workflows/   # CI (lint/test/build) + Deploy (GHCR + terraform)
└── Makefile             # Docker, terraform, and deploy shortcuts
```

## Quick Start

### Prerequisites

- Docker
- An [AssemblyAI API key](https://www.assemblyai.com/)
- Cloudflare account (for tunnel deployment)

### Local Development

```bash
# Install backend in editable mode
pip install -e backend/[dev]

# Run tests
pytest backend/tests -q

# Run the backend directly (needs ASSEMBLYAI_API_KEY)
cp backend/.env.example .env
# ... fill in your keys ...
yt-dlp-mcp
```

### Docker

```bash
make build      # Build the image
make up         # Start the backend (no tunnel)
make up-tunnel  # Start backend + Cloudflare tunnel
make down       # Stop everything
make health     # Check /healthz
make logs-app   # Tail logs
```

### Full Deploy

```bash
# 1. Fill in .env from backend/.env.example
# 2. Deploy tunnel + DNS + start containers
make deploy

# Tear down
make destroy
```

### Terraform Only

```bash
make tf-init     # terraform init
make tf-apply    # terraform apply
make tf-destroy  # terraform destroy
```

## Environment Variables

Create a `.env` at the repo root (see `backend/.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ASSEMBLYAI_API_KEY` | Yes | AssemblyAI transcription API key |
| `GOOGLE_CLIENT_ID` | For OAuth | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For OAuth | Google OAuth client secret |
| `PUBLIC_BASE_URL` | For OAuth | Public URL of the service |
| `CLOUDFLARE_ACCOUNT_ID` | For deploy | CF account ID |
| `CLOUDFLARE_ZONE_ID` | For deploy | CF zone ID |
| `CLOUDFLARE_API_TOKEN` | For deploy | CF API token |
| `DOMAIN` | For deploy | e.g. `pantainos.net` |
| `SUBDOMAIN` | For deploy | e.g. `yt-cli` |

## CI/CD

- **CI** — Runs on every push/PR: ruff, mypy, pytest, Docker build smoke test
- **Deploy** — Runs on push to `main` + nightly cron: builds and pushes to GHCR, then applies terraform
