# yt-dlp-mcp Operational Notes

## Runtime Model
- Async MCP contract: `transcribe` always returns immediately with a `job_id` unless deduplicated.
- Background worker polls every 5 seconds and processes exactly one job at a time.
- Job lifecycle: `queued -> downloading -> transcribing -> completed|failed`.
- Transcription provider: AssemblyAI (`/v2/upload` + `/v2/transcript` polling).

## Duplicate Policy
- URL input is normalized before queueing.
- If a completed transcript already exists for the normalized URL, `transcribe` returns the existing result.
- If an active job exists for the normalized URL, `transcribe` returns that job ID.

## Data Layout
- SQLite database path defaults to `/data/yt_dlp_mcp.sqlite3`.
- Transcript artifacts live at:
  - `/data/transcripts/{platform}/{channel}/{video_id}/metadata.json`
  - `/data/transcripts/{platform}/{channel}/{video_id}/audio.mp3`
  - `/data/transcripts/{platform}/{channel}/{video_id}/transcript.md`
  - `/data/transcripts/{platform}/{channel}/{video_id}/transcript.json`
  - `/data/transcripts/{platform}/{channel}/{video_id}/transcript.txt`

## Authentication
- FastMCP OAuth with Google is enabled when `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` + `PUBLIC_BASE_URL` are set.
- `API_KEY` is reserved for a future token-auth fallback and is not enforced in v1.

## Deploy Pattern
- Cloudflare Tunnel exposes only the FastMCP app service.
- Nightly deploy workflow rebuilds image with fresh yt-dlp nightly binary.
