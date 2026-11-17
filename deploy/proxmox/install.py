#!/usr/bin/env python3
"""Print a native Proxmox OCI installation plan; change the host only with --apply."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from deploy.proxmox.notes import SetupNotesError, sync_setup_notes
from deploy.proxmox.worker import DeploymentError, Worker, load_config, run
from manager.control import atomic_document, read_document


def archive_check(path, checksum):
    if path.is_symlink() or not path.is_file():
        raise DeploymentError("Use a regular, private OCI archive.")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != checksum:
        raise DeploymentError("OCI archive checksum mismatch.")
    with tarfile.open(path) as archive:
        names = {member.name.removeprefix("./") for member in archive}
    if not {"oci-layout", "index.json"} <= names or not any(
        name.startswith("blobs/sha256/") for name in names
    ):
        raise DeploymentError("Expected an OCI archive, not a Docker archive or rootfs tar.")


def manager_create_command(cfg, archive):
    data = Path(cfg["data"])
    return [
        "pct",
        "create",
        str(cfg["manager_id"]),
        str(archive),
        "--hostname",
        "orca-manager-" + cfg["installation"],
        "--description",
        f"OSM:{cfg['installation']}:manager",
        "--unprivileged",
        "1",
        "--ostype",
        "unmanaged",
        "--rootfs",
        f"{cfg['storage']}:8",
        "--memory",
        "768",
        "--cores",
        "1",
        "--swap",
        "256",
        "--net0",
        f"name=eth0,bridge={cfg['bridge']},ip=dhcp,firewall=1",
        "--mp0",
        f"{data / 'manager'},mp=/data",
        "--mp1",
        f"{data / 'control'},mp=/control",
        "--onboot",
        "1",
        "--protection",
        "1",
    ]


def plan(cfg, archive_dir):
    worker = Worker(cfg, Path(cfg["base"]) / "deployment.json")
    runtime = archive_dir / f"orca-runtime-{cfg['version']}.oci.tar"
    manager = archive_dir / "orca-manager-0.2.0.oci.tar"
    return {
        "mode": "plan only; no host changes",
        "installation": cfg["installation"],
        "builder": {"id": cfg["builder_id"], "alias": cfg["builder_alias"], "create": False},
        "data_mount": cfg["data"],
        "commands": [
            worker.runtime_create_command(cfg["runtime_id"], runtime),
            manager_create_command(cfg, manager),
            ["pct", "set", str(cfg["runtime_id"]), "--onboot", "1"],
            ["pct", "start", str(cfg["runtime_id"])],
            ["pct", "start", str(cfg["manager_id"])],
        ],
        "notes": [
            "The OCI extractor reads a temporary copy as mapped root; private backups stay inaccessible.",
            "Requires a dedicated builder already assigned with the matching ownership marker.",
            "Requires an empty, dedicated, mounted data filesystem; never formats disks.",
            "Creates two unprivileged OCI containers; does not replace an existing guest.",
            "Installs a scoped root worker and timer; no web-facing host shell or Docker socket.",
            "Existing clients, provider logins and the OpenAI tunnel still use native setup.",
        ],
    }


def validate_resume(saved, cfg):
    fields = ["installation", "data", "runtime_id", "manager_id", "builder_id", "version"]
    if (
        any(saved.get(key) != cfg.get(key) for key in fields)
        or type(saved.get("generation")) is not int
        or saved["generation"] != 0
    ):
        raise DeploymentError("Only the same unfinished initial installation may be resumed.")
    if saved.get("previous") or saved.get("pending"):
        raise DeploymentError("Use deployment recovery for an existing version change.")


def apply(cfg, source_config, archive_dir, resume=False):
    if os.geteuid() != 0 or not Path("/etc/pve").is_dir():
        raise DeploymentError("Apply only as administrator on the assigned test Proxmox host.")
    # Full administrator-owned configuration validation happens before any change.
    cfg = load_config(source_config)
    base, data = Path(cfg["base"]), Path(cfg["data"])
    if base.exists() and not resume:
        raise DeploymentError("Deployment base already exists; refusing an overwrite.")
    if resume:
        saved = read_document(base / "deployment.json")
        validate_resume(saved, cfg)
    if not data.is_mount() or data.is_symlink():
        raise DeploymentError("The data directory must be a dedicated mounted filesystem.")
    if data.stat().st_uid != 0 or data.stat().st_mode & 0o022:
        raise DeploymentError(
            "The data mount must be administrator-owned and not writable by others."
        )
    for path in [
        ROOT,
        ROOT / "deploy/proxmox/worker.py",
        ROOT / "deploy/proxmox/notes.py",
        ROOT / "deploy/proxmox/pairing.py",
        ROOT / "manager/control.py",
        ROOT / "manager/pairing.py",
        ROOT / "manager/releases.py",
        ROOT / "manager/opencode_releases.py",
    ]:
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise DeploymentError("The host worker checkout must be administrator-owned.")
    for suffix in ["service", "timer"]:
        if (Path("/etc/systemd/system") / f"orca-manager-{cfg['installation']}.{suffix}").exists():
            raise DeploymentError("A worker unit with this installation name already exists.")
    if not resume and any(item.name != "lost+found" for item in data.iterdir()):
        raise DeploymentError("The dedicated data filesystem is not empty.")
    for vmid in [cfg["runtime_id"], cfg["manager_id"]]:
        existing = subprocess.run(
            ["pvesh", "get", "/cluster/nextid", "--vmid", str(vmid)],
            capture_output=True,
            check=False,
        )
        if existing.returncode:
            raise DeploymentError("An assigned container ID is already occupied.")
    worker = Worker(cfg, base / "deployment.json")
    worker.own_builder()
    # The selected build must come from exactly this clean source checkout.
    metadata = read_document(archive_dir / f"manifest-{cfg['version']}.json")
    commit = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()
    dirty = run(["git", "-C", str(ROOT), "status", "--porcelain"]).strip()
    if (
        dirty
        or commit != cfg["source_commit"]
        or metadata.get("source_dirty")
        or metadata.get("source_commit") != commit
        or metadata.get("orca_version") != cfg["version"]
        or metadata.get("opencode_version") != cfg["opencode_version"]
    ):
        raise DeploymentError(
            "Installer, configuration and OCI manifest must name the same clean source."
        )
    expected = {
        "runtime": archive_dir / f"orca-runtime-{cfg['version']}.oci.tar",
        "manager": archive_dir / "orca-manager-0.2.0.oci.tar",
    }
    for role, archive in expected.items():
        archive_check(archive, metadata["archives"][role]["sha256"])
    if shutil.disk_usage(data).free < 10 * 2**30:
        raise DeploymentError("At least 10 GiB must be free on the dedicated data filesystem.")
    base.mkdir(mode=0o700, parents=True, exist_ok=resume)
    # Keep the root-owned parent out of both guests. Only explicit children are mounted.
    for path, owner, mode in [
        (data / "control", 0, 0o755),
        (data / "control/requests", 101000, 0o700),
        (data / "control/results", 0, 0o755),
        (data / "private", 0, 0o700),
        (data / "private/runtime-data", 0, 0o700),
        (data / "private/runtime-data/home", 101000, 0o700),
        (data / "private/runtime-data/workspaces", 101000, 0o700),
        (data / "private/runtime-secrets", 101000, 0o700),
        (data / "private/runtime-tunnel", 0, 0o755),
        (data / "manager", 100000, 0o711),
    ]:
        if path.is_symlink():
            raise DeploymentError("An installation data directory cannot be a symlink.")
        path.mkdir(mode=mode, exist_ok=resume)
        os.chown(path, owner, owner)
        os.chmod(path, mode)
    cfg["generation"] = 0
    atomic_document(base / "deployment.json", cfg)
    # Persist the execution plan before importing; failures leave inspectable resources, never delete.
    atomic_document(base / "installation-plan.json", plan(cfg, archive_dir))
    with worker.import_archive(expected["runtime"]) as staged:
        run(worker.runtime_create_command(cfg["runtime_id"], staged), timeout=300)
    with worker.import_archive(expected["manager"]) as staged:
        run(manager_create_command(cfg, staged), timeout=300)
    run(["pct", "set", str(cfg["runtime_id"]), "--onboot", "1"])
    run(["pct", "start", str(cfg["runtime_id"])], timeout=90)
    run(["pct", "start", str(cfg["manager_id"])], timeout=90)
    try:
        sync_setup_notes(cfg)
    except SetupNotesError:
        print(
            "The host worker will retry publishing the setup code to manager Notes.",
            file=sys.stderr,
        )
    worker.publish_status()
    unit = Path("/etc/systemd/system")
    for suffix in ["service", "timer"]:
        content = (ROOT / f"deploy/proxmox/orca-manager-worker.{suffix}").read_text()
        content = (
            content.replace("@CHECKOUT@", str(ROOT))
            .replace("@CONFIG@", str(base / "deployment.json"))
            .replace("@DATA@", str(data))
        )
        destination = unit / f"orca-manager-{cfg['installation']}.{suffix}"
        if destination.exists():
            raise DeploymentError("A worker unit with this installation name already exists.")
        destination.write_text(content)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", f"orca-manager-{cfg['installation']}.timer"])
    print(
        "Installed. Open the manager's HTTPS address and copy the setup code from its Proxmox Summary → Notes."
    )
    print(
        "The host worker refreshes these Notes as the manager starts and removes the code after setup."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--resume", action="store_true", help="Resume before either initial CT exists."
    )
    args = parser.parse_args()
    cfg = read_document(args.config)
    if args.apply:
        apply(cfg, args.config, args.archives.resolve(), resume=args.resume)
    else:
        print(json.dumps(plan(cfg, args.archives.resolve()), indent=2))


if __name__ == "__main__":
    main()
