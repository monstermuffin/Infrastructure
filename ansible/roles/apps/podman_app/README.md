# podman_app

Deploys containerised apps via rootful Podman + systemd Quadlet.

## Usage

```yaml
# host_vars/myhost.yml
podman_apps:
  radarr:
    # --- role / lifecycle (deploy_app.yml, main.yml)
    enabled: true
    service_enable: true   # systemd enable on boot (default: true)
    service_start: true    # start/manage in this play; set false to only write Quadlet (default: true)
    uid: 65534             # host dir ownership for auto-created bind mounts (default: 0)
    gid: 65534             # (default: 0)

    # --- Proxmox note (note_app.yml; tag: note)
    display_name: Radarr   # lxc note title; default: app key title-cased

    # --- Container / Quadlet [Container] (app.container.j2)
    description: Radarr    # systemd unit Description; default: title-cased app key
    after: []              # extra After= units, e.g. [mnt-nas.mount]
    requires: []          # Requires= units
    image: ghcr.io/home-operations/radarr
    tag: rolling           # image tag (default: latest)
    container_name: radarr  # ContainerName=; default: app key
    user: "65534:65534"    # Quadlet User= (optional; unlike uid/gid for host dirs)
    # port: used for PublishPort, wait_for, and Proxmox note URL (omit if none)
    port: 7878
    container_port: 7878   # container side when host port differs; default: same as port
    # Multi mapping (takes precedence over port/container_port); ignored when network_mode: host
    # ports:
    #   - "7878:7878"
    #   - "9888:9888"
    network_mode: bridge   # e.g. bridge, host; if host, PublishPort is omitted
    # network: mypodman_net # named network (used if network_mode unset)
    volumes:
      - /opt/radarr/config:/config
      - /movies:/movies
    tmpfs:
      - /tmp:size=256M,mode=1777
    env:
      TZ: Europe/London
    # exec: /usr/bin/custom-entrypoint   # optional Container Exec=
    devices:
      - /dev/dri/renderD128
    cap_add:
      - NET_BIND_SERVICE
    shm_size: 256m
    privileged: false      # true → SecurityLabelDisable=true
    security_label_disable: false  # true → SecurityLabelDisable=true (without full privileged)
    labels:
      io.containers.autoupdate: registry

    # --- [Service]
    restart: always        # systemd Restart= (default: always)
    restart_sec: 5         # optional RestartSec=
```

## Options

- `enabled`
- `service_enable` / `service_start` — systemd enable and whether the role starts the service (defaults: `true` / `true`)
- `image` / `tag` — image ref (`tag` defaults to `latest`)
- `description` — unit `Description=` (default: title-cased app key)
- `after` / `requires` — lists for `After=` / `Requires=` in the unit
- `display_name` — Proxmox note title (default: title-cased app key); note tasks require `port`
- `container_name` — Quadlet `ContainerName=` (default: app key)
- `user` — Quadlet `User=` inside the container (optional; separate from `uid`/`gid` for host paths)
- `port` / `container_port` — single `PublishPort` as `port:container_port` (default container side: same as `port`)
- `ports` — explicit `PublishPort` list e.g. `["8080:80"]`; wins over `port`/`container_port`; skipped when `network_mode: host`
- `network_mode` / `network` — `Network=` line; if `network_mode` is set it wins, else `network` (named net)
- `volumes` — `host:container[:opts]`; host dirs are created when safe (not under `/dev`, `/proc`, …)
- `tmpfs` — list of `Tmpfs=` paths (e.g. `/tmp:size=256M`)
- `env` — environment dict
- `exec` — optional `Exec=` (container command)
- `devices` / `cap_add` — `AddDevice=` / `AddCapability=` lists
- `shm_size` — `ShmSize=` (e.g. `256m`)
- `privileged` / `security_label_disable` — either sets `SecurityLabelDisable=true`
- `labels` — Quadlet `Label=` key/value dict
- `restart` / `restart_sec` — `Restart=` and optional `RestartSec=`
- `uid` / `gid` — ownership for auto-created bind mount directories on the host (defaults: `0`)

## Lifecycle

The role attempts to reconcile desired state in `podman_apps` against actual state (Quadlet files on disk) on every run.

## Tags

- `deploy` — full deploy
- `image` — pull image
- `note` — update PVE container notes

## TODO

- [ ] Fix/Understand why `netavark` is accumulating stale nftables DNAT rules when `state: restarted` is used, or any kind of redeploy happens.
  - Current 'workaround' is rebooting the LXC.