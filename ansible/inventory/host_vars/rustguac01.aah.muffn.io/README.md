# rustguac01

Browser RDP gateway. [rustguac](https://github.com/sol1/rustguac) (web UI plus bundled guacd) signs users in through Pocket ID and keeps its saved connections in OpenBao. Both run as Podman containers on one LXC, on a private `rustguac` network; OpenBao is not published on the host.

| Piece | Where |
| --- | --- |
| LXC definition | `group_vars/aah-cluster01/lxc/apps/rustguac01.yml` |
| Containers, secrets | `podman.yml` (this directory) |
| rustguac config | `files/config.toml.j2` (no secrets; they come from the container env) |
| Ingress / tunnel | `rustguac` entry in `group_vars/tag_app_ingress_aah/bindings.yml`, route in `tf/cloudflare.tf` |

## How it fits together

- **Login:** rustguac does the OIDC authorization-code flow with PKCE against Pocket ID. Pocket ID decides who may sign in (the client is restricted to a user group), so `auto_create_users = true`: the first login creates an `operator` account pinned to that Pocket ID `sub`. Operators can only open saved connections. Grant admin with `set-role` or a group mapping (step 5).
- **Connections page:** needs a Vault-compatible KV v2 store. OpenBao runs single-node with integrated (raft) storage and a static-key auto-unseal, so a restart needs no manual unseal. The key sits in the container env next to the data it protects, so anyone with root on this LXC can read the store; that is accepted for a single-host store.
- **Recordings** live in the `rustguac-recordings` named volume: rustguac sets the directory to 0750 at startup, which a bind mount would have reset (and restarted the service) on every deploy.
- **Image users:** rustguac runs as 996:996 and OpenBao as 100:1000. Both are pinned in `podman.yml`. Check them against the new image before bumping a major version, or bind mounts become unwritable.
- **RDP targets:** `rustguac_rdp_allowed_networks` in `podman.yml` is the allowlist of hosts rustguac may open RDP to. It starts as loopback only. Add the target machine as a /32.

## First-time setup

Run on the LXC after the first deploy. rustguac starts without OIDC or the Connections page until steps 2 to 4 are done.

1. **Save the break-glass API key.** On first start rustguac prints an admin API key once. The container is removed on restart, so read it from the journal: `journalctl -u rustguac | grep -A1 'API Key'`. Store it in the password manager. If it is lost, create another with `podman exec rustguac /opt/rustguac/bin/rustguac --config /opt/rustguac/config.toml add-admin --name <name>`.

2. **Initialise OpenBao (once).** With a static seal, init returns a recovery key and a root token, not unseal keys. Store both.

   ```bash
   podman exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator init -recovery-shares=1 -recovery-threshold=1
   ```

3. **Provision the secret store.** Use the root token from step 2 for this block only:

   ```bash
   B='podman exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=<root token> openbao bao'
   $B secrets enable -path=secret kv-v2
   $B policy write rustguac - <<'EOF'
   path "secret/data/rustguac/*"     { capabilities = ["create", "read", "update", "delete"] }
   path "secret/metadata/rustguac/*" { capabilities = ["list", "read", "delete"] }
   EOF
   $B auth enable approle
   $B write auth/approle/role/rustguac token_policies=rustguac token_ttl=1h token_max_ttl=4h secret_id_ttl=0
   $B read -field=role_id auth/approle/role/rustguac/role-id
   $B write -field=secret_id -f auth/approle/role/rustguac/secret-id
   $B token revoke -self
   ```

   The last command revokes the root token. A new one can be generated from the recovery key (`bao operator generate-root`).

4. **Pocket ID client.** Create a confidential client with callback URL `https://<public host>/auth/callback`, scopes `openid profile email groups`, and restrict it to the user group allowed to use this. Then set in `podman.yml` (encrypt secrets with `ansible-vault encrypt_string`):

   ```yaml
   rustguac_oidc_client_id: <client id>
   rustguac_oidc_client_secret: !vault |  # client secret
   rustguac_vault_role_id: <role id from step 3>
   rustguac_vault_secret_id: !vault |     # secret id from step 3
   ```

   Deploy again; the config template then renders the `[oidc]` and `[vault]` blocks.

5. **Make yourself an admin.** Sign in once through Pocket ID, then promote the account (or map a Pocket ID group to admin so it applies at login):

   ```bash
   R='podman exec rustguac /opt/rustguac/bin/rustguac --config /opt/rustguac/config.toml'
   $R set-role --email <your email> --role admin
   $R map-group --group <pocket id group> --role admin
   ```

6. **Add the RDP connection** on the Connections page (host, port, credentials). The credentials are stored in OpenBao and never reach the browser.

## Contractor access (live state in OpenBao, not in git)

- Folder `lutron`, visible only to the Pocket ID group `lutron-users`. That group must also be assigned to the rustguac client in Pocket ID, or its members cannot sign in.
- Entry `windows-desktop`: RDP to the target with a stored low-privilege account. The password is set in the Connections page (edit the entry), never in git.
- New users start as `operator`: they can open entries in folders their groups allow and cannot edit anything.
- To give someone access: add them to `lutron-users` in Pocket ID. To remove it: take them out of the group; an existing session ends within its session limit, so also disable the account with `disable-user --email <email>` if it must stop at once.

## Windows side

- Enable Remote Desktop on the target and allow TCP 3389 only from this LXC.
- The network between this LXC's VLAN and the target's VLAN must allow TCP 3389.
- Add the target's address to `rustguac_rdp_allowed_networks`.

## Operations

- **Logs:** `journalctl -u rustguac -u openbao`.
- **Restart:** a restart of a container with a published port can leave the port dead until the guest reboots (stale netavark NAT); see `.agents/monitoring.md`.
- **Backups:** the LXC replicates and backs up like the other app guests. State is `/opt/rustguac/data` (users, tokens, history) and `/opt/openbao/file` (all saved connections).
- **OpenBao init output:** `/root/openbao-init.json` on the guest holds the recovery key (and the revoked root token) from the one-time init. Move the recovery key to the password manager, then delete the file.
- **Unseal key rotation:** see the OpenBao static seal documentation (`previous_key` / `previous_key_id`). Changing the key without that procedure makes the store unreadable.
- **Nested folders:** rustguac encodes `/` as `%2F` in nested folder paths. If subfolder clicks return 404 after a Traefik upgrade, check Traefik's encoded-character handling; flat folders are unaffected.
