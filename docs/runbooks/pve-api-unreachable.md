# PveApiUnreachable

## What it means

The site collector could not query any Proxmox API for one Proxmox module (a cluster or a standalone node) for 10 minutes. Proxmox metrics for it are missing and the guest-down rules cannot see its guests. A single unreachable node of a cluster does not trigger this; that shows up as `PveNodeDown`.

## First three checks

1. Are the nodes up? `ping <node>` and `ssh root@<node>`. For a standalone node, this alert is also the node-down signal.
2. Is the exporter answering on the collector? `systemctl status pve-exporter` and `curl -s 'http://127.0.0.1:9221/pve?module=<module>&target=<node>' | head` on the collector.
3. Does the API token still work? From the collector: `curl -sk -H 'Authorization: PVEAPIToken=<user>!<token>=<secret>' https://<node>:8006/api2/json/version` (do not paste the secret anywhere shared).

## Common causes and fixes

- The node or the path to it is down: fix that first; the alert clears when the API answers.
- `pveproxy` stopped on the node: `systemctl restart pveproxy` there.
- The API token was deleted, expired or lost its permissions: recreate it in the Proxmox UI (read-only role) and update the vault value for the module in the collector's host variables, then redeploy the collector.
- The exporter container is down: `systemctl restart pve-exporter` on the collector and read `journalctl -u pve-exporter`.

## When it is safe to silence

During planned maintenance of the Proxmox nodes or their network. Create an Alertmanager silence on `alertname="PveApiUnreachable"` and `job="<job>"` with an expiry and a comment.
