#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
. ./.env
set +a

TF="${ROOT_DIR}/scripts/terraformw.sh"

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

# Stop containers first (doesn't delete the volume unless you ask it to).
docker compose down

$TF -chdir=terraform init -backend-config=production.s3.tfbackend
$TF -chdir=terraform destroy -auto-approve "${TF_ARGS[@]}"
