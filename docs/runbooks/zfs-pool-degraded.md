# ZfsPoolDegraded

## What it means

A ZFS pool on a Proxmox host has reported a state other than online for 5 minutes. Degraded means a device is missing or failing and the pool has lost redundancy (a stripe has none to lose: for it, any non-online state means data at risk). Faulted or unavailable means the pool may be unreadable, and every guest stored on it is affected.

## First three checks

1. On the host: `zpool status -v <pool>` shows the state, the affected device and any files with errors.
2. Device health: `smartctl -a /dev/<device>` for the device named in the status, and `dmesg -T | grep -iE "nvme|ata|zfs|i/o error" | tail -50`.
3. History: `zpool events -v | tail -50` and `journalctl -u zfs-zed --since "1 day ago"`, plus `node_zfs_zpool_state{host="<host>", zpool="<pool>"}` in Grafana Explore to see when it changed.

## Common causes and fixes

- A device dropped out (cable, slot, power): reseat it, then `zpool online <pool> <device>` and watch the resilver in `zpool status`.
- A failing device: replace it with `zpool replace <pool> <old> <new>`, and check backups are current first if the pool has no redundancy.
- Errors on a device that is otherwise fine: `zpool clear <pool>` after finding the cause, then `zpool scrub <pool>` to verify.
- A pool that did not import at boot: `zpool import` lists what is available; import it by name.

## When it is safe to silence

Only during planned work on the pool, for example a device replacement or a resilver you are watching. Create an Alertmanager silence on `alertname="ZfsPoolDegraded"` and `host="<host>"` with an expiry and a comment. Do not silence it to make a known-bad pool quiet.
