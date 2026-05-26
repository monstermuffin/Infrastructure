#!/usr/bin/env python3

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CommandSpec:
    workdir: Path
    playbook: str
    limit: str | None = None
    tags: tuple[str, ...] = ()
    extra_vars: tuple[tuple[str, str], ...] = ()
    # Lower priority value runs first.
    priority: int = 10

    def merge_key(self) -> tuple[str, str, str | None, tuple[tuple[str, str], ...]]:
        return (str(self.workdir), self.playbook, self.limit, self.extra_vars)

    def merge(self, other: "CommandSpec") -> "CommandSpec":
        merged_tags = tuple(dict.fromkeys((*self.tags, *other.tags)))
        return CommandSpec(
            workdir=self.workdir,
            playbook=self.playbook,
            limit=self.limit,
            tags=merged_tags,
            extra_vars=self.extra_vars,
            priority=min(self.priority, other.priority),
        )

    def render(self) -> str:
        prefix = self.workdir.name + "/"
        cmd = f"ansible-playbook {self.playbook.removeprefix(prefix)}"
        if self.limit:
            cmd += f" --limit '{self.limit}'"
        if self.tags:
            cmd += f" --tags {','.join(self.tags)}"
        for key, val in self.extra_vars:
            cmd += f" -e {key}={val}"
        return cmd


def git_changed_files() -> list[tuple[str, str]]:
    last_successful = os.environ.get("LAST_SUCCESSFUL_SHA", "").strip()
    before = os.environ.get("BEFORE_SHA", "").strip()
    # Prefer the last successful deploy SHA to retry failed deploys
    if last_successful:
        base = last_successful
    elif before and before != "0" * 40:
        base = before
    else:
        base = "HEAD~1"
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", base, "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    changed = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        changed.append((parts[0], parts[-1]))
    return changed


def change_kind(status: str) -> str:
    return status[:1]


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
    parts = Path(path).parts
    # Expand {group} to the group name immediately under group_vars/ in the path.
    if "group_vars" in parts:
        idx = parts.index("group_vars")
        if idx + 1 < len(parts):
            val = val.replace("{group}", parts[idx + 1])
    # Expand {host} to the hostname immediately under host_vars/ in the path.
    if "host_vars" in parts:
        idx = parts.index("host_vars")
        if idx + 1 < len(parts):
            val = val.replace("{host}", parts[idx + 1])
    return val


def get_workdir(rule: dict, path: str) -> Path:
    # Explicit 'workdir' field in the rule takes precedence. Otherwise inferred from the top-level directory of the playbook or changed file path.
    if "workdir" in rule:
        return REPO_ROOT / rule["workdir"]
    ref = rule.get("playbook") or path
    top = ref.split("/")[0]
    candidate = REPO_ROOT / top
    return candidate if candidate.is_dir() else REPO_ROOT


def _make_command(
    playbook: str,
    *,
    path: str,
    limit: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    extra_vars: dict[str, str] | None = None,
    workdir: Path | None = None,
    priority: int = 10,
) -> CommandSpec:
    command_workdir = workdir or get_workdir({"playbook": playbook}, path)
    command_tags = tuple(tags or ())
    expanded_extra_vars = tuple(
        (key, _expand_template(val, path))
        for key, val in (extra_vars or {}).items()
    )
    return CommandSpec(
        workdir=command_workdir,
        playbook=playbook,
        limit=limit,
        tags=command_tags,
        extra_vars=expanded_extra_vars,
        priority=priority,
    )


def build_command(rule: dict, path: str, status: str) -> list[CommandSpec]:
    workdir = get_workdir(rule, path)
    action = rule.get("action")
    priority = int(rule.get("priority", 10))

    if action == "playbook_self":
        return [_make_command(path, path=path, workdir=workdir, priority=priority)]

    if action == "noop":
        return []

    if action == "host_linux":
        linux_playbook = "ansible/playbooks/linux/manage.yml"
        limit = extract_limit(path, {})
        return [_make_command(linux_playbook, path=path, limit=limit, priority=priority)]

    if action == "host_self":
        return _build_host_self_commands(path, status)

    playbook = rule.get("playbook")
    if not playbook:
        return []

    limit = extract_limit(path, rule)
    return [
        _make_command(
            playbook,
            path=path,
            limit=limit,
            extra_vars=rule.get("extra_vars"),
            workdir=workdir,
            priority=priority,
        )
    ]


