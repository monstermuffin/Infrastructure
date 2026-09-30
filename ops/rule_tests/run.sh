#!/usr/bin/env bash
# Check the alerting and recording rules of the hub without deploying them:
#   1. copy the hand-written rules (*.yml.static) and render the generated one
#      from the inventory,
#   2. `vmalert -dryRun` on all of them and `amtool check-config`,
#   3. run the unit tests in this directory with vmalert-tool.
#
# Needs vmalert-prod, vmalert-tool-prod and amtool (release binaries; set BIN
# to the directory that holds them) and ansible with access to the inventory.
#   BIN=~/bin ops/rule_tests/run.sh
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
hub="$repo/ansible/inventory/host_vars/victoriametrics01.aah.muffn.io/files"
bin="${BIN:-}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

for f in "$hub"/rules/*.yml.static; do
  cp "$f" "$work/$(basename "${f%.static}")"
done
(cd "$repo/ansible" && ansible-playbook "$here/render_generated.yml" -e "out=$work/host_generated.yml" >/dev/null || { echo "rendering the generated rules failed" >&2; exit 1; })

"${bin:+$bin/}vmalert-prod" -dryRun -rule="$work/*.yml"
"${bin:+$bin/}amtool" check-config "$hub/alertmanager.yml.static"

cp "$here"/*.test.yml "$work/"
cd "$work"
"${bin:+$bin/}vmalert-tool-prod" unittest --files="$work/*.test.yml" -disableAlertgroupLabel
