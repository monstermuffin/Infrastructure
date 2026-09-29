# MonitoringPipelineStale

## What it means

Either a site collector has been delivering samples to the hub more than 15 minutes late, or a hub component that vmalert can see (vmalert itself, Alertmanager) has not answered scrapes for 10 minutes. Dashboards may show old data and alerts may be delayed or not evaluated.

## First three checks

1. Which branch fired: the labels tell you. `job="collector"` is delivery lag; `job="vmalert"` or `job="alertmanager"` is a hub component.
2. Lag: `time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds{job="collector"}` per host. Then on the collector `journalctl -u alloy -n 100` for remote-write errors, and `curl -s http://<hub>:8428/health` from it.
3. Hub components: `systemctl status vmalert alertmanager` on the hub (they are podman services), and `curl -s localhost:8880/api/v1/rules` (vmalert) or `curl -s localhost:9093/-/healthy` (Alertmanager).

## Common causes and fixes

- The hub was restarted or overloaded and a collector is replaying its buffer: the lag falls by itself; check again after a few minutes.
- The link between the collector and the hub is slow or flapping: fix the network; the buffer holds the data meanwhile.
- A hub container is down or stuck: `systemctl restart <app>` on the hub and read `journalctl -u <app>`.
- Hub disk full: free space; VictoriaMetrics stops accepting writes when its disk is nearly full.

## When it is safe to silence

During planned work on the hub or the link. Create an Alertmanager silence on `alertname="MonitoringPipelineStale"` with an expiry and a comment.
