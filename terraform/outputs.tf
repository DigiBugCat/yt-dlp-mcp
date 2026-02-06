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

# Access service token for frontend
output "cf_access_client_id" {
  description = "CF Access Client ID for frontend"
  value       = cloudflare_zero_trust_access_service_token.frontend.client_id
}

output "cf_access_client_secret" {
  description = "CF Access Client Secret for frontend"
  value       = cloudflare_zero_trust_access_service_token.frontend.client_secret
  sensitive   = true
}
