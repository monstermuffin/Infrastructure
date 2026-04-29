#!/usr/bin/env python3

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VM_ROOT = REPO_ROOT / "tf" / "proxmox_vms"
CONTROL_PLANES_FILE = REPO_ROOT / "ops" / "proxmox_control_planes.yml"


@dataclass(frozen=True)
class ControlPlane:
    id: str
    tfvars_file: str
    nodes: tuple[str, ...]
    hostname_suffixes: tuple[str, ...]


def _load_control_planes() -> list[ControlPlane]:
    raw = yaml.safe_load(CONTROL_PLANES_FILE.read_text()) or {}
    control_planes = []
    for item in raw.get("control_planes", []):
        control_planes.append(
            ControlPlane(
                id=item["id"],
                tfvars_file=item["tfvars_file"],
                nodes=tuple(item.get("nodes", [])),
                hostname_suffixes=tuple(item.get("hostname_suffixes", [])),
            )
        )
    return control_planes


def _git_changed_vm_files(base: str | None, head: str) -> list[Path]:
    if base:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head, "--", "tf/proxmox_vms"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        rel_paths = [Path(line) for line in result.stdout.splitlines() if line.strip()]
        return [REPO_ROOT / path for path in rel_paths if (REPO_ROOT / path).is_file()]

    return sorted(VM_ROOT.rglob("*.vm.yml"))


def _git_changed_vm_statuses(base: str, head: str) -> list[tuple[str, Path]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", base, head, "--", "tf/proxmox_vms"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    changes: list[tuple[str, Path]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path_text = parts[-1]
        changes.append((status, REPO_ROOT / path_text))
    return changes


def _load_vm_doc(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _load_vm_doc_at_ref(ref: str, path: Path) -> dict:
    rel_path = str(path.relative_to(REPO_ROOT))
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return yaml.safe_load(result.stdout) or {}


def _vm_name(path: Path, doc: dict) -> str:
    if doc.get("name"):
        return doc["name"]
    return path.name.removesuffix(".vm.yml")


def _match_control_plane(path: Path, doc: dict, control_planes: list[ControlPlane]) -> ControlPlane:
    hostname = doc.get("hostname")
    node_name = doc.get("node_name")

    if not hostname or not node_name:
        raise SystemExit(f"{path.relative_to(REPO_ROOT)} is missing required hostname/node_name fields")

    matches = [
        plane
        for plane in control_planes
        if node_name in plane.nodes and any(hostname.endswith(suffix) for suffix in plane.hostname_suffixes)
    ]

    if len(matches) != 1:
        raise SystemExit(
            f"{path.relative_to(REPO_ROOT)} does not map cleanly to one control plane "
            f"(hostname={hostname!r}, node_name={node_name!r})"
        )

    return matches[0]


def _changed_vm_info(base: str | None, head: str) -> list[tuple[Path, dict, ControlPlane]]:
    control_planes = _load_control_planes()
    info = []
    for path in _git_changed_vm_files(base, head):
        doc = _load_vm_doc(path)
        plane = _match_control_plane(path, doc, control_planes)
        info.append((path, doc, plane))
    return info


def _changed_vm_control_planes(base: str | None, head: str) -> set[str]:
    if not base:
        return _all_vm_control_planes()

    control_planes = _load_control_planes()
    plane_ids = set()
    for status, path in _git_changed_vm_statuses(base, head):
        if status.startswith("D"):
            doc = _load_vm_doc_at_ref(base, path)
        else:
            if not path.is_file():
                continue
            doc = _load_vm_doc(path)
        plane_ids.add(_match_control_plane(path, doc, control_planes).id)
    return plane_ids


def _all_vm_control_planes() -> set[str]:
    control_planes = _load_control_planes()
    plane_ids = set()
    for path in sorted(VM_ROOT.rglob("*.vm.yml")):
        doc = _load_vm_doc(path)
        plane_ids.add(_match_control_plane(path, doc, control_planes).id)
    return plane_ids


def _is_linux_vm(doc: dict) -> bool:
    """Return True for VMs that can be SSH-bootstrapped (i.e. not Windows)."""
    os_value = doc.get("operating_system", "")
    return not str(os_value).lower().startswith("win")


def command_changed_names(args: argparse.Namespace) -> int:
    names = sorted(
        {
            _vm_name(path, doc)
            for path, doc, _ in _changed_vm_info(args.base, args.head)
            if _is_linux_vm(doc)
        }
    )
    print(",".join(names))
    return 0


def command_resolve_tfvars(args: argparse.Namespace) -> int:
    changed_plane_ids = _changed_vm_control_planes(args.base, args.head)
    if changed_plane_ids:
        plane_ids = changed_plane_ids
        source = "changed VM definitions"
    else:
        all_plane_ids = _all_vm_control_planes()
        if len(all_plane_ids) > 1:
            raise SystemExit(
                "Terraform VM automation currently supports one control plane per run. "
                f"The repository currently contains VM definitions for multiple planes: {sorted(all_plane_ids)}."
            )
        plane_ids = all_plane_ids
        source = "all VM definitions"

    if not plane_ids:
        print("")
        return 0

    if len(plane_ids) != 1:
        raise SystemExit(
            "Terraform VM automation currently supports one control plane per run. "
            f"Found {sorted(plane_ids)} from {source}."
        )

    all_planes = _load_control_planes()
    plane_map = {plane.id: plane for plane in all_planes}
    selected_plane = plane_map[next(iter(plane_ids))]
    print(selected_plane.tfvars_file)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Proxmox VM dispatch metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    changed_names = subparsers.add_parser("changed-names", help="Print changed VM inventory names as a comma-separated list.")
    changed_names.add_argument("--base", default=None, help="Git base SHA. If omitted, all VM definitions are considered changed.")
    changed_names.add_argument("--head", default="HEAD", help="Git head SHA.")
    changed_names.set_defaults(func=command_changed_names)

    resolve_tfvars = subparsers.add_parser("resolve-tfvars", help="Resolve the tfvars file for the active VM control plane.")
    resolve_tfvars.add_argument("--base", default=None, help="Git base SHA used to detect changed VM definitions.")
    resolve_tfvars.add_argument("--head", default="HEAD", help="Git head SHA.")
    resolve_tfvars.set_defaults(func=command_resolve_tfvars)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
