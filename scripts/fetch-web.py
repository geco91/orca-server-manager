#!/usr/bin/env python3
"""Add only Orca's original browser files from the checksummed matching desktop package."""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

PREFIX = "opt/Orca/resources/app.asar.unpacked/out/renderer/"
MANIFEST = ".orca-web-client-files.json"


def web_files(raw):
    files = json.loads(raw)
    if (
        not isinstance(files, list)
        or not 1 <= len(files) <= 20000
        or "web-index.html" not in files
        or any(
            not isinstance(name, str)
            or not (
                name == "web-index.html"
                or name.startswith(("assets/", "cmaps/", "standard_fonts/", "wasm/"))
            )
            or "\\" in name
            or "\0" in name
            or name.endswith(".map")
            or any(part in {"", ".", ".."} for part in name.split("/"))
            for name in files
        )
    ):
        raise ValueError("Invalid official browser file manifest")
    return set(files)


@contextmanager
def package_tar(package):
    process = subprocess.Popen(
        ["dpkg-deb", "--fsys-tarfile", str(package)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as source:
            yield source
        process.stdout.close()
        if process.wait(timeout=30):
            raise ValueError("Could not read the verified desktop package")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def browser_manifest(source):
    raw = None
    for member in source:
        if member.name.removeprefix("./") != PREFIX + MANIFEST:
            continue
        if raw is not None or not member.isfile() or member.size > 256 * 1024:
            raise ValueError("Invalid official browser file manifest")
        raw = source.extractfile(member).read()
    if raw is None:
        raise ValueError("The matching desktop package has no original browser bundle")
    return raw, web_files(raw)


def extract_browser(source, raw, files, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("The browser destination must be empty")
    seen, total = set(), 0
    for member in source:
        path = member.name.removeprefix("./")
        if not path.startswith(PREFIX) or path[len(PREFIX) :] not in files:
            continue
        name = path[len(PREFIX) :]
        total += member.size
        if name in seen or not member.isfile() or member.size > 128 * 2**20 or total > 768 * 2**20:
            raise ValueError("Unexpected original browser asset")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.extractfile(member) as asset, target.open("xb") as output:
            while block := asset.read(1024 * 1024):
                output.write(block)
        target.chmod(0o644)
        seen.add(name)
    if seen != files:
        raise ValueError("The original browser bundle is incomplete")
    (destination / MANIFEST).write_bytes(raw)


def install(version, architecture, checksum, destination):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9][A-Za-z0-9.-]{0,60})?", version):
        raise ValueError("Invalid official browser version")
    if architecture not in {"x64", "arm64"} or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("A matching architecture and published desktop checksum are required")
    arch = "amd64" if architecture == "x64" else "arm64"
    url = f"https://github.com/stablyai/orca/releases/download/v{version}/orca-ide_{version}_{arch}.deb"
    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "desktop.deb"
        digest, size = hashlib.sha256(), 0
        with urlopen(url, timeout=60) as response, package.open("wb") as output:
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > 350 * 2**20:
                    raise ValueError("Official desktop package exceeds the size limit")
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != checksum:
            raise ValueError("Official desktop checksum mismatch")
        with package_tar(package) as source:
            raw, files = browser_manifest(source)
        with package_tar(package) as source:
            extract_browser(source, raw, files, destination)
    print(f"Verified original Orca browser bundle: {len(files)} files, version {version}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("architecture", choices=["x64", "arm64"])
    parser.add_argument("sha256")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    install(args.version, args.architecture, args.sha256, args.destination)
