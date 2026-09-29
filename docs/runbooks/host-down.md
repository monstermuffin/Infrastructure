# HostDown

## What it means

A Proxmox guest is stopped although it is set to start at boot, and it has been that way for 10 minutes. Services on the guest are unavailable. Guests that are stopped on purpose have start at boot disabled and never trigger this alert.

## First three checks

1. Guest state from the node that owns it: `pct status <vmid>` (containers) or `qm status <vmid>` (VMs), and `ha-manager status | grep <vmid>` to see whether HA is trying to start it.
2. Why it stopped: `journalctl -u pve-ha-lrm --since "1 hour ago"` and the task log for the guest in the Proxmox UI.
3. Metric: `pve_up{id="<type>/<vmid>"}` in Grafana Explore, and `pve_onboot_status` for the same id.

## Common causes and fixes

- Stopped by hand for maintenance and not restarted: start it (`pct start <vmid>`), or turn off start at boot if it is meant to stay off.
- HA reached its restart or relocation limit and left the guest in an error state: fix the underlying cause, then `ha-manager set ct:<vmid> --state started`.
- The guest crashed on boot (for example a full disk or a failed mount): open the console, or `pct start <vmid>` and read the start log.

## When it is safe to silence

While the guest is deliberately stopped for maintenance. Create an Alertmanager silence on `alertname="HostDown"` and `host="<guest name>"` with an expiry and a comment. If it is parked long term, disable start at boot instead of silencing.
