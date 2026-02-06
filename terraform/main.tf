provider "cloudflare" {
  # Prefer API token auth.
  api_token = var.cloudflare_api_token

  # Legacy auth (works only if provider still supports it).
  email   = var.cloudflare_email
  api_key = var.cloudflare_api_key
}

locals {
  hostname = "${var.subdomain}.${var.domain}"
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "tunnel" {
  account_id = var.account_id
  name       = var.tunnel_name
}

# Remotely-managed config (Terraform-defined ingress rules).
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "config" {
  account_id = var.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.tunnel.id

  # v5.x: config is an attribute with object syntax
  config = {
    ingress = [
      {
        hostname = local.hostname
        service  = var.service_url
      },
      {
        # Catch-all rule (mandatory)
        service = "http_status:404"
      }
    ]
  }
}

# Public hostname -> tunnel CNAME
resource "cloudflare_dns_record" "cname" {
  zone_id = var.zone_id
  name    = var.subdomain
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.tunnel.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}

data "cloudflare_zero_trust_tunnel_cloudflared_token" "token" {
  account_id = var.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.tunnel.id
}

# --- Cloudflare Access (Zero Trust) ---

# Access Application to protect the backend
resource "cloudflare_zero_trust_access_application" "backend" {
  account_id                 = var.account_id
  name                       = "yt-dlp-mcp-backend"
  domain                     = local.hostname
  type                       = "self_hosted"
  session_duration           = "24h"
  auto_redirect_to_identity  = false
  http_only_cookie_attribute = true
}

# Service token for frontend -> backend auth
resource "cloudflare_zero_trust_access_service_token" "frontend" {
  account_id = var.account_id
  name       = "yt-dlp-mcp-frontend"
  duration   = "8760h" # 1 year
}

# Policy: allow the service token
resource "cloudflare_zero_trust_access_policy" "service_token" {
  account_id     = var.account_id
  application_id = cloudflare_zero_trust_access_application.backend.id
  name           = "Allow Frontend Service Token"
  decision       = "non_identity"
  precedence     = 1

  include = [{
    service_token = {
      token_id = cloudflare_zero_trust_access_service_token.frontend.id
    }
  }]
}
