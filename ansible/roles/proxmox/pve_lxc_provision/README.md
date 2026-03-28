# pve_lxc_provision

Provisions and updates Proxmox LXC containers from cluster-level `pve_lxcs` inventory definitions.

## DNS

- Per-container DNS overrides remain available with `nameserver` and `searchdomain` in the individual LXC definition.
- If those fields are omitted, the role inherits site-wide DNS defaults from:
  - `site_nameservers`
  - `site_search_domains`

## Inventory

Example:

```yaml
pve_lxcs:
  sonarr01:
    vmid: 111
    hostname: sonarr01.aah.muffn.io
    node: pve03
    network_ip: "10.82.10.111/24"
    network_gw: "10.82.10.1"
    network_vlan: 710
    # Optional explicit overrides:
    # nameserver: "10.82.7.102 1.1.1.1"
    # searchdomain: "aah.muffn.io lcy.muffn.io"
```
