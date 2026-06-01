# pve_power_mgmt

Manage idle power draw on Proxmox VE hosts. CPU frequency governor + Energy Performance Preference, Wake-on-LAN, and USB autosuspend.

PCIe ASPM and PCI runtime power management are intentionally excluded, both are known to
documented causes of NIC link drops on Intel X710/I225/I226 hardware under Proxmox.

## Design decisions

- **Host-specific activation** — `pve_power_mgmt_enabled: false` by default; set `true` per host in `host_vars`
- **Applies immediately via sysfs/ethtool** with persistence via cron `@reboot` (CPU) and udev rules (WoL/USB)
- **No boot config changes** — no GRUB or kernel cmdline modifications; nothing that can prevent a host from booting
- **EPP silently skipped** on CPUs that don't support Intel HWP / AMD CPPC
- **WoL per-interface udev rules** — new NICs added later are unaffected until the playbook is re-run
- **Fully reversible** — `--tags revert` removes all cron jobs and udev rules

## Variables

| Variable | Default | Description |
|---|---|---|
| `pve_power_mgmt_enabled` | `false` | Safety gate — must be set `true` per host |
| `pve_power_mgmt_cpu_governor` | `powersave` | cpufreq governor (`performance`, `schedutil`, `""` = skip) |
| `pve_power_mgmt_cpu_epp` | `balance_power` | Energy Performance Preference (`balance_performance`, `power`, `""` = skip, silently skipped if unsupported) |
| `pve_power_mgmt_cpu_persistent` | `true` | Persist governor/EPP via cron `@reboot` |
| `pve_power_mgmt_wol_disable` | `true` | Disable WoL on managed interfaces |
| `pve_power_mgmt_wol_keep_interfaces` | `[]` | Interfaces to keep WoL enabled on |
| `pve_power_mgmt_wol_interfaces` | `[]` | Explicit list; empty = auto-discover all WoL-capable interfaces |
| `pve_power_mgmt_usb_autosuspend` | `true` | Enable USB autosuspend |
| `pve_power_mgmt_usb_autosuspend_delay_ms` | `2000` | USB suspend delay (ms) |

## Tags

| Tag | Action |
|---|---|
| `info`, `power_info` | Display current state (no `enabled` gate) |
| `apply`, `power_apply` | Apply all enabled settings |
| `cpu`, `governor`, `epp` | CPU governor + EPP only |
| `wol` | Wake-on-LAN only |
| `usb` | USB autosuspend only |
| `revert` | Remove all persistence |

## Usage

### Enable per host

```yaml
# host_vars/pveXX.site.example.com/main.yml
pve_power_mgmt_enabled: true

# Keep WoL on the management NIC (run --tags info first to see interface names)
pve_power_mgmt_wol_keep_interfaces:
  - enp89s0
```

### Run

```bash
# Check current state — no changes
ansible-playbook playbooks/pve/power_mgmt.yml --tags info

# Apply all settings
ansible-playbook playbooks/pve/power_mgmt.yml

# CPU settings only
ansible-playbook playbooks/pve/power_mgmt.yml --tags cpu

# Dry run
ansible-playbook playbooks/pve/power_mgmt.yml --check --diff

# Revert everything
ansible-playbook playbooks/pve/power_mgmt.yml --tags revert
```

## WoL notes

`ethtool -s <iface> wol d` only affects wake-from-poweroff behaviour. It has no effect on
a running link — speed, duplex, and packet handling are completely unaffected.

Use `pve_power_mgmt_wol_keep_interfaces` to exempt any NIC you need for remote wakeup.
The udev rules written by this role use specific `KERNEL=="<iface>"` matching, so NICs
you add or replace later are unaffected until you re-run the playbook.
