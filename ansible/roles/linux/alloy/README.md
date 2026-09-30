# alloy

Grafana Alloy on every Linux host. It collects node metrics in two sampling tiers, per-service (systemd unit) metrics on hosts that run podman apps, and optional per-host scrapes, and pushes them to the collector of the host's site (`roles/apps/collector`), which forwards them to the hub. Nothing scrapes the host and no port is opened on it.

## What it deploys

- The Grafana apt repository (deb822 source, `amd64` or `arm64` picked from the host) and the `alloy` package, pinned by `alloy_version`. The package is large (about 170 MB to download, 560 MB installed): the role refuses to install when `/` has less than `alloy_min_free_mb` (1200) free.
- `/etc/default/alloy`: `CONFIG_FILE=/etc/alloy` (Alloy loads every `*.alloy` file in the directory), usage reporting off, status endpoint on loopback (`127.0.0.1:12345`), an optional `GOMEMLIMIT`. Alloy runs as the packaged unprivileged `alloy` user.
- Config fragments in `/etc/alloy`:

| Fragment | On | Contents |
|---|---|---|
| `base.alloy` | all | identity labels (`site`, `host`, `kind`), the buffered push to the collector, Alloy's own health series (`job="alloy"`) |
| `node.alloy` | all | two embedded node-exporter instances: fast (15s: `cpu`, `netdev`, `pressure`, `loadavg`, job `node_fast`) and slow (60s: file systems, memory, network, `systemd` restricted to an allowlist, and more; job `node_slow`) |
| `units.alloy` | hosts with podman apps | embedded cAdvisor in raw cgroup mode, one series set per systemd service with a `unit` label (30s, job `units`) |
| `extras.alloy` | hosts with `monitoring_extra_scrapes` | one scrape per entry |

  On kind `pve` the slow tier also runs `zfs`, `hwmon`, `thermal_zone`, `nvme` and `cpufreq`. On kind `lxc` it leaves out `diskstats`: a container sees every disk of its host there. Collector hosts also load `collector.alloy` (role `apps/collector`) from the same directory; the two never share a component name, and the collector pushes its own host metrics to its own site receiver like any other host.
- Each set of files is rendered into `/var/lib/alloy/staging/<set>`, checked as a whole with `alloy validate`, and only then copied into `/etc/alloy`. A failed check leaves the running config untouched.
- A config change is applied with a **reload**. The package or `/etc/default/alloy` changing restarts the service. A restart takes about 20 s and drops the samples that were not yet sent (the buffer is read again only from its newest segment), so avoid version bumps during a collector outage.

## Variables

Fleet-wide values live in `inventory/group_vars/monitored.yml` (the `monitored` group, defined in `inventory/ephemeral_groups.yml`; deliberately not `all.yml`). Role mechanics are defaults in `defaults/main.yml`.

| Variable | Where | Meaning |
|---|---|---|
| `monitoring_enabled` | `monitored.yml` (`false` for the `pi` group) | `false` removes the host fragments and stops Alloy (a collector keeps running). Set it per host in `host_vars/<host>/alloy.yml` |
| `monitoring_collector_urls` / `monitoring_collector_url` | `monitored.yml` | push URL per site, and the one picked for the host from its site |
| `monitoring_site`, `monitoring_kind` | `monitored.yml` | derived from the inventory groups (`tag_site_*`, `aah`/`lcy`/`nbg1`; `pve`, `vps`, `pi`, `vm`, `lxc`) |
| `monitoring_systemd_units`, `monitoring_systemd_units_pve` | `monitored.yml` | units the node `systemd` collector reports (names without `.service`). Podman app names of the host are added automatically |
| `monitoring_systemd_units_extra` | `host_vars/<host>/alloy.yml` | more units for one host |
| `monitoring_extra_scrapes` | `host_vars/<host>/alloy.yml` | see below |
| `alloy_version` | role defaults | pinned package version (Renovate) |
| `alloy_gomemlimit` | role defaults | optional Go memory limit, e.g. `96MiB` (restarts Alloy when changed) |
| `alloy_wal_max_keepalive_time` | role defaults | how long unsent samples are kept while the collector is unreachable (72h; the design minimum is 48h) |

### monitoring_extra_scrapes

```yaml
monitoring_extra_scrapes:
  - job: myapp               # required; becomes the job label
    address: 127.0.0.1:9100  # required; the target to scrape (from the host itself)
    instance: myhost:9100    # optional instance label, default the address (set it to keep an old series identity)
    path: /metrics           # default /metrics
    interval: 60s            # default 60s
    timeout: 10s             # default 10s
    scheme: http             # default http
    params: {module: [x]}    # optional query parameters
    labels: {app: myapp}     # optional static labels (site, host, kind, job, instance are ignored)
    keep: "metric_a|metric_b"  # optional metric-name regex to keep (up is always kept)
```

## Deploying

```bash
# from ansible/. One host (an unreachable host is an error with dispatch_fail_offline):
ansible-playbook playbooks/linux/deploy_alloy.yml --limit radarr01.aah.muffn.io -e dispatch_fail_offline=true
# a bounded set, with the play's batch size (default 10); collectors always go last, one at a time:
ansible-playbook playbooks/linux/deploy_alloy.yml --limit 'tag_site_lcy' -e alloy_serial=5
```

Tags: `alloy` (the role), `repo`, `install`, `config`, `service`, `verify`. Dispatch (`ops/dispatch_map.yml`): changes to the role, the playbook and `group_vars/monitored.yml` deploy the whole `monitored` group; `host_vars/<host>/alloy.yml` deploys that host.

## Operating

- Health: `systemctl status alloy`, `curl -s localhost:12345/-/ready`, and `journalctl -u alloy -n 100` on the host. Delivery: `time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds{job="alloy"}` in Grafana, or the Fleet dashboard.
- Check a config by hand: `alloy validate /etc/alloy` (the whole directory), then `systemctl reload alloy`; a config that fails to load leaves the running one in place.
- Buffer on disk: `du -sh /var/lib/alloy/data/prometheus.remote_write.push`. It stays small while the collector is reachable and grows by about 6 bytes per buffered sample while it is not.

## Removing Alloy from a host

Stops the pushes for that host; the collector and everything else keep running.

1. Preferred, to keep it reversible: set `monitoring_enabled: false` in `host_vars/<host>/alloy.yml` and deploy the host. Fragments go, the service is stopped and disabled, the package stays.
2. Full removal by hand, as root on the host:

```bash
systemctl disable --now alloy
apt-get purge -y alloy
rm -rf /etc/alloy /var/lib/alloy /etc/default/alloy /var/lib/prometheus/node-exporter \
       /etc/apt/sources.list.d/grafana.sources /etc/apt/keyrings/grafana.asc
apt-get update
userdel alloy   # optional
```

   Never do this on a collector without meaning to: it also removes the site's push receiver and every host at the site stops delivering (they buffer for 72h).
3. Remove the host from `monitored` (or set `monitoring_enabled: false`) so the next deploy does not bring it back. Its series simply stop; the hub keeps the history.

To stop the whole fleet quickly, set `monitoring_enabled: false` in `group_vars/monitored.yml` and deploy (`--limit monitored`), or stop `alloy` on the collectors to refuse every push at once.
