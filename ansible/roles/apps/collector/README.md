# collector

Site collector: one small LXC per site (`collector01.<site>`). Grafana Alloy receives the remote-write pushes from the hosts at the site, buffers them on disk, forwards them to the hub (VictoriaMetrics) and scrapes the fixed targets listed in `monitoring_topology`. Exporters that Alloy has no built-in equivalent for run as podman apps from the host's `podman.yml` (today: `pve-exporter`).

## What it deploys

- Alloy itself comes from the `linux/alloy` role (a role dependency): the Grafana apt repository, the pinned `alloy` package (`alloy_version`), `/etc/default/alloy`, the service and its handlers, and the host fragments (`base.alloy`, `node.alloy`, `units.alloy`) that give the collector its own node metrics. This role adds only `collector.alloy` next to them; the collector pushes its own host metrics to its own receiver like any host.
- `/etc/alloy/collector.alloy`, rendered from `templates/collector.alloy.j2` and checked with `alloy validate` before it is copied into place. It contains:
  - `prometheus.receive_http` on `collector_receiver_port` (default 8429, path `/api/v1/metrics/write`). No authentication; access is limited to the site network by the network itself.
  - `prometheus.remote_write "hub"` with an on-disk WAL. `collector_wal_max_keepalive_time` (default 72h; the design minimum is 48h) is how long unsent data is kept while the hub is unreachable. Data is sent in order when the hub is back. Two limits, both measured: an outage longer than the window loses the whole backlog, and so does a restart of Alloy during the outage (older WAL segments are read only for their series records on start), which is why config changes use a reload.
  - A self-scrape whose `up{job="collector"}` is the site heartbeat, plus a short list of Alloy and remote-write series used by rules and the Collectors dashboard.
  - One scrape job per `monitoring_topology.pve` entry of the site, named `pve_<module>` and querying the local pve-exporter with `__param_module` and `__param_target`. Job, instance and all exporter labels are unchanged from when the exporter ran on the hub; the collector adds `site`.
- A config change is applied with a reload (a config that fails to load leaves the running one in place); package or environment file changes restart the service.

## Variables

All are role defaults in `defaults/main.yml`; the site layout comes from `monitoring_topology` (`group_vars/tag_app_collector/monitoring_topology.yml`, git-crypt encrypted).

| Variable | Default | Meaning |
|---|---|---|
| `collector_site` | derived | The site whose `monitoring_topology.sites` entry names this host as collector |
| `collector_receiver_port` | `8429` | Push receiver port |
| `collector_hub_host` / `collector_hub_port` | `victoriametrics01.aah.muffn.io` / `8428` | Hub; the inventory address is used when known |
| `collector_wal_max_keepalive_time` | `72h` | Buffer window while the hub is unreachable |
| `collector_pve_scrape_interval` | `60s` | Proxmox API scrape interval |

Per-module Proxmox API credentials are looked up as `<module>_exporter_token_value` (inline vault values in the collector's `podman.yml`); the exporter config is rendered from `host_vars/<host>/files/pve-exporter.yml.j2`.

## Deploying

```bash
# from ansible/
ansible-playbook playbooks/lxc/deploy_collector.yml -e target=collector01.aah.muffn.io -e dispatch_fail_offline=true
```

Tags: `alloy` (this role), `deploy` (podman apps), `repo`, `install`, `config`, `service`, `verify`. Dispatch: changes to the role, the topology file and a collector's `podman.yml` or `files/` run this playbook (`ops/dispatch_map.yml`).

## Operating

- Status and pipeline: `curl -s localhost:12345/metrics | grep -E '^(up|prometheus_remote_storage_samples_pending)'` on the collector; the Alloy UI is on the same loopback port.
- Buffer on disk: `du -sh /var/lib/alloy/data/prometheus.remote_write.hub`. It stays small while the hub is reachable and grows by roughly 6 bytes per buffered sample while it is not.
- Adding a site-local exporter later (OPNsense, json_exporter): add it to the collector's `podman_apps` bound to loopback and add its scrape job to the template.
