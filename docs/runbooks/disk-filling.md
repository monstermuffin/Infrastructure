# DiskFilling

## What it means

A file system on a host has had less than 10% of its space available for 15 minutes. Network file systems, tmpfs, overlays and the EFI partition are not judged. When the file system fills, writes fail: services stop, databases can be left corrupt, and on a root file system the host may stop accepting logins.

## First three checks

1. Which file system and how bad: `df -h <mountpoint>` on the host, and `df -i <mountpoint>` in case inodes ran out instead of space.
2. What is using it: `du -xh --max-depth=2 <mountpoint> | sort -h | tail -20`, or `ncdu -x <mountpoint>`.
3. Trend: `node_filesystem_avail_bytes{host="<host>", mountpoint="<mountpoint>"}` over the last 7 days in Grafana Explore, or the Host overview dashboard, to see whether it grew slowly or all at once.

## Common causes and fixes

- Logs: `journalctl --disk-usage`, then `journalctl --vacuum-size=200M`. For an application log, fix its rotation.
- Container images and layers on a podman host: `podman system df`, then `podman image prune -a` (removes images not used by a running container) and `podman system prune`.
- Package cache: `apt-get clean`.
- An application growing its own data (downloads, thumbnails, a database): move the data to bigger storage or trim it at the source.
- A guest's disk is simply too small: on Proxmox, `pct resize <vmid> rootfs +<size>G` for a container or grow the disk of a VM and its file system. Check the storage pool has room first.

## When it is safe to silence

While a known large cleanup or resize is under way. Create an Alertmanager silence on `alertname="DiskFilling"`, `host="<host>"` and `mountpoint="<mountpoint>"` with an expiry and a comment. If a volume is meant to run nearly full (a scratch area), tell the monitoring rules to skip that file system instead of silencing it repeatedly.
