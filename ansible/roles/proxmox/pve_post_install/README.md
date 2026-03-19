# pve_post_install

Post-installation configuration for Proxmox VE. Replicates the community post-install script behaviour as an idempotent Ansible role, they should just allow that shit to be automated.

## Actions

- Manages APT repositories (enterprise, no-subscription, test, Ceph) using deb822 `.sources` format
- Removes the subscription nag dialog (with APT hook to reapply after updates)
- Manages HA services (pve-ha-lrm, pve-ha-crm, corosync)
- Imports SSH keys for root from GitHub or a custom list
- Optionally runs apt update / dist-upgrade

## Variables

See [defaults/main.yml](defaults/main.yml) for all variables and their defaults. Should be set in host_vars/group_vars.

## Tags

| Tag | Description |
|-----|-------------|
| `repositories`, `repos` | APT repository config |
| `subscription`, `nag` | Subscription nag removal |
| `services`, `ha` | HA services |
| `ssh`, `ssh_keys`, `keys` | SSH key management |
| `updates`, `apt` | apt update |
| `upgrade` | dist-upgrade |

## Notes

- Legacy `.list` files are renamed to `.list.bak`, not deleted.
- Existing `.sources` files are disabled with `Enabled: false`, not deleted.
- After nag removal, clear browser cache (Ctrl+F5) to see the change.
