# pve_system_config

Configures basic system settings on Proxmox VE hosts: hostname, timezone, locale, DNS, NTP, SSH, and MOTD.

Each section is conditionally included based on whether its variables are set, leave a variable empty/default to skip that section.

## Variables

See [defaults/main.yml](defaults/main.yml) for all variables and their defaults. Should be set in host_vars/group_vars really.

## Tags

| Tag | Description |
|-----|-------------|
| `hostname` | Hostname and /etc/hosts |
| `timezone` | Timezone |
| `locale` | Locale |
| `dns` | DNS resolvers |
| `ntp` | NTP (chrony) |
| `ssh` | SSH server config |
| `motd` | MOTD |

## Notes

- DNS makes `/etc/resolv.conf` immutable to prevent DHCP from overwriting it. Undo with `chattr -i /etc/resolv.conf`.
- SSH config is validated with `sshd -t` before applying to prevent lockouts.
- Hostname requires `pve_system_hosts_ip` to be set, Proxmox needs the FQDN to resolve to a real IP, not loopback, or cluster communication breaks.
- SSH keys can be imported from a URL (e.g. `https://github.com/username.keys`).
