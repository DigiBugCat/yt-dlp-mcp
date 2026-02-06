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