def _dispatch_entries(dispatch_config: dict | list | None, status: str) -> list[dict]:
    if not dispatch_config:
        return []
    selected = dispatch_config
    if isinstance(dispatch_config, dict) and any(
        key in dispatch_config for key in ("on_add", "on_change", "on_delete")
    ):
        event_key = {
            "A": "on_add",
            "D": "on_delete",
        }.get(change_kind(status), "on_change")
        selected = dispatch_config.get(event_key, [])
    if isinstance(selected, dict):
        selected = [selected]
    return [entry for entry in selected if isinstance(entry, dict) and entry.get("playbook")]


def _build_dispatch_commands(path: str, limit: str | None, dispatch_config: dict | list, status: str) -> list[CommandSpec]:
    commands = []
    for entry in _dispatch_entries(dispatch_config, status):
        commands.append(
            _make_command(
                entry["playbook"],
                path=path,
                limit=limit,
                tags=entry.get("tags"),
                extra_vars=entry.get("extra_vars"),
                priority=int(entry.get("priority", 10)),
            )
        )
    return commands


def _build_host_self_commands(path: str, status: str) -> list[CommandSpec]:
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
        commands.append(_make_command(custom_playbook, path=path, limit=limit))

    if "podman_apps" in host_vars:
        if change_kind(status) == "A":
            commands.append(
                _make_command(
                    "ansible/playbooks/lxc/update_podman_packages.yml",
                    path=path,
                    limit=limit,
                )
            )
        # Pass target as extra_var so the play matches the host directly,
        # regardless of tag_podman_app
        commands.append(
            _make_command(
                "ansible/playbooks/lxc/deploy_podman_app.yml",
                path=path,
                limit=limit,
                tags=["setup", "image", "deploy"],
                extra_vars={"target": limit} if limit else None,
            )
        )

    if host_vars.get("dispatch"):
        commands.extend(_build_dispatch_commands(path, limit, host_vars["dispatch"], status))

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
    commands: dict[tuple[str, str, str | None, tuple[tuple[str, str], ...]], CommandSpec] = {}
    notices: list[str] = []

    for status, path in changed:
        for rule in rules:
            if Path(path).full_match(rule["pattern"]):
                if rule.get("action") == "manual_notice":
                    note = rule.get("note", f"Manual action required for {path}")
                    notices.append(_expand_template(note, path))
                    break
                for command in build_command(rule, path, status):
                    key = command.merge_key()
                    if key in commands:
                        commands[key] = commands[key].merge(command)
                    else:
                        commands[key] = command
                break  # first matching rule wins

    if not commands:
        print("Changed files matched no dispatch rules — nothing to run.")
        if notices:
            print("Manual follow-up required:")
            for note in dict.fromkeys(notices):
                print(f"  - {note}")
        _write_script([], dry_run)
        return

    print(f"Dispatching {len(commands)} run(s):")
    for command in commands.values():
        print(f"  [{command.workdir.name}] → {command.render()}")

    if notices:
        print("Manual follow-up required:")
        for note in dict.fromkeys(notices):
            print(f"  - {note}")

    _write_script(list(commands.values()), dry_run)


def _write_script(commands: list[CommandSpec], dry_run: bool) -> None:
    lines = [
        "#!/bin/bash",
        "set -uo pipefail",
        "",
        "failures=0",
        "declare -a failed_commands=()",
        "",
    ]

    sorted_commands = sorted(commands, key=lambda c: (c.priority, str(c.workdir), c.playbook))

    if not sorted_commands:
        lines.append("echo 'Nothing to run.'")
    else:
        for command in sorted_commands:
            cmd = command.render()
            lines.append(f'echo "==> [{command.workdir.name}] {cmd}"')
            lines.append(f"if ! (cd {shlex.quote(str(command.workdir))} && {cmd}); then")
            lines.append("  ((failures+=1))")
            lines.append(f"  failed_commands+=({shlex.quote(f'[{command.workdir.name}] {cmd}')})")
            lines.append("fi")
            lines.append("")

    lines.extend([
        "if (( failures > 0 )); then",
        '  echo ""',
        '  echo "Dispatch completed with ${failures} failure(s):"',
        '  for failed_command in "${failed_commands[@]}"; do',
        '    echo "  - ${failed_command}"',
        "  done",
        "  exit 1",
        "fi",
    ])

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
