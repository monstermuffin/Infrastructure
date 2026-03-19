# pve_lxc_device_passthrough

Device passthrough for Proxmox LXC containers — GPUs, TPUs, USB devices.

Handles character device passthrough via `pct set --devN`, container group creation, and user-to-group assignment.

## USB Passthrough in LXC

USB passthrough via `pct set --usb0` is **not supported in LXC** (QEMU VMs only). For USB devices like the Coral TPU, create a stable device node with a udev rule and pass through the character device instead:

```yaml
pve_lxc_devices:
  - type: "device"
    path: "/dev/coral-tpu"  # stable symlink from udev rule
    gid: 46
```

## Variables

See [defaults/main.yml](defaults/main.yml) for all variables and examples.

### Required

| Variable | Description |
|---|---|
| `pve_lxc_device_enabled` | Must be `true` to run |
| `pve_lxc_vmid` | Container VMID |
| `pve_lxc_proxmox_node` | Proxmox node FQDN |
| `pve_lxc_devices` | List of devices to pass through |

### Optional

| Variable | Default | Description |
|---|---|---|
| `pve_lxc_device_action` | `present` | `present` or `absent` |
| `pve_lxc_device_auto_restart` | `false` | Restart container after config |
| `pve_lxc_device_validate` | `true` | Check device exists on host |
| `pve_lxc_device_backup_config` | `true` | Backup LXC conf before changes |
| `pve_lxc_device_groups` | `[]` | Groups to create in container |
| `pve_lxc_device_users` | `[]` | Users to add to groups |

## Examples

### Intel iGPU

```yaml
pve_lxc_device_enabled: true
pve_lxc_vmid: "110"
pve_lxc_proxmox_node: "pve01.lcy.muffn.io"
pve_lxc_device_auto_restart: true

pve_lxc_devices:
  - type: "device"
    path: "/dev/dri/renderD128"
    gid: 109
  - type: "device"
    path: "/dev/dri/card0"
    gid: 109

pve_lxc_device_groups:
  - name: "render"
    gid: 109

pve_lxc_device_users:
  - username: "frigate"
    groups: ["render"]
```

### Combined iGPU + Coral TPU (Frigate)

```yaml
pve_lxc_devices:
  - type: "device"
    path: "/dev/dri/renderD128"
    gid: 109
  - type: "device"
    path: "/dev/dri/card0"
    gid: 109
  - type: "device"
    path: "/dev/coral-tpu"
    gid: 46

pve_lxc_device_groups:
  - name: "render"
    gid: 109
  - name: "video"
    gid: 44
  - name: "plugdev"
    gid: 46

pve_lxc_device_users:
  - username: "frigate"
    groups: ["render", "video", "plugdev"]
```

## Tags

| Tag | Description |
|---|---|
| `configure`, `device`, `passthrough` | Configure device passthrough |
| `remove`, `cleanup` | Remove device passthrough |
| `groups`, `permissions` | Group management in container |
| `users` | User group assignments |

## Notes

- Container is stopped during device passthrough config (required by `pct set`)
- Slots auto-assigned from list index if not specified
- Group/user config only runs if container is started after changes
- Coral USB TPU changes VID:PID after init (`1a6e:089a` → `18d1:9302`) — use a udev rule for a stable device node instead
