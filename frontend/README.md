# yt-dlp-mcp Frontend

Thin FastMCP proxy that handles OAuth authentication and forwards all tool calls to the backend service.

## Architecture

```
[Claude.ai] --> [fastmcp.cloud]  <-- handles OAuth, MCP protocol
                     |
          (CF Access Service Token)
                     v
         [yt-cli.pantainos.net]  <-- backend via CF tunnel
               (Docker)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BACKEND_URL` | Yes | Backend MCP endpoint (e.g., `https://yt-cli.pantainos.net/mcp`) |
| `CF_ACCESS_CLIENT_ID` | Yes | Cloudflare Access service token client ID |
| `CF_ACCESS_CLIENT_SECRET` | Yes | Cloudflare Access service token client secret |
| `HOST` | No | Bind host (default: `0.0.0.0`) |
| `PORT` | No | Bind port (default: `8000`) |
| `MCP_PATH` | No | MCP endpoint path (default: `/mcp`) |

## Cloudflare Access Setup

### 1. Create Access Application

1. Go to Cloudflare Zero Trust Dashboard
2. Navigate to **Access > Applications > Add an Application**
3. Select **Self-hosted**
4. Configure:
   - Application name: `yt-dlp-mcp`
   - Session duration: 24 hours
   - Application domain: `yt-cli.pantainos.net`

### 2. Create Service Token

1. Navigate to **Access > Service Auth > Create Service Token**
2. Name it `fastmcp-cloud-frontend`
3. Copy the **Client ID** and **Client Secret** immediately (secret shown only once)

### 3. Create Access Policy

1. In the application settings, add a policy:
   - Policy name: `Service Token Auth`
   - Action: Allow
   - Include: Service Token - select the token you created

## Deploy to fastmcp.cloud

1. Create a new deployment on fastmcp.cloud
2. Point to this directory or provide the GitHub URL
3. Set the required environment variables:
   ```
   BACKEND_URL=https://yt-cli.pantainos.net/mcp
   CF_ACCESS_CLIENT_ID=<your-client-id>
   CF_ACCESS_CLIENT_SECRET=<your-client-secret>
   ```

## Local Development

```bash
# Install dependencies
pip install -e .

# Set environment variables
export BACKEND_URL="https://yt-cli.pantainos.net/mcp"
export CF_ACCESS_CLIENT_ID="your-client-id"
export CF_ACCESS_CLIENT_SECRET="your-client-secret"

# Run
python server.py
```

## Verification

Test the backend is accessible with CF Access:

```bash
curl -H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" \
     -H "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET" \
     https://yt-cli.pantainos.net/healthz
```

Expected response:
```json
{"ok": true, "worker_running": true, ...}
```

## Available Tools

All tools proxy directly to the backend:

- `transcribe(url)` - Queue a video for transcription
- `job_status(job_id)` - Check transcription job status
- `search(query, limit)` - Search transcript content
- `list_transcripts(platform, channel, limit)` - List available transcripts
- `read_transcript(video_id, format)` - Read a transcript
