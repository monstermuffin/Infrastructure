# HostDown

## What it means

A host is down or silent, and has been for 10 minutes. The alert carries a `reason` label:

- `stopped`: a Proxmox guest is stopped although it is set to start at boot. Services on it are unavailable. Guests that are stopped on purpose have start at boot disabled and never trigger this alert.
- `silent`: the host is running as far as Proxmox knows (or is a host Proxmox does not manage, such as a VPS) but no node metrics have arrived from it. It may be hung or cut off from the network, or Alloy on it has stopped.

## First three checks

For `reason="silent"`, start with the last check below and then look at the host itself: `ping <host>`, `ssh <host> systemctl status alloy`, and `journalctl -u alloy -n 100` for push errors. If a whole site is silent, look at `SiteUnreachable` first.

1. Guest state from the node that owns it: `pct status <vmid>` (containers) or `qm status <vmid>` (VMs), and `ha-manager status | grep <vmid>` to see whether HA is trying to start it.
2. Why it stopped: `journalctl -u pve-ha-lrm --since "1 hour ago"` and the task log for the guest in the Proxmox UI.
3. Metric: `pve_up{id="<type>/<vmid>"}` in Grafana Explore, and `pve_onboot_status` for the same id. For a silent host: `up{job="node_fast", host="<host>"}`.

## Common causes and fixes

- Stopped by hand for maintenance and not restarted: start it (`pct start <vmid>`), or turn off start at boot if it is meant to stay off.
- HA reached its restart or relocation limit and left the guest in an error state: fix the underlying cause, then `ha-manager set ct:<vmid> --state started`.
- Silent host, Alloy stopped or failing: `systemctl restart alloy` after checking `alloy validate /etc/alloy`; redeploy the Alloy role to restore a good config. Restarting drops what was not yet sent.
- Silent host, cannot reach its collector: check the route and the site network; from the host, `curl -s -o /dev/null -w '%{http_code}\n' http://<collector>:8429/`. The host buffers and delivers after it recovers.
- The guest crashed on boot (for example a full disk or a failed mount): open the console, or `pct start <vmid>` and read the start log.

## When it is safe to silence

While the guest is deliberately stopped for maintenance, or while Alloy is being changed on a host. Create an Alertmanager silence on `alertname="HostDown"` and `host="<guest name>"` with an expiry and a comment. If it is parked long term, disable start at boot instead of silencing. A guest that is meant to run without an agent (an appliance, a test VM) belongs in `monitoring_hostdown_ignore` in `ansible/inventory/group_vars/monitored.yml`, which the `silent` rule leaves out.
