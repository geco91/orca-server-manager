#!/usr/bin/env python3
"""Assemble upstream's verified Linux orcad template; never build or alter Orca code."""

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ORCA_VERSION = "1.4.239"
# Native artifact ABI version, distinct from the desktop product version.
# stablyai/orca src/shared/orcad-artifacts.ts (ORCAD_VERSION).
ORCAD_ARTIFACT_VERSION = "0.1.0"
DEB_SHA512 = (
    "VakWMtdki1TPXTdUhLHzco0kY7k7cgLIT5AzUQ49HivqTZaLbbAljSf0Jwu1JyCKAo+861cX5O/dBTWMTTpBYw=="
)
NODE_SHA256 = "6c172a9ab6718f7b801fb5a7bd486af2ee5e32758086a04b84fcce2aa77095e6"
TARGET = "linux-x64-glibc"


def digest(path, algorithm="sha256"):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).digest()


def safe_path(root, name):
    result = (root / name).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Unsafe upstream artifact path")
    return result


def materialize(deb, node_archive, destination):
    if base64.b64encode(digest(deb, "sha512")).decode() != DEB_SHA512:
        raise ValueError("Orca release SHA-512 mismatch")
    if digest(node_archive).hex() != NODE_SHA256:
        raise ValueError("Node archive SHA-256 mismatch")
    extracted = destination / "extracted"
    extracted.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "-x", str(deb), str(extracted)], check=True)
    resources = extracted / "opt/Orca/resources"
    template = resources / "orcad-template"
    manifest = json.loads((template / "orcad-template.json").read_text())
    if manifest["schemaVersion"] != 4:
        raise ValueError("Unreviewed template schema")
    slot = destination / "server"
    slot.mkdir()
    for name, expected in manifest["commonSha256"].items():
        source = safe_path(template, name)
        if digest(source).hex() != expected:
            raise ValueError(f"Corrupt common artifact: {name}")
        target = safe_path(slot, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    target_manifest = manifest["targets"][TARGET]
    for name, expected in target_manifest["files"].items():
        source = safe_path(template / "targets" / TARGET, name)
        if target_manifest.get("packagedRipgrep") and name.startswith("ripgrep/"):
            source = safe_path(resources, name)
        if digest(source).hex() != expected:
            raise ValueError(f"Corrupt target artifact: {name}")
        target = safe_path(slot, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if (slot / ".server-target").read_text().strip() != TARGET:
        raise ValueError("Target identity mismatch")
    reference = (slot / ".runtime-node").read_text().strip()
    with tarfile.open(node_archive) as archive:
        archive.extractall(destination / "node", filter="data")
    node_root = destination / "node/node-v24.22.1-linux-x64"
    if digest(node_root / "bin/node").hex() != reference:
        raise ValueError("Node executable does not match Orca's pinned runtime")
    runtime_root = destination / "runtimes" / f"node-{reference}"
    runtime_root.parent.mkdir(exist_ok=True)
    shutil.move(str(node_root), runtime_root)
    version = json.loads((slot / "out/package.json").read_text())["version"]
    if version != ORCA_VERSION:
        raise ValueError("Orca version mismatch")
    # Upstream's canonical artifact order (schema 4, Linux glibc). The version is
    # the release version plus the first 12 hex characters of the concatenated
    # artifact SHA-256; the native runtime requires this identity at startup.
    mobile = sorted(
        name
        for name in manifest["commonSha256"]
        if name.startswith("out/mobile-web/") and not name.endswith("/manifest.json")
    )
    ordered = [name for name in manifest["commonSha256"] if name not in mobile]
    watcher = ordered.index("node_modules/@parcel/watcher/index.js")
    ordered[watcher:watcher] = [".server-target", ".runtime-node"]
    ordered.insert(watcher + 3, "node_modules/@parcel/watcher/watcher.node")
    ordered += ["node_modules/node-pty/build/Release/pty.node", "ripgrep/linux-x64/rg"] + mobile
    expected_names = set(manifest["commonSha256"]) | set(target_manifest["files"])
    if set(ordered) != expected_names or len(ordered) != len(expected_names):
        raise ValueError("Unreviewed artifact layout")
    combined = hashlib.sha256()
    for name in ordered:
        with (slot / name).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                combined.update(chunk)
    (slot / ".version").write_text(f"{ORCAD_ARTIFACT_VERSION}+{combined.hexdigest()[:12]}\n")
    renderer = resources / "app.asar.unpacked/out/renderer"
    web = destination / "web"
    web.mkdir()
    web_manifest = renderer / ".orca-web-client-files.json"
    files = json.loads(web_manifest.read_text())
    if "web-index.html" not in files:
        raise ValueError("Missing Orca web client")
    for name in files:
        source = safe_path(renderer, name)
        target = safe_path(web, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(web_manifest, web / web_manifest.name)
    shutil.copy2(template / "orcad-template.json", destination / "upstream-manifest.json")
    # All source artifacts are covered by the verified official Debian package.
    shutil.rmtree(extracted)
    shutil.rmtree(destination / "node")
    print(f"Verified Orca {version}, native addons, web client and pinned Node runtime")


if __name__ == "__main__":
    materialize(*(Path(arg).resolve() for arg in sys.argv[1:]))
