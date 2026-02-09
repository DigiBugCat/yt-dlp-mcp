output "hostname" {
  value = "${var.subdomain}.${var.domain}"
}

output "tunnel_id" {
  value = cloudflare_zero_trust_tunnel_cloudflared.tunnel.id
}

output "tunnel_token" {
  value     = data.cloudflare_zero_trust_tunnel_cloudflared_token.token.token
  sensitive = true
}

output "cf_access_client_id" {
  value = cloudflare_zero_trust_access_service_token.fastmcp_frontend.client_id
}

output "cf_access_client_secret" {
  value     = cloudflare_zero_trust_access_service_token.fastmcp_frontend.client_secret
  sensitive = true
}

