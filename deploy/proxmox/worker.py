#!/usr/bin/env python3
"""Scoped Proxmox OCI executor. No web listener, shell endpoint or Docker socket."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from deploy.proxmox import forge
from deploy.proxmox.notes import SetupNotesError, sync_setup_notes
from deploy.proxmox.pairing import prune_pairings, publish_pairing, read_manager_origin
from manager.control import JOB_ID, ControlError, atomic_document, read_document, utc_now
from manager.forge import ACTIONS as FORGE_ACTIONS
from manager.opencode_releases import LEGACY_VERSION as LEGACY_OPENCODE_VERSION
from manager.opencode_releases import require_upgrade as require_opencode_upgrade
from manager.opencode_releases import resolve_release as resolve_opencode
from manager.opencode_releases import validate_version as validate_opencode
from manager.pairing import PAIRING_TTL, PairingError, native_pairing
from manager.releases import require_upgrade, resolve_release, validate_version


class DeploymentError(ValueError):
    pass


def run(args, *, timeout=120):
    # PVE creates /var/lib/lxc/<id>/rootfs with inherited directory modes. Its
    # mapped OCI extractor needs the standard traversal rights during creation.
    native_create = args[:2] == ["pct", "create"]
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        umask=0o022 if native_create else -1,
    )
    if result.returncode:
        # Raw command output stays out of the UI; native tools can include private paths.
        raise DeploymentError(f"{Path(args[0]).name} failed with exit code {result.returncode}.")
    return result.stdout


def load_config(path):
    info = path.stat(follow_symlinks=False)
    if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise DeploymentError(
            "The worker configuration must be root-owned and not writable by others."
        )
    cfg = read_document(path)
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", cfg.get("installation", "")):
        raise DeploymentError("Invalid installation identity.")
    for field in ["runtime_id", "manager_id", "builder_id"]:
        if type(cfg.get(field)) is not int or cfg[field] < 100:
            raise DeploymentError("A dedicated runtime, manager and builder must be assigned.")
    if len({cfg["runtime_id"], cfg["manager_id"], cfg["builder_id"]}) != 3:
        raise DeploymentError("Runtime, manager and builder identities must differ.")
    for field in ["base", "data", "builder_checkout", "builder_output"]:
        value = cfg.get(field, "")
        if not isinstance(value, str) or not re.fullmatch(r"/[a-zA-Z0-9_./-]+", value):
            raise DeploymentError("Deployment paths must be configured explicitly.")
        if ".." in Path(value).parts or Path(value) == Path("/"):
            raise DeploymentError("Deployment paths must be scoped directories.")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", cfg.get("builder_alias", "")):
        raise DeploymentError("Invalid existing builder SSH alias.")
    for field in ["storage", "bridge"]:
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", cfg.get(field, "")):
            raise DeploymentError("Choose an existing storage and bridge explicitly.")
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", cfg.get("runtime_mac", "")):
        raise DeploymentError("A persistent runtime MAC address is required.")
    if not re.fullmatch(r"[a-f0-9]{40}", cfg.get("source_commit", "")):
        raise DeploymentError("Pin the manager source commit.")
    validate_version(cfg.get("version"))
    validate_opencode(cfg.setdefault("opencode_version", LEGACY_OPENCODE_VERSION))
    ssh_config = Path(cfg.get("ssh_config", ""))
    if not ssh_config.is_absolute():
        raise DeploymentError("Use an explicit, private SSH configuration.")
    ssh_info = ssh_config.stat(follow_symlinks=False)
    if ssh_config.is_symlink() or ssh_info.st_uid != 0 or ssh_info.st_mode & 0o022:
        raise DeploymentError("The builder SSH configuration must be administrator-owned.")
    return cfg


def validate_request(document, name):
    expected = {"schema", "id", "action", "version", "restore_data", "created_at", "generation"}
    if set(document) != expected or document.get("schema") != 1:
        raise DeploymentError("Unsupported request schema.")
    if document.get("id") != name or not JOB_ID.fullmatch(name):
        raise DeploymentError("Invalid operation identity.")
    if document.get("action") not in {
        *FORGE_ACTIONS,
        "refresh",
        "update",
        "update_opencode",
        "rollback",
        "pair_web",
    }:
        raise DeploymentError("Unsupported operation.")
    if document["action"] == "update_opencode":
        validate_opencode(document.get("version"))
    elif document["action"] == "update":
        validate_version(document.get("version"))
    elif document.get("version") is not None:
        raise DeploymentError("Only update requests may specify a version.")
    if type(document.get("restore_data")) is not bool:
        raise DeploymentError("Choose the rollback data policy explicitly.")
    if document["action"] != "rollback" and document["restore_data"]:
        raise DeploymentError("Data restoration requires a rollback.")
    if type(document.get("generation")) is not int:
        raise DeploymentError("Missing deployment generation.")
    return document


class Worker:
    def __init__(self, cfg, config_path, command=run):
        self.cfg, self.config_path, self.run = cfg, config_path, command
        self.cfg.setdefault("opencode_version", LEGACY_OPENCODE_VERSION)
        self.base, self.data = Path(cfg["base"]), Path(cfg["data"])
        self.control, self.private = self.data / "control", self.data / "private"
        self.requests, self.results = self.control / "requests", self.control / "results"
        self.inflight = self.private / "inflight"
        self.runtime_data = self.private / "runtime-data"
        self.home, self.workspaces = self.runtime_data / "home", self.runtime_data / "workspaces"
        self.cache = self.private / "images"

    def save(self):
        atomic_document(self.config_path, self.cfg)

    def result(self, job, state, message, phase="", detail=""):
        value = {
            "id": job["id"],
            "state": state,
            "message": message,
            "phase": phase,
            "detail": detail,
            "updated_at": utc_now(),
        }
        atomic_document(self.results / f"{job['id']}.json", value, mode=0o644)

    def own_container(self, vmid, role="runtime"):
        data = self.run(["pct", "config", str(vmid)])
        expected = f"OSM:{self.cfg['installation']}:{role}"
        if not self.has_marker(data, expected):
            raise DeploymentError("The container does not belong to this scoped deployment.")

    @staticmethod
    def has_marker(config, expected):
        # PVE CLI config output URL-encodes descriptions, including ':' and newlines.
        value = next(
            (
                line.removeprefix("description: ")
                for line in config.splitlines()
                if line.startswith("description: ")
            ),
            "",
        )
        return expected in unquote(value).splitlines()

    def own_builder(self):
        data = self.run(["qm", "config", str(self.cfg["builder_id"])])
        expected = f"OSM:{self.cfg['installation']}:builder"
        if not self.has_marker(data, expected):
            raise DeploymentError("The VM is not the assigned builder for this deployment.")

    def running(self, vmid):
        self.own_container(vmid)
        return "status: running" in self.run(["pct", "status", str(vmid)])

    def probe(self):
        vmid = self.cfg["runtime_id"]
        self.own_container(vmid)
        if not self.running(vmid):
            return {
                "runtime": {
                    "reachable": False,
                    "version": self.cfg["version"],
                    "opencode_version": self.cfg["opencode_version"],
                    "active_terminals": 0,
                },
                "integrations": {},
            }
        raw = self.run(
            [
                "pct",
                "exec",
                str(vmid),
                "--",
                "/usr/sbin/runuser",
                "-u",
                "orca",
                "--",
                "/opt/orca/node-bin/node",
                "/opt/osm/runtime-status.cjs",
            ],
            timeout=75,
        )
        if len(raw) > 128 * 1024:
            raise DeploymentError("Runtime observation exceeds its size limit.")
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("schema") != 1:
            raise DeploymentError("Unexpected runtime observation.")
        runtime = result.get("runtime", {})
        if not isinstance(runtime, dict):
            raise DeploymentError("Unexpected runtime observation.")
        if "opencode_version" in runtime:
            try:
                validate_opencode(runtime["opencode_version"])
            except ValueError:
                runtime["opencode_version"] = None
        else:
            # Older observers only included Orca. Their image shipped the v1 executable.
            try:
                version = (
                    self.run(
                        [
                            "pct",
                            "exec",
                            str(vmid),
                            "--",
                            "/usr/sbin/runuser",
                            "-u",
                            "orca",
                            "--",
                            "/usr/bin/env",
                            "--chdir=/workspaces",
                            "/usr/local/bin/opencode",
                            "--version",
                        ],
                        timeout=10,
                    )
                    .strip()
                    .removeprefix("v")
                )
                runtime["opencode_version"] = validate_opencode(version)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                runtime["opencode_version"] = None
        return result

    def publish_status(self):
        try:
            observed = self.probe()
        except (DeploymentError, OSError, ValueError, subprocess.TimeoutExpired):
            observed = {
                "runtime": {
                    "reachable": False,
                    "version": self.cfg["version"],
                    "active_terminals": None,
                },
                "integrations": {},
            }
        previous = self.cfg.get("previous") or {}
        value = {
            "schema": 1,
            "observed_at": utc_now(),
            "runtime": observed.get("runtime", {}),
            "integrations": observed.get("integrations", {}),
            "deployment": {
                "runtime_id": self.cfg["runtime_id"],
                "version": self.cfg["version"],
                "opencode_version": self.cfg["opencode_version"],
                "generation": self.cfg.get("generation", 0),
                "previous_version": previous.get("version"),
                "previous_opencode_version": previous.get("opencode_version"),
                "backup_at": previous.get("backup_at"),
            },
        }
        atomic_document(self.control / "status.json", value, mode=0o644)
        return value

    def idle_runtime(self):
        observed = self.probe()["runtime"]
        count = observed.get("active_terminals")
        if count is None:
            raise DeploymentError(
                "Terminal activity is not observable. Inspect Orca before replacing it."
            )
        if type(count) is not int or count != 0:
            raise DeploymentError(
                "Close running terminal sessions in Orca before changing the container."
            )
        return observed

    def build(self, version, opencode_version):
        release = resolve_release(version)
        opencode = resolve_opencode(opencode_version)
        self.own_builder()
        alias = self.cfg["builder_alias"]
        checkout, output = self.cfg["builder_checkout"], self.cfg["builder_output"]
        if "status: running" not in self.run(["qm", "status", str(self.cfg["builder_id"])]):
            self.run(["qm", "start", str(self.cfg["builder_id"])], timeout=90)
        ssh = [
            "ssh",
            "-F",
            self.cfg["ssh_config"],
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=10",
            alias,
        ]
        deadline = time.monotonic() + 90
        while True:
            try:
                self.run(ssh + ["/usr/bin/true"], timeout=15)
                break
            except (DeploymentError, subprocess.TimeoutExpired):
                if time.monotonic() >= deadline:
                    raise DeploymentError(
                        "The assigned builder did not become reachable."
                    ) from None
                time.sleep(3)
        self.run(
            ssh
            + [
                shlex.join(
                    [
                        "python3",
                        checkout + "/scripts/build-oci.py",
                        "--version",
                        version,
                        "--opencode-version",
                        opencode_version,
                        "--output",
                        output,
                    ]
                )
            ],
            timeout=1800,
        )
        self.cache.mkdir(mode=0o700, exist_ok=True)
        manifest = self.cache / f"manifest-{version}.json"
        source_manifest = output + f"/manifest-{version}.json"
        self.run(
            [
                "scp",
                "-F",
                self.cfg["ssh_config"],
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                f"{alias}:{source_manifest}",
                str(manifest),
            ]
        )
        metadata = read_document(manifest)
        if (
            metadata.get("source_dirty")
            or metadata.get("source_commit") != self.cfg["source_commit"]
        ):
            raise DeploymentError("The builder source differs from the configured implementation.")
        if (
            metadata.get("orca_version") != version
            or metadata.get("upstream_sha256") != release["sha256"]
            or metadata.get("upstream_web_sha256") != release["web_sha256"]
        ):
            raise DeploymentError("The built version differs from the selected official release.")
        if (
            metadata.get("opencode_version") != opencode_version
            or metadata.get("opencode_sha256") != opencode["sha256"]
        ):
            raise DeploymentError("The built OpenCode package differs from the selected release.")
        archive = self.cache / f"orca-runtime-{version}.oci.tar"
        source_archive = output + f"/orca-runtime-{version}.oci.tar"
        self.run(
            [
                "scp",
                "-F",
                self.cfg["ssh_config"],
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                f"{alias}:{source_archive}",
                str(archive),
            ],
            timeout=300,
        )
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != metadata["archives"]["runtime"]["sha256"]:
            raise DeploymentError("OCI archive transfer checksum mismatch.")
        return archive

    def runtime_create_command(self, vmid, archive):
        return [
            "pct",
            "create",
            str(vmid),
            str(archive),
            "--hostname",
            "orca-" + self.cfg["installation"],
            "--description",
            f"OSM:{self.cfg['installation']}:runtime",
            "--unprivileged",
            "1",
            "--ostype",
            "unmanaged",
            "--rootfs",
            f"{self.cfg['storage']}:8",
            "--memory",
            str(self.cfg.get("runtime_memory", 4096)),
            "--cores",
            str(self.cfg.get("runtime_cores", 2)),
            "--swap",
            "256",
            "--net0",
            f"name=eth0,bridge={self.cfg['bridge']},ip=dhcp,hwaddr={self.cfg['runtime_mac']},firewall=1",
            "--mp0",
            f"{self.home},mp=/home/orca",
            "--mp1",
            f"{self.workspaces},mp=/workspaces",
            "--mp2",
            f"{self.private / 'runtime-secrets'},mp=/run/secrets,ro=1",
            "--mp3",
            f"{self.private / 'runtime-tunnel'},mp=/opt/tunnel,ro=1",
            "--onboot",
            "0",
            "--protection",
            "1",
        ]

    def candidate(self, archive):
        vmid = int(self.run(["pvesh", "get", "/cluster/nextid"]).strip())
        # Creation is atomic in PVE; no force/overwrite or unrelated container deletion.
        with self.import_archive(archive) as staged:
            self.run(self.runtime_create_command(vmid, staged), timeout=300)
        self.own_container(vmid)
        return vmid

    @contextmanager
    def import_archive(self, archive):
        # PVE's OCI extractor runs as mapped root (host UID 100000). Give it
        # read-only access to a temporary image, never to the private backup tree.
        directory = self.data / "imports"
        directory.mkdir(mode=0o711, exist_ok=True)
        info = directory.stat(follow_symlinks=False)
        if directory.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise DeploymentError("The OCI import directory is not administrator-controlled.")
        # The worker uses umask 0077; mkdir alone would remove the required traverse bits.
        os.chmod(directory, 0o711)
        stage = directory / (secrets.token_hex(16) + ".tar")
        try:
            fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as target, Path(archive).open("rb") as source:
                shutil.copyfileobj(source, target, length=4 * 1024 * 1024)
            os.chown(stage, 100000, 100000)
            os.chmod(stage, 0o400)
            yield stage
        finally:
            stage.unlink(missing_ok=True)

    def stop(self, vmid):
        if self.running(vmid):
            self.run(["pct", "shutdown", str(vmid), "--timeout", "45"], timeout=60)
        if self.running(vmid):
            raise DeploymentError("Runtime shutdown did not complete; no data was replaced.")

    def backup(self, job):
        backup = self.private / "backups" / job["id"]
        backup.mkdir(mode=0o700, parents=True)
        self.run(
            ["cp", "-a", "--reflink=auto", str(self.runtime_data), str(backup / "data")],
            timeout=600,
        )
        return backup

    def repair_interrupted_data_swap(self):
        pending = self.cfg.get("pending") or {}
        if pending.get("phase") != "swapping-data":
            return
        job_id = pending.get("job", "")
        if not JOB_ID.fullmatch(job_id):
            raise DeploymentError("Invalid interrupted data operation.")
        staged = self.private / "restore" / job_id / "data"
        retired = self.private / "retired-data" / job_id / "data"
        if not self.runtime_data.exists():
            if staged.is_dir() and not staged.is_symlink():
                staged.rename(self.runtime_data)
            elif retired.is_dir() and not retired.is_symlink():
                retired.rename(self.runtime_data)
            else:
                raise DeploymentError("Interrupted data swap needs administrator recovery.")
        self.cfg["pending"]["phase"] = "rollback-interrupted"
        self.save()

    def wait_start(self, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            observed = self.publish_status()
            runtime = observed["runtime"]
            if (
                runtime.get("reachable") is True
                and runtime.get("version") == self.cfg["version"]
                and runtime.get("opencode_version") == self.cfg["opencode_version"]
            ):
                return True
            time.sleep(3)
        return False

    def update(self, job):
        if self.cfg.get("pending"):
            raise DeploymentError("An interrupted change needs recovery before another update.")
        provider_update = job["action"] == "update_opencode"
        version = self.cfg["version"] if provider_update else job["version"]
        if not provider_update:
            require_upgrade(version, self.cfg["version"])
        observed = self.idle_runtime()
        old_opencode = observed.get("opencode_version")
        validate_opencode(old_opencode)
        opencode_version = job["version"] if provider_update else old_opencode
        if provider_update:
            require_opencode_upgrade(opencode_version, old_opencode)
        self.result(job, "running", "Preparing the selected official release.", "Prepare OCI image")
        archive = self.build(version, opencode_version)
        self.result(job, "running", "Creating the replacement container.", "Prepare OCI container")
        candidate = self.candidate(archive)
        old_id, old_version = self.cfg["runtime_id"], self.cfg["version"]
        self.cfg["pending"] = {"job": job["id"], "candidate": candidate, "phase": "prepared"}
        self.save()
        current = self.idle_runtime()
        if current.get("opencode_version") != old_opencode:
            raise DeploymentError(
                "OpenCode changed during image preparation. Refresh and choose again."
            )
        self.result(
            job, "running", "Stopping Orca and preserving its data.", "Save consistent return point"
        )
        self.stop(old_id)
        try:
            backup = self.backup(job)
        except (DeploymentError, OSError, subprocess.TimeoutExpired):
            self.run(["pct", "start", str(old_id)], timeout=90)
            raise
        previous = {
            "id": old_id,
            "version": old_version,
            "opencode_version": old_opencode,
            "backup": str(backup),
            "backup_at": utc_now(),
        }
        if self.cfg.get("previous"):
            self.cfg.setdefault("retained_containers", []).append(self.cfg["previous"]["id"])
        self.run(["pct", "set", str(old_id), "--onboot", "0"])
        self.cfg.update(
            previous=previous,
            runtime_id=candidate,
            version=version,
            opencode_version=opencode_version,
            generation=self.cfg.get("generation", 0) + 1,
            pending={"job": job["id"], "candidate": candidate, "phase": "starting"},
        )
        self.save()
        self.result(job, "running", "Starting the selected version.", "Start Orca")
        self.run(["pct", "set", str(candidate), "--onboot", "1"])
        self.run(["pct", "start", str(candidate)], timeout=90)
        started = self.wait_start()
        self.cfg.pop("pending", None)
        self.save()
        self.result(
            job,
            "completed" if started else "failed",
            "The selected version is running. Try it yourself in Orca."
            if started
            else "The selected software could not be confirmed. The previous container and its data backup remain available.",
            "Runtime state observed",
        )

    def rollback(self, job):
        previous = self.cfg.get("previous")
        if not previous:
            raise DeploymentError("There is no saved previous version for this deployment.")
        self.own_container(previous["id"])
        if self.probe()["runtime"].get("reachable") is True:
            self.idle_runtime()
        self.result(job, "running", "Stopping the current runtime.", "Prepare rollback")
        current_id = self.cfg["runtime_id"]
        self.stop(current_id)
        self.run(["pct", "set", str(current_id), "--onboot", "0"])
        if job["restore_data"]:
            backup = Path(previous["backup"])
            expected = self.private / "backups"
            if backup.parent != expected or not JOB_ID.fullmatch(backup.name):
                raise DeploymentError("The saved data path is not owned by this deployment.")
            if backup.is_symlink() or not all(
                (backup / "data" / name).is_dir() for name in ["home", "workspaces"]
            ):
                raise DeploymentError("The consistent data backup is unavailable.")
            self.result(
                job,
                "running",
                "Restoring the saved data; newer changes are being discarded.",
                "Restore saved data",
            )
            retired = self.private / "retired-data" / job["id"]
            retired.mkdir(mode=0o700, parents=True)
            staged = self.private / "restore" / job["id"]
            staged.mkdir(mode=0o700, parents=True)
            self.run(
                ["cp", "-a", "--reflink=auto", str(backup / "data"), str(staged / "data")],
                timeout=600,
            )
            self.cfg["pending"] = {"job": job["id"], "phase": "swapping-data"}
            self.save()
            self.runtime_data.rename(retired / "data")
            (staged / "data").rename(self.runtime_data)
        self.cfg.update(
            runtime_id=previous["id"],
            version=previous["version"],
            opencode_version=previous.get("opencode_version", LEGACY_OPENCODE_VERSION),
            generation=self.cfg.get("generation", 0) + 1,
        )
        self.cfg.setdefault("retained_containers", []).append(current_id)
        self.cfg.pop("previous", None)
        self.cfg.pop("pending", None)
        self.save()
        self.result(job, "running", "Starting the previous version.", "Start previous Orca")
        self.run(["pct", "set", str(self.cfg["runtime_id"]), "--onboot", "1"])
        self.run(["pct", "start", str(self.cfg["runtime_id"])], timeout=90)
        started = self.wait_start()
        self.result(
            job,
            "completed" if started else "failed",
            (
                "The previous software and saved data were restored."
                if job["restore_data"]
                else "The previous software was restored; newer data was retained."
            )
            if started
            else "The previous runtime did not become reachable. Inspect its native logs.",
        )

    def execute(self, job):
        if job["action"] != "refresh" and job["generation"] != self.cfg.get("generation", 0):
            self.result(
                job,
                "blocked",
                "The deployment changed after this request. Read its current state and choose again.",
            )
            return
        self.result(job, "running", "The scoped deployment worker accepted the request.")
        try:
            if job["action"] == "refresh":
                self.publish_status()
                self.result(
                    job,
                    "completed",
                    "The native runtime status was read. No account or device was connected.",
                )
            elif job["action"] in FORGE_ACTIONS:
                forge.start(self, job)
            elif job["action"] == "pair_web":
                self.pair_web(job)
            elif job["action"] in {"update", "update_opencode"}:
                self.update(job)
            else:
                self.rollback(job)
        except (DeploymentError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            pending = self.cfg.get("pending") or {}
            if pending.get("phase") == "prepared":
                self.cfg.setdefault("retained_containers", []).append(pending["candidate"])
                self.cfg.pop("pending", None)
                self.save()
            self.result(job, "failed", str(error))
        finally:
            self.publish_status()

    def tick(self):
        try:
            prune_pairings(self.control)
        except PairingError as error:
            print(str(error), file=sys.stderr)
        try:
            sync_setup_notes(self.cfg)
        except SetupNotesError as error:
            # Notes failures do not block runtime recovery. Error text contains no secret.
            print(str(error), file=sys.stderr)
        self.inflight.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.repair_interrupted_data_swap()
        # Do not silently replay requests that may already have changed a container.
        for path in self.inflight.glob("*.json"):
            try:
                job = validate_request(read_document(path), path.stem)
                prior = read_document(self.results / path.name)
                if prior.get("state") in {"queued", "running"}:
                    self.result(
                        job,
                        "interrupted",
                        "The previous worker stopped. Inspect the current state and use the saved rollback if needed.",
                    )
            except (ControlError, DeploymentError, ValueError):
                pass
            path.rename(path.with_suffix(".interrupted"))
        self.publish_status()
        forge.poll(self)
        for source in sorted(self.requests.glob("*.json")):
            if not JOB_ID.fullmatch(source.stem) or source.is_symlink():
                continue
            destination = self.inflight / source.name
            source.rename(destination)
            try:
                job = validate_request(read_document(destination), destination.stem)
                self.execute(job)
            except (ControlError, DeploymentError, ValueError):
                # Invalid requests never reach native commands; keep the original for inspection.
                pass
            destination.rename(destination.with_suffix(".done"))

    def pair_web(self, job):
        try:
            created = datetime.fromisoformat(job["created_at"])
        except (ValueError, TypeError):
            raise DeploymentError("Invalid pairing request timestamp.") from None
        if created.tzinfo is None or not -5 <= time.time() - created.timestamp() <= PAIRING_TTL:
            raise DeploymentError(
                "This pairing request expired. Open the WebUI again to prepare another link."
            )
        self.own_container(self.cfg["manager_id"], role="manager")
        observed = self.probe().get("runtime", {})
        if observed.get("reachable") is not True or not observed.get("web_url"):
            raise DeploymentError(
                "The Orca WebUI is not reachable yet. Refresh the status and try again."
            )
        origin = read_manager_origin(self.data)
        self.result(job, "running", "Requesting this server's native browser pairing link.")
        raw = self.run(
            [
                "pct",
                "exec",
                str(self.cfg["runtime_id"]),
                "--",
                "/usr/sbin/runuser",
                "-u",
                "orca",
                "--",
                "/usr/local/bin/orca",
                "pair",
                "--address",
                origin.replace("https://", "wss://", 1) + "/orca",
                "--json",
            ],
            timeout=30,
        )
        payload = native_pairing(raw, origin, job["id"], self.cfg["generation"])
        publish_pairing(self.control, payload)
        self.result(
            job,
            "completed",
            "The private native pairing link is ready. Open the WebUI to connect this browser.",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0 or not Path("/etc/pve").is_dir():
        parser.error("Run only as the administrator on the assigned Proxmox host.")
    cfg = load_config(args.config)
    if not Path(cfg["data"]).is_mount():
        parser.error("The dedicated data filesystem is not mounted; no operation was started.")
    lock_path = Path(cfg["base"]) / "worker.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        Worker(cfg, args.config).tick()


if __name__ == "__main__":
    main()
