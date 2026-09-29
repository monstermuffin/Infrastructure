# PveNodeDown

## What it means

The Proxmox cluster has reported a node as offline for 5 minutes. Guests that were running on it are unavailable until the node returns or HA restarts them on another node. If the node was the only one holding a recent replica of a guest, that guest may restart with data from the last replication run.

## First three checks

1. Is the node reachable at all? `ping <node>` and `ssh root@<node>`. A pingable node with a hung web UI is different from a powered-off one.
2. Cluster view from a surviving node: `pvecm status` (quorum) and `ha-manager status` (which guests were fenced or recovered).
3. Metric: `pve_up{id="node/<node>"}` in Grafana Explore. If it flaps, look at the network path rather than the node.

## Common causes and fixes

- Planned reboot or kernel update that is taking longer than usual: wait for it, then confirm guests started.
- Network or switch problem isolating the node: the node is fine but not in quorum. Fix the link; do not force quorum unless you are sure the other side is down.
- Hardware fault or power loss: use the out-of-band console if available. After recovery, check `ha-manager status` and replication (`pvesr status`) before moving guests back.

## When it is safe to silence

During planned maintenance on the node. Create an Alertmanager silence on `alertname="PveNodeDown"` and `node="<node>"` with an expiry and a comment.
