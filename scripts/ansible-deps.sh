#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$SCRIPT_DIR/../ansible"

echo "Installing Ansible collections..."
ansible-galaxy collection install -r "$ANSIBLE_DIR/requirements.yml" "$@"

echo "Installing Ansible roles..."
ansible-galaxy role install -r "$ANSIBLE_DIR/requirements.yml" --roles-path ~/.ansible/roles "$@"

echo "Done."
