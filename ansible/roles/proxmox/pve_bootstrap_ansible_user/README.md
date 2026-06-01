# pve_bootstrap_ansible_user

Creates a dedicated ansible user on Proxmox hosts with SSH key auth and passwordless sudo.
It does not create a separate admin user.

## Usage

Run once as root to bootstrap hosts (from `ansible/`):

```bash
ansible-playbook playbooks/pve/bootstrap.yml \
  -e target_hosts=pve02.lcy.muffn.io \
  -k
```

On a fresh install, enterprise Proxmox APT sources are disabled automatically
before `apt` runs so cache updates do not fail with HTTP 401.

If bootstrap failed partway through, re-run the same command.
## Variables

```yaml
ansible_user_name: ansible
ansible_user_groups: [sudo]
ansible_authorized_keys: |
  ssh-ed25519 AAAA... ansible_new
  ssh-ed25519 AAAA... muffin@mbp.internal.muffn.io
```
