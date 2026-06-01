# wgtun role

Deploys the wgtun stack: gluetun (VPN gateway) + qbittorrent + firefox + qsticky + filebrowser + qbittorrent-exporter.

## Networking issues(?)

### gluetun: FIREWALL_INPUT_PORTS is required

qbittorrent/firefox WebUIs are unreachable from the LAN even though ports are published and containers are running.

Gluetun sets up a policy routing rule that sends all traffic destined for RFC1918 subnets (`FIREWALL_OUTBOUND_SUBNETS=10.0.0.0/8`) via routing table 199. However, it does not populate table 199 with a return route. Responses from qbittorrent/firefox fall through to gluetun's catch-all rule (`not fwmark 0xca6c lookup 51820`) and exit via `tun0` (the VPN tunnel) instead of `eth0` back to the LAN. The client never receives a response.

To fix, set `FIREWALL_INPUT_PORTS` in gluetun's env to the container-side port numbers of any services running in gluetun's network namespace. This causes gluetun to populate table 199 with the correct gateway and mark connections so responses return via `eth0`.

```yaml
env:
  FIREWALL_INPUT_PORTS: "8080,5800,8888"  # qbittorrent, firefox, http proxy
```

### qbittorrent: Host header validation and auth bypass

- qbittorrent returns `401 Unauthorized` from the LAN when accessed through a port mapping.
- qbittorrent skips login entirely for clients on a previously trusted subnet.

qbittorrent 5.x validates the HTTP `Host` header against its own listen address/port. When accessed via a port-mapped address (e.g. `10.82.10.117:8081`), the Host header doesn't match qbittorrent's internal address (`10.88.0.10:8080`), causing a 401. Separately, qBittorrent persists `WebUI\AuthSubnetWhitelist*` in its own config, so an old trusted subnet can silently bypass auth until the setting is explicitly cleared. 

To fix, disable host header validation and explicitly manage the auth-bypass whitelist. Would optionally just be easier to keep the default port but due to migration from VM it was kept.

Config keys managed by the role:
- `WebUI\HostHeaderValidation=false`
- `WebUI\AuthSubnetWhitelistEnabled=false`

Set via the API (or directly in `/opt/wgtun/qbittorrent/qBittorrent/qBittorrent.conf` under `[Preferences]`):
```
[Preferences]
WebUI\HostHeaderValidation=false
WebUI\AuthSubnetWhitelistEnabled=false
WebUI\Address=0.0.0.0
```

## VueTorrent

VueTorrent managed as per `/opt/wgtun/qbittorrent/vuetorrent` by cloning the upstream `latest-release` branch and pointing qBittorrent's alternative WebUI to `/config/vuetorrent`.

### qbittorrent-exporter

`ghcr.io/esanchezm/prometheus-qbittorrent-exporter` exposes prometheus metrics on host port `9171` via gluetun. Uses qBittorrent API key (`QBITTORRENT_API_KEY`) for authentication.
