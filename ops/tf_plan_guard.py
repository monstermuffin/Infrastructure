#!/usr/bin/env python3
"""Exit 1 if a saved Terraform plan deletes or replaces resources.

Usage: tf_plan_guard.py <terraform dir> <plan file>

Used by run_dispatch.sh so unattended deploys only apply additive or
in-place changes. Destructive plans need a manual run with allow_destroy.
"""

import json
import subprocess
import sys

# Generated from LXC/VM inventory by gen_lxc_dns.py; removing a guest or
# changing its IP legitimately deletes or replaces its record.
AUTO_APPROVED_DELETE_TYPES = {"technitium_dns_zone_record"}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    tf_dir, plan = sys.argv[1], sys.argv[2]
    show = subprocess.run(
        ["terraform", f"-chdir={tf_dir}", "show", "-json", plan],
        capture_output=True, text=True, check=True,
    )
    changes = json.loads(show.stdout).get("resource_changes", [])

    blocked = []
    allowed = []
    for rc in changes:
        actions = rc.get("change", {}).get("actions", [])
        if "delete" not in actions:
            continue
        kind = "replace" if "create" in actions else "delete"
        entry = f"{kind}: {rc['address']}"
        if rc.get("type") in AUTO_APPROVED_DELETE_TYPES:
            allowed.append(entry)
        else:
            blocked.append(entry)

    for entry in allowed:
        print(f"auto-approved {entry}")
    if blocked:
        print("Plan contains destructive changes:")
        for entry in blocked:
            print(f"  {entry}")
        return 1
    print("Plan has no destructive changes outside the auto-approved types.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
