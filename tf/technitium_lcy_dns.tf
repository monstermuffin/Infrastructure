# ---------------------------------------------------------------------------
# Technitium DNS — LCY (technitium01.lcy.muffn.io)
#
# DNS zones and records are managed via the kenske provider over the plain HTTP
# API listener on :5380. Server settings stay on the darkhonor provider.
#
# ---------------------------------------------------------------------------

resource "technitium_dns_zone" "lcy" {
  provider = kenske-technitium.lcy

  name                       = "lcy.muffn.io"
  type                       = "Primary"
  use_soa_serial_date_scheme = true
}

locals {
  lcy_lxc_records = {
    for r in var.lxc_dns_records : "${r.name}.${r.zone}" => {
      ip  = r.ip
      ttl = 300
    } if r.zone == technitium_dns_zone.lcy.name
  }

  lcy_vm_records = {
    for fqdn, record in local.proxmox_vm_dns_records : fqdn => {
      ip  = record.ip
      ttl = 300
    } if record.zone == technitium_dns_zone.lcy.name
  }

  lcy_host_records = merge(
    local.lcy_infra_records,
    local.lcy_lxc_records,
    local.lcy_vm_records,
  )

  lcy_reverse_records = {
    for fqdn, record in local.lcy_host_records : fqdn => {
      ip  = record.ip
      ttl = record.ttl
      zone = format(
        "%s.%s.%s.in-addr.arpa",
        split(".", record.ip)[2],
        split(".", record.ip)[1],
        split(".", record.ip)[0],
      )
      name = format(
        "%s.%s.%s.%s.in-addr.arpa",
        split(".", record.ip)[3],
        split(".", record.ip)[2],
        split(".", record.ip)[1],
        split(".", record.ip)[0],
      )
    }
  }

  lcy_reverse_zones = toset([
    for record in values(local.lcy_reverse_records) : record.zone
  ])
}

resource "technitium_dns_zone_record" "lcy_infra" {
  for_each = local.lcy_infra_records
  provider = kenske-technitium.lcy

  zone       = technitium_dns_zone.lcy.name
  domain     = each.key
  type       = "A"
  ip_address = each.value.ip
  ttl        = each.value.ttl
}

resource "technitium_dns_zone_record" "lcy_lxc_hosts" {
  for_each = local.lcy_lxc_records
  provider = kenske-technitium.lcy

  zone       = technitium_dns_zone.lcy.name
  domain     = each.key
  type       = "A"
  ip_address = each.value.ip
  ttl        = each.value.ttl

  depends_on = [technitium_dns_zone.lcy]
}

resource "technitium_dns_zone_record" "lcy_vm_hosts" {
  for_each = local.lcy_vm_records
  provider = kenske-technitium.lcy

  zone       = technitium_dns_zone.lcy.name
  domain     = each.key
  type       = "A"
  ip_address = each.value.ip
  ttl        = each.value.ttl

  depends_on = [technitium_dns_zone.lcy]
}

resource "technitium_dns_zone" "lcy_reverse" {
  for_each = local.lcy_reverse_zones
  provider = kenske-technitium.lcy

  name                       = each.value
  type                       = "Primary"
  use_soa_serial_date_scheme = true
}

resource "technitium_dns_zone_record" "lcy_ptr" {
  for_each = local.lcy_reverse_records
  provider = kenske-technitium.lcy

  zone     = each.value.zone
  domain   = each.value.name
  type     = "PTR"
  ptr_name = each.key
  ttl      = each.value.ttl

  lifecycle {
    # kenske/technitium does not round-trip PTR target data in Read, so
    # legacy malformed PTRs can fail non-essential TTL-only updates.
    ignore_changes = [ttl]
  }

  depends_on = [
    technitium_dns_zone.lcy_reverse,
    technitium_dns_zone_record.lcy_infra,
    technitium_dns_zone_record.lcy_lxc_hosts,
    technitium_dns_zone_record.lcy_vm_hosts,
  ]
}
