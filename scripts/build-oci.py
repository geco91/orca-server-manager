#!/usr/bin/env python3
"""Build private OCI archives for the selected official Orca release."""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from manager.opencode_releases import DEFAULT_VERSION
from manager.opencode_releases import resolve_release as resolve_opencode
from manager.releases import resolve_release


def command(args):
    subprocess.run(args, cwd=ROOT, check=True)


def export(image, destination):
    docker_archive = destination.with_suffix(".docker.tar")
    command(["docker", "save", "-o", str(docker_archive), image])
    try:
        if shutil.which("skopeo"):
            command(
                ["skopeo", "copy", f"docker-archive:{docker_archive}", f"oci-archive:{destination}"]
            )
        else:
            # Standard OCI converter; no socket, host network or privileged container.
            command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network=none",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--mount",
                    f"type=bind,src={destination.parent},dst=/export",
                    "quay.io/skopeo/stable:latest",
                    "copy",
                    f"docker-archive:/export/{docker_archive.name}",
                    f"oci-archive:/export/{destination.name}",
                ]
            )
    finally:
        docker_archive.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manager", action="store_true")
    parser.add_argument("--opencode-version", default=DEFAULT_VERSION)
    parser.add_argument("--ca-file", type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    lock = (args.output / ".build.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("Another OCI build is already using this output directory.")
    release = resolve_release(args.version)
    opencode = resolve_opencode(args.opencode_version)
    common = ["docker", "build"]
    if args.ca_file:
        common += ["--secret", f"id=proxy_ca,src={args.ca_file.resolve()}"]
    version = release["version"]
    runtime = f"orca-server-manager/runtime:{version}"
    with_tools = f"orca-server-manager/runtime-tools:{version}"
    command(
        common
        + [
            "-f",
            "container/runtime.Dockerfile",
            "-t",
            runtime,
            "--build-arg",
            f"ORCA_VERSION={version}",
            "--build-arg",
            f"ORCA_SHA256={release['sha256']}",
            "--build-arg",
            f"ORCA_WEB_SHA256={release['web_sha256'] or ''}",
            ".",
        ]
    )
    command(
        common
        + [
            "-f",
            "container/providers.Dockerfile",
            "-t",
            with_tools,
            "--build-arg",
            f"RUNTIME_IMAGE={runtime}",
            "--build-arg",
            f"OPENCODE_VERSION={opencode['version']}",
            "--build-arg",
            f"OPENCODE_SHA256={opencode['sha256']}",
            ".",
        ]
    )
    archives = {}
    runtime_archive = args.output / f"orca-runtime-{version}.oci.tar"
    export(with_tools, runtime_archive)
    archives["runtime"] = runtime_archive
    if args.manager:
        manager = "orca-server-manager/manager-oci:0.2.0"
        command(common + ["-f", "container/manager-oci.Dockerfile", "-t", manager, "."])
        manager_archive = args.output / "orca-manager-0.2.0.oci.tar"
        export(manager, manager_archive)
        archives["manager"] = manager_archive
    record = {
        "schema": 1,
        "orca_version": version,
        "upstream_sha256": release["sha256"],
        "upstream_web_sha256": release["web_sha256"],
        "opencode_version": opencode["version"],
        "opencode_sha256": opencode["sha256"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "archives": {},
    }
    for key, path in archives.items():
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        record["archives"][key] = {"path": str(path), "sha256": digest}
    (args.output / f"manifest-{version}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
