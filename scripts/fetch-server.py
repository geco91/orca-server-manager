#!/usr/bin/env python3
"""Download and extract the exact official server asset, verifying its published SHA-256."""

import argparse
import hashlib
import re
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9][A-Za-z0-9.-]{0,60})?\Z")


def install(version, architecture, checksum, destination):
    if not VERSION.fullmatch(version) or architecture not in {"x64", "arm64"}:
        raise ValueError("Invalid official server target")
    if not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("An official SHA-256 digest is required")
    url = (
        f"https://github.com/stablyai/orca/releases/download/v{version}/"
        f"orca-server-linux-{architecture}.tar.gz"
    )
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("The extraction destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "server.tar.gz"
        digest = hashlib.sha256()
        size = 0
        with urlopen(url, timeout=60) as source, archive.open("wb") as output:
            while block := source.read(1024 * 1024):
                size += len(block)
                if size > 300 * 1024 * 1024:
                    raise ValueError("Server archive exceeds the download limit")
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != checksum:
            raise ValueError("Official server checksum mismatch")
        with tarfile.open(archive) as source:
            members = source.getmembers()
            roots = {Path(member.name).parts[0] for member in members}
            if len(roots) != 1:
                raise ValueError("Unexpected server archive layout")
            staging = Path(temporary) / "extract"
            source.extractall(staging, filter="data")
            root = staging / roots.pop()
            record = dict(
                line.split(" ", 1)
                for line in (root / "VERSION").read_text().splitlines()
                if " " in line
            )
            if record.get("orca") != version:
                raise ValueError("Server package VERSION differs from the requested release")
            marker = (root / "orcad/.runtime-node").read_text().strip()
            node = root / "runtimes" / f"node-{marker}" / "bin/node"
            if not re.fullmatch(r"[a-f0-9]{64}", marker) or not node.is_file():
                raise ValueError("The official runtime marker is invalid")
            with node.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != marker:
                    raise ValueError("The bundled Node executable differs from its runtime marker")
            for child in root.iterdir():
                child.rename(destination / child.name)
    if not (destination / "bin/orca-ide").is_file():
        raise ValueError("Official server CLI is missing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("architecture", choices=["x64", "arm64"])
    parser.add_argument("sha256")
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    install(arguments.version, arguments.architecture, arguments.sha256, arguments.destination)
    print("Official Orca server package and VERSION verified.")
