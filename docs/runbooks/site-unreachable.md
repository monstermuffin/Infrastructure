# SiteUnreachable

## What it means

The hub has not received a heartbeat (`up{job="collector"}`) from a site's collector for 5 minutes, so metrics from that site are no longer arriving. Hosts at the site and the collector keep what they cannot send on disk and deliver it once the collector is reachable again. The collector buffers for up to 72 hours; an outage longer than that, or a restart of the collector's Alloy service during the outage, loses the buffered backlog. Alerts that depend on data from that site cannot fire while it is silent.

At the site that hosts the hub the alert means the collector guest or its Alloy service is down, not the whole site. If the whole hub site is down nothing can alert at all.

## First three checks

1. Is the collector guest running? From its Proxmox node: `pct status <vmid>`, and `ha-manager status | grep <vmid>` where HA manages it.
2. Is it reachable from the hub? `ping <collector>` and `ssh <collector> systemctl status alloy`. From the collector, the hub's write endpoint should answer: `curl -s http://<hub>:8428/health`.
3. Metric: `up{job="collector",site="<site>"}` and `prometheus_remote_storage_queue_highest_sent_timestamp_seconds{job="collector"}` in Grafana Explore, and the Collectors dashboard.

## Common causes and fixes

- The collector guest is stopped or its node is down: start it (`pct start <vmid>`) or deal with the node first (see `PveNodeDown`).
- Alloy is stopped or failing to load its config: `journalctl -u alloy -n 100` on the collector. `alloy validate /etc/alloy` checks the config; redeploy the collector role to restore a good one.
- The link between the site and the hub is down: check the site-to-site tunnel and routing. Data buffers meanwhile; nothing is lost while the outage is shorter than the buffer window.
- The hub is rejecting writes: check the hub's VictoriaMetrics logs and disk space.

## When it is safe to silence

During planned work on the collector, its node or the site link. Create an Alertmanager silence on `alertname="SiteUnreachable"` and `site="<site>"` with an expiry and a comment. If a collector was retired on purpose, the alert clears by itself 30 days after its last heartbeat; silence it until then.
