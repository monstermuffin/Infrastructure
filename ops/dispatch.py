#!/usr/bin/env python3

import fnmatch
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not available. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DISPATCH_MAP = REPO_ROOT / "ops" / "dispatch_map.yml"
OUTPUT_SCRIPT = Path("/tmp/dispatch_cmds.sh")
ANSIBLE_DIR = REPO_ROOT / "ansible"


def git_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def extract_limit(path: str, rule: dict) -> str | None:
    # Derive --limit value from a changed file path.
    if rule.get("limit"):
        return rule["limit"]

    if path.startswith("ansible/inventory/host_vars/"):
        remainder = path.removeprefix("ansible/inventory/host_vars/")
        # Dir type: pve02.aah.muffn.io/lxc.yml → pve02.aah.muffn.io
        if "/" in remainder:
            return remainder.split("/")[0]
        # File type: radarr01.aah.muffn.io.yml → radarr01.aah.muffn.io
        return remainder.removesuffix(".yml")

    return None


def build_command(rule: dict, path: str) -> str | None:
    # Build ansible-playbook command string from matched rule.
    action = rule.get("action")

    if action == "playbook_self":
        return f"ansible-playbook {path}"

    playbook = rule.get("playbook")
    if not playbook:
        return None

    limit = extract_limit(path, rule)
    cmd = f"ansible-playbook {playbook}"
    if limit:
        cmd += f" --limit '{limit}'"
    return cmd


def main(dry_run: bool = False) -> None:
    changed = git_changed_files()
    if not changed:
        print("No changed files — nothing to dispatch.")
        _write_script(["echo 'Nothing to run.'"], dry_run)
        return

    with open(DISPATCH_MAP) as f:
        config = yaml.safe_load(f)

    rules = config["rules"]
    # Use dict keyed by command string to deduplicate while preserving order
    commands: dict[str, str] = {}

    for path in changed:
        for rule in rules:
            if fnmatch.fnmatch(path, rule["pattern"]):
                cmd = build_command(rule, path)
                if cmd and cmd not in commands:
                    commands[cmd] = path
                break  # first matching rule wins

    if not commands:
        print("Changed files matched no dispatch rules — nothing to run.")
        _write_script(["echo 'No matching rules.'"], dry_run)
        return

    print(f"Dispatching {len(commands)} playbook run(s):")
    for cmd, src in commands.items():
        print(f"  [{src}] → {cmd}")

    script_lines = [cmd for cmd in commands]
    _write_script(script_lines, dry_run)


def _write_script(commands: list[str], dry_run: bool) -> None:
    lines = ["#!/bin/bash", "set -euo pipefail", f"cd {ANSIBLE_DIR}", ""]
    for cmd in commands:
        lines.append(f'echo "==> {cmd}"')
        lines.append(cmd)
        lines.append("")

    script = "\n".join(lines)

    if dry_run:
        print("\n--- dispatch script ---")
        print(script)
        return

    OUTPUT_SCRIPT.write_text(script)
    OUTPUT_SCRIPT.chmod(0o755)
    print(f"Written: {OUTPUT_SCRIPT}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
