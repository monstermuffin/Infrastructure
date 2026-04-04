#!/usr/bin/env python3
# Generate tf/lxc_dns.auto.tfvars.json from Ansible LXC inventory.

# Scans all pve_lxcs_* variable files across clusters and standalone PVE hosts,
# extracts hostname + network_ip, and writes a JSON tfvars file consumed by
# tf/technitium.tf to register LXC A records in Technitium DNS.

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not available.", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "tf" / "lxc_dns.auto.tfvars.json"

# Ignore unknown YAML tags (e.g. !vault encrypted values)
yaml.add_multi_constructor("", lambda loader, tag, node: loader.construct_scalar(node), Loader=yaml.SafeLoader)

LXC_GLOBS = [
    "ansible/inventory/group_vars/*/lxc/**/*.yml",
    "ansible/inventory/host_vars/pve*/lxc/*.yml",
]


def find_lxc_files() -> list[Path]:
    files = []
    for pattern in LXC_GLOBS:
        files.extend(REPO_ROOT.glob(pattern))
    return sorted(files)


def parse_record(hostname: str, network_ip: str) -> dict | None:
    """Derive a DNS record dict from an LXC hostname and network_ip."""
    if not hostname or not network_ip:
        return None
    # Skip Jinja2 template values that haven't been resolved
    if "{{" in hostname or "{{" in network_ip:
        return None
    parts = hostname.split(".", 1)
    if len(parts) != 2:
        return None
    name, zone = parts
    ip = network_ip.split("/")[0]
    return {"name": name, "zone": zone, "ip": ip}


def generate_records() -> list[dict]:
    records = []
    seen = set()

    for path in find_lxc_files():
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"WARNING: skipping {path}: {e}", file=sys.stderr)
            continue

        for key, value in data.items():
            if not key.startswith("pve_lxcs_") or not isinstance(value, dict):
                continue
            for lxc_name, lxc in value.items():
                if not isinstance(lxc, dict):
                    continue
                record = parse_record(
                    lxc.get("hostname", ""),
                    lxc.get("network_ip", ""),
                )
                if record is None:
                    continue
                key_tuple = (record["name"], record["zone"])
                if key_tuple in seen:
                    continue
                seen.add(key_tuple)
                records.append(record)

    return sorted(records, key=lambda r: (r["zone"], r["name"]))


def main() -> None:
    records = generate_records()
    OUTPUT.write_text(json.dumps({"lxc_dns_records": records}, indent=2) + "\n")
    print(f"Written {len(records)} records → {OUTPUT.relative_to(REPO_ROOT)}")
    for r in records:
        print(f"  {r['name']}.{r['zone']} → {r['ip']}")


if __name__ == "__main__":
    main()
