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

