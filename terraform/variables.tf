variable "cloudflare_api_token" {
  description = "Cloudflare API token (recommended)."
  type        = string
  sensitive   = true
  default     = null
}

variable "cloudflare_email" {
  description = "Cloudflare email for legacy global API key auth (not recommended)."
  type        = string
  default     = null
}

variable "cloudflare_api_key" {
  description = "Cloudflare global API key for legacy auth (not recommended)."
  type        = string
  sensitive   = true
  default     = null
}

variable "account_id" {
  description = "Cloudflare account ID that owns the tunnel."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for the domain."
  type        = string
}

variable "domain" {
  description = "Root domain, e.g. pantainos.net"
  type        = string
}

variable "subdomain" {
  description = "Subdomain label, e.g. yt-cli"
  type        = string
}

variable "tunnel_name" {
  description = "Tunnel name (human-readable)."
  type        = string
  default     = "yt-dlp-mcp"
}

variable "service_url" {
  description = "Origin service URL reachable from cloudflared container. For this repo: http://app:3000"
  type        = string
  default     = "http://app:3000"
}
