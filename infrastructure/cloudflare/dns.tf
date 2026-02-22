# SIMS Plus - Cloudflare DNS Configuration
# This is a reference for the DNS setup. Apply only after
# configuring the Cloudflare provider with API tokens.

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for simsplus.io"
  type        = string
  sensitive   = true
}

variable "server_ip" {
  description = "IP address of the origin server"
  type        = string
}

# Root domain
resource "cloudflare_record" "root" {
  zone_id = var.cloudflare_zone_id
  name    = "simsplus.io"
  content = var.server_ip
  type    = "A"
  proxied = true
}

# Wildcard subdomain (covers all school subdomains)
resource "cloudflare_record" "wildcard" {
  zone_id = var.cloudflare_zone_id
  name    = "*"
  content = "simsplus.io"
  type    = "CNAME"
  proxied = true
}

# API subdomain (explicit for clarity)
resource "cloudflare_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = "api"
  content = var.server_ip
  type    = "A"
  proxied = true
}
