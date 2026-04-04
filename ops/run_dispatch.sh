#!/bin/bash
set -euo pipefail

# Unlock git-crypt and write vault password file
echo "$GIT_CRYPT_KEY" | base64 -d | git-crypt unlock -
echo "$VAULT_PASSWORD" > /tmp/.vault_password
chmod 600 /tmp/.vault_password

SHA=$(git rev-parse HEAD)
LAST_SHA_FILE="/opt/github-runner/last_dispatched_sha"
LAST_SHA=$(cat "$LAST_SHA_FILE" 2>/dev/null || echo "")

# Skip if already processed commit
if [ "$SHA" = "$LAST_SHA" ]; then
  echo "Skipping dispatch: commit $SHA already processed"
  exit 0
fi

GITHUB_REPO="monstermuffin/Infrastructure"
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

post_status "pending" "Dispatch running..."

run_ansible() {
  python3 ops/dispatch.py && bash /tmp/dispatch_cmds.sh
}

run_terraform() {
  python3 ops/gen_lxc_dns.py
  terraform -chdir=tf init -backend-config="path=/opt/github-runner/terraform.tfstate" -reconfigure -input=false
  terraform -chdir=tf apply -auto-approve -var-file=terraform.tfvars
}

if run_ansible && run_terraform; then
  echo "$SHA" > "$LAST_SHA_FILE"
  post_status "success" "Dispatch succeeded"
else
  post_status "failure" "Dispatch failed"
  exit 1
fi
