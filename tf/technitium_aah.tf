# ---------------------------------------------------------------------------
# Technitium DNS — AAH (technitium{xx}.aah.muffn.io)
#
# Manages the aah.muffn.io zone and all host records for the AAH cluster.
#
# LXC records are populated at deploy time by ops/gen_lxc_dns.py for this site.
#
# ---------------------------------------------------------------------------
# TODO: Conditionals not supported?

resource "technitium_server_settings" "aah" {
  provider = technitium.aah

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

resource "technitium_zone" "aah" {
  provider = technitium.aah

  name                   = "aah.muffn.io"
  type                   = "Primary"
  soa_serial_date_scheme = true
}

# PVE nodes are not LXCs so the generator does not pick them up.
locals {
  aah_infra_records = {
    "pve02.aah.muffn.io" = "10.82.2.152"
    "pve03.aah.muffn.io" = "10.82.2.153"
    "pve04.aah.muffn.io" = "10.82.2.154"
  }
}

resource "technitium_record" "aah_infra" {
  for_each = local.aah_infra_records
  provider = technitium.aah

  zone  = technitium_zone.aah.name
  name  = each.key
  type  = "A"
  value = each.value
  ttl   = 3600
}

resource "technitium_record" "aah_lxc_hosts" {
  for_each = { for r in var.lxc_dns_records : r.name => r if r.zone == "aah.muffn.io" }
  provider = technitium.aah

  zone  = each.value.zone
  name  = "${each.value.name}.${each.value.zone}"
  type  = "A"
  value = each.value.ip
  ttl   = 300

  depends_on = [technitium_zone.aah]
}
