output "aah_tunnel_id" {
  description = "AAH cluster tunnel UUID"
  value       = cloudflare_zero_trust_tunnel_cloudflared.aah.id
}

output "aah_tunnel_token" {
  description = "Tunnel token for ingress hosts — encrypt and store in Ansible vault as cftun_tunnel_token"
  value       = data.cloudflare_zero_trust_tunnel_cloudflared_token.aah.token
  sensitive   = true
}
