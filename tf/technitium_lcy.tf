# ---------------------------------------------------------------------------
# Technitium DNS — LCY (technitium01.lcy.muffn.io)
#
# Manages server-level settings and static infrastructure records for LCY.
#
# LXC records are populated at deploy time by ops/gen_lxc_dns.py for this site.
#
# ---------------------------------------------------------------------------

resource "technitium_server_settings" "lcy" {
  provider = technitium.lcy

  recursion             = "AllowOnlyForPrivateNetworks"
  recursion_network_acl = ["10.0.0.0/8", "127.0.0.0/8"]
  dnssec_validation     = true
  qname_minimization    = true
  randomize_name        = true
  log_queries           = true
  enable_blocking       = false
  forwarders            = ["9.9.9.9:853", "149.112.112.112:853"]
  forwarder_protocol    = "Tls"
  serve_stale           = true
}

# PVE nodes are not LXCs so the generator does not pick them up.
locals {
  lcy_infra_records = {
    "pve01.lcy.muffn.io" = {
      ip  = "10.83.2.151"
      ttl = 3600
    }
  }
}
