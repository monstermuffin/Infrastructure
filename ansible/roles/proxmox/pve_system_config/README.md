# pve_system_config

Configures basic system settings on Proxmox VE hosts. Recreated community scripts-ish.

## Vars

Preferred inventory interface:

- Site-wide values should be set with `site_*` vars in site `group_vars`:
  - `site_domain`
  - `site_nameservers`
  - `site_search_domains`
  - `site_ntp_servers`
  - `site_ntp_enabled`
- Host-specific values remain `pve_system_*`:
  - `pve_system_hostname`
  - `pve_system_hosts_ip`
  - `pve_system_cluster_peers`
  - `pve_system_timezone`

The role maps `site_*` values into its internal `pve_system_*` vars for compatibility.

## Tags

- `hostname`
- `timezone`
- `locale`
- `dns`
- `ntp`
- `ssh`
- `motd`

## Notes

- DNS makes `/etc/resolv.conf` immutable to prevent DHCP from overwriting it. Undo with `chattr -i /etc/resolv.conf`.
- The same site DNS settings are also used as the default DNS source for newly provisioned LXCs unless a container explicitly overrides `nameserver` or `searchdomain`.
- Hostname requires `pve_system_hosts_ip` to be set, Proxmox needs the FQDN to resolve to a real IP, not loopback, or cluster communication will break.
