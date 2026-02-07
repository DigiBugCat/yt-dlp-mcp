#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env. Create it (see backend/.env.example) and set Cloudflare + OAuth variables." >&2
  exit 1
fi

# Export env vars from .env for this script.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

TF="${BACKEND_DIR}/scripts/terraformw.sh"

: "${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID in .env}"
: "${CLOUDFLARE_ZONE_ID:?Set CLOUDFLARE_ZONE_ID in .env}"
: "${DOMAIN:?Set DOMAIN in .env (e.g. pantainos.net)}"
: "${SUBDOMAIN:?Set SUBDOMAIN in .env (e.g. yt-cli)}"

# Use API token if present; otherwise allow legacy email/api_key.
TF_ARGS=(
  -var "account_id=${CLOUDFLARE_ACCOUNT_ID}"
  -var "zone_id=${CLOUDFLARE_ZONE_ID}"
  -var "domain=${DOMAIN}"
  -var "subdomain=${SUBDOMAIN}"
  -var "tunnel_name=${TUNNEL_NAME:-yt-dlp-mcp}"
  -var "service_url=${SERVICE_URL:-http://app:3000}"
)

if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  TF_ARGS+=( -var "cloudflare_api_token=${CLOUDFLARE_API_TOKEN}" )
fi
if [[ -n "${CLOUDFLARE_EMAIL:-}" ]]; then
  TF_ARGS+=( -var "cloudflare_email=${CLOUDFLARE_EMAIL}" )
fi
if [[ -n "${CLOUDFLARE_API_KEY:-}" ]]; then
  TF_ARGS+=( -var "cloudflare_api_key=${CLOUDFLARE_API_KEY}" )
fi

$TF -chdir=terraform init -upgrade -backend-config=production.s3.tfbackend
$TF -chdir=terraform apply -auto-approve "${TF_ARGS[@]}"

# Capture the tunnel token without printing it.
TUNNEL_TOKEN="$($TF -chdir=terraform output -raw tunnel_token)"

# Update (or append) CF_TUNNEL_TOKEN in .env
python3 - <<PY
import pathlib

env_path = pathlib.Path(".env")
lines = env_path.read_text(encoding="utf-8").splitlines()
key = "CF_TUNNEL_TOKEN"
value = ${TUNNEL_TOKEN!r}
out = []
found = False
for line in lines:
    if line.startswith(key + "="):
        out.append(f"{key}={value}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={value}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

# Bring up app + cloudflared.
docker compose -f backend/docker-compose.yml up -d app cloudflared

echo "Deployed. Hostname: https://${SUBDOMAIN}.${DOMAIN}"
