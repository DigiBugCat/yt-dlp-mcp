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

# --- Cloudflare Access (protect backend) ---

resource "cloudflare_zero_trust_access_application" "app" {
  account_id       = var.account_id
  type             = "self_hosted"
  name             = "yt-dlp-mcp"
  domain           = local.hostname
  session_duration = "24h"
  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.service_token.id
      precedence = 1
    }
  ]
}

resource "cloudflare_zero_trust_access_service_token" "fastmcp_frontend" {
  account_id = var.account_id
  name       = "fastmcp-cloud-frontend"
  duration   = "8760h"

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "service_token" {
  account_id = var.account_id
  name       = "Allow service token"
  decision   = "non_identity"
  include = [
    {
      any_valid_service_token = {}
    }
  ]
}

