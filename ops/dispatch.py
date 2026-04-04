#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not available.", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Loader that ignores unknown tags (e.g. !vault) so host_vars files parse without errors
_SafeLoader = yaml.SafeLoader
yaml.add_multi_constructor("", lambda loader, tag, node: loader.construct_scalar(node), Loader=_SafeLoader)
DISPATCH_MAP = REPO_ROOT / "ops" / "dispatch_map.yml"
OUTPUT_SCRIPT = Path("/tmp/dispatch_cmds.sh")


def git_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def extract_limit(path: str, rule: dict) -> str | None:
    if rule.get("limit"):
        return _expand_template(rule["limit"], path)

    if path.startswith("ansible/inventory/host_vars/"):
        remainder = path.removeprefix("ansible/inventory/host_vars/")
        # Dir type: pve02.aah.muffn.io/lxc.yml → pve02.aah.muffn.io
        if "/" in remainder:
            return remainder.split("/")[0]
        # File type: radarr01.aah.muffn.io.yml → radarr01.aah.muffn.io
        return remainder.removesuffix(".yml")

    return None


def _expand_template(val: str, path: str) -> str:
    # Expand {stem} to the filename stem (e.g. runner01 from .../runner01.yml).
    val = val.replace("{stem}", Path(path).stem)
    # Expand {group} to the group name immediately under group_vars/ in the path.
    parts = Path(path).parts
    if "group_vars" in parts:
        idx = parts.index("group_vars")
        if idx + 1 < len(parts):
            val = val.replace("{group}", parts[idx + 1])
    return val


def get_workdir(rule: dict, path: str) -> Path:
    # Explicit 'workdir' field in the rule takes precedence. Otherwise inferred from the top-level directory of the playbook or changed file path.
    if "workdir" in rule:
        return REPO_ROOT / rule["workdir"]
    ref = rule.get("playbook") or path
    top = ref.split("/")[0]
    candidate = REPO_ROOT / top
    return candidate if candidate.is_dir() else REPO_ROOT


def build_command(rule: dict, path: str) -> list[tuple[Path, str]]:
    workdir = get_workdir(rule, path)
    prefix = workdir.name + "/"
    action = rule.get("action")

    if action == "playbook_self":
        return [(workdir, f"ansible-playbook {path.removeprefix(prefix)}")]

    if action == "host_self":
        return _build_host_self_commands(path)

    playbook = rule.get("playbook")
    if not playbook:
        return []

    limit = extract_limit(path, rule)
    cmd = f"ansible-playbook {playbook.removeprefix(prefix)}"
    if limit:
        cmd += f" --limit '{limit}'"
    for key, val in rule.get("extra_vars", {}).items():
        cmd += f" -e {key}={_expand_template(val, path)}"
    return [(workdir, cmd)]


def _build_host_self_commands(path: str) -> list[tuple[Path, str]]:
    try:
        with open(REPO_ROOT / path) as f:
            host_vars = yaml.safe_load(f) or {}
    except FileNotFoundError:
        # File deleted — nothing to deploy
        return []

    limit = extract_limit(path, {})
    commands = []

    custom_playbook = host_vars.get("dispatch_playbook")
    if custom_playbook:
        workdir = get_workdir({"playbook": custom_playbook}, path)
        cmd = f"ansible-playbook {custom_playbook.removeprefix(workdir.name + '/')}"
        if limit:
            cmd += f" --limit '{limit}'"
        commands.append((workdir, cmd))

    if "podman_apps" in host_vars:
        podman_playbook = "ansible/playbooks/lxc/deploy_podman_app.yml"
        workdir = get_workdir({"playbook": podman_playbook}, path)
        cmd = f"ansible-playbook {podman_playbook.removeprefix(workdir.name + '/')}"
        if limit:
            cmd += f" --limit '{limit}'"
        commands.append((workdir, cmd))

    if not commands:
        print(f"  WARNING: {path} matched host_self but has no dispatch_playbook or podman_apps — skipping")

    return commands


def main(dry_run: bool = False) -> None:
    changed = git_changed_files()
    if not changed:
        print("No changed files — nothing to dispatch.")
        _write_script([], dry_run)
        return

    with open(DISPATCH_MAP) as f:
        config = yaml.safe_load(f)

    rules = config["rules"]
    # Dict keyed by "workdir:cmd" to deduplicate while preserving order
    commands: dict[str, tuple[Path, str]] = {}

    for path in changed:
        for rule in rules:
            if Path(path).match(rule["pattern"]):
                for workdir, cmd in build_command(rule, path):
                    key = f"{workdir}:{cmd}"
                    if key not in commands:
                        commands[key] = (workdir, cmd)
                break  # first matching rule wins

    if not commands:
        print("Changed files matched no dispatch rules — nothing to run.")
        _write_script([], dry_run)
        return

    print(f"Dispatching {len(commands)} run(s):")
    for workdir, cmd in commands.values():
        print(f"  [{workdir.name}] → {cmd}")

    _write_script(list(commands.values()), dry_run)


def _write_script(commands: list[tuple[Path, str]], dry_run: bool) -> None:
    lines = ["#!/bin/bash", "set -euo pipefail", ""]

    if not commands:
        lines.append("echo 'Nothing to run.'")
    else:
        for workdir, cmd in commands:
            lines.append(f'echo "==> [{workdir.name}] {cmd}"')
            lines.append(f"(cd {workdir} && {cmd})")
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
