#!/bin/bash
set -euo pipefail

# Only run on pushes to main
if [ "${PUSHED_REF:-}" != "refs/heads/main" ]; then
  echo "Skipping dispatch: push was to ${PUSHED_REF:-unknown}, not refs/heads/main"
  exit 0
fi

# Unlock git-crypt and write vault password file
echo "$GIT_CRYPT_KEY" | base64 -d | git-crypt unlock -
echo "$VAULT_PASSWORD" > /tmp/.vault_password
chmod 600 /tmp/.vault_password

GITHUB_REPO="monstermuffin/Infrastructure"
SHA=$(git rev-parse HEAD)
CONTEXT="ansible/dispatch"

post_status() {
  local state=$1
  local description=$2
  curl -s -X POST \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"state\":\"${state}\",\"context\":\"${CONTEXT}\",\"description\":\"${description}\"}" \
    "https://api.github.com/repos/${GITHUB_REPO}/statuses/${SHA}" \
    > /dev/null
}

post_status "pending" "Ansible dispatch running..."

if python3 ops/dispatch.py && bash /tmp/dispatch_cmds.sh; then
  post_status "success" "Ansible dispatch succeeded"
else
  post_status "failure" "Ansible dispatch failed"
  exit 1
fi
