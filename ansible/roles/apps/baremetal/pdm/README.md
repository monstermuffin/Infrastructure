# pdm

Installs and configures Proxmox Datacenter Manager (PDM) and bootstraps a pdm realm user.

1. Adds the PDM no-subscription APT repository and disables the enterprise repo
2. Installs  and enables/starts `proxmox-datacenter-manager` and `proxmox-datacenter-manager-ui`
4. Optionally creates an `admin@pdm` realm user with a set password and Administrator ACL bypassing need for root lxc pass

## Usage

```yaml
pdm_enabled: true

pdm_admin_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...
```

```bash
ansible-playbook playbooks/lxc/deploy_pdm.yml
ansible-playbook playbooks/lxc/deploy_pdm.yml --tags auth
```

Web UI is at `https://<host>:8443`.

## PDM Bootstrap Process

PDM has two services:

- **`proxmox-datacenter-privileged-api`** — runs as root, handles privileged ops, exposes a Unix socket at `/run/proxmox-datacenter-manager/priv.sock`
- **`proxmox-datacenter-api`** — runs as `www-data` with zero Linux capabilities (`CapEff: 0`), handles all HTTP/HTTPS traffic and proxies privileged requests to the above via the socket

Authentication for the `pdm` realm is handled by the unprivileged API reading `shadow.json` directly. Because the process has no capabilities and runs as `www-data`, the file must be readable by that user.

The file uses Proxmox's SectionConfig format. Properties must be indented with a real tab character and have no colon after the key name:

```
user: admin@pdm
	enable 1
	comment Ansible Admin
```

The parser errors are logged to `/var/log/proxmox-datacenter-manager/api/auth.log`.

`shadow.json` must be `root:www-data 640`

The file is owned `root:root 600` if PDM creates it itself (e.g. via the web UI), but the unprivileged API process (`www-data`) cannot read a `600` file it doesn't own. It needs group read:

```bash
chown root:www-data /etc/proxmox-datacenter-manager/access/shadow.json
chmod 640 /etc/proxmox-datacenter-manager/access/shadow.json
```

Ansible handles this via `grp.getgrnam('www-data')`.

`shadow.json` key is the username, not the userid

The JSON key must be just `"admin"` without the realm. The auth code calls `userid.name()` to strip the realm before the lookup:

```json
{
  "admin": "$6$salt$hash..."
}
```
