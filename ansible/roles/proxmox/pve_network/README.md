# pve_network

Manages `/etc/network/interfaces` on Proxmox VE hosts. Supports physical interfaces, bridges, VLANs, bonds, bridge VLAN sub-interfaces, and static routes.

!! NOT FULLY TESTED !!

## Usage

Defaults to `pve_network_manage: "skip"`,set to `"manual"` to enable.

```yaml
pve_network_manage: "manual"

pve_network_interfaces:
  - name: eno1
    method: manual

pve_network_bridges:
  - name: vmbr0
    ports: "eno1"
    address: "{{ ansible_host }}/24"
    gateway: "10.0.0.1"
    bridge_stp: false
    bridge_fd: 0
```

See [defaults/main.yml](defaults/main.yml) for all variables. Configure per-host in `host_vars/`.

## Tags

| Tag | Description |
|-----|-------------|
| `configure` | Apply network configuration |
| `restart` | Restart networking service |

## Applying changes

The role does **not** restart networking by default. After running the playbook:

```bash
# Dry-run first
ansible-playbook playbooks/pve/network.yml --check --diff

# Apply (writes config, no restart)
ansible-playbook playbooks/pve/network.yml

# Then on the host (with console access):
ifreload -a          # or
systemctl restart networking  # or
systemctl reboot
```

Set `pve_network_auto_restart: true` to restart automatically (use with caution).

## Recovery

If you lose connectivity, access via console and restore the timestamped backup:

```bash
cp /etc/network/interfaces.backup.<timestamp> /etc/network/interfaces
systemctl restart networking
```
