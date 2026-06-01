# Infrastructure

A homelab infrastructure repository managing Proxmox VE hosts, LXC containers, and applications via Ansible and Terraform.

## Structure

```
infra/
├── ansible/
│   ├── inventory/          # Hosts, group_vars, host_vars
│   ├── playbooks/          # Entrypoint playbooks (pve/, lxc/, app/)
│   └── roles/              # Reusable roles (proxmox/, apps/, linux/)
├── tf/                     # Terraform for LXC/VM provisioning
├── ops/                    # CI dispatch scripts
└── secrets/                # Encrypted secrets (git-crypt)
```

## Secrets

Sensitive values (API keys, tokens, domain names, etc.) are split across two mechanisms:

- **Ansible Vault** — encrypts individual variable values inline with `!vault` tags
- **git-crypt** — encrypts whole files (e.g. `bindings.yml` files containing app domain names and other recon-adjacent data)

Example files are provided alongside encrypted ones for reference.

## CI / Auto-deploy

Pushes to `main` trigger `ops/dispatch.py`, which diffs changed files against a path→playbook map in `ops/dispatch_map.yml` and runs only the affected playbooks. Secrets are unlocked via `GIT_CRYPT_KEY` and `VAULT_PASSWORD` environment secrets on the runner.

## Monitoring

Metrics are collected by VictoriaMetrics, scraped via a Prometheus-compatible config rendered from a Jinja2 template at deploy time.

To register a scrape target for any host, create a `monitoring.yml` in that host's `host_vars` directory:

```yaml
# ansible/inventory/host_vars/<hostname>/monitoring.yml
prometheus_scrape_targets:
  - job_name: my_exporter
    targets:
      - <hostname>:<port>
    # Optional:
    scrape_interval: 30s
    labels:
      env: homelab
```

The Prometheus config template iterates `prometheus_scrape_targets` across all hosts in inventory automatically — no changes to the metrics host config are needed. CI redeploys the metrics stack whenever any `monitoring.yml` changes.

## TODO

- [ ] Deploy tf config for full VM deployment and management.
- [ ] Find / Write a tf provider that has full functionality for Proxmox LXC containers.
- [ ] Tweak Renovate config to ensure automerge is doing its thing correctly.
- [X] Fix/Understand why `netavark` is accumulating stale nftables DNAT rules when `state: restarted` is used, or any kind of redeploy happens.
  - Resolved by reloading Podman network rules after container restarts.
