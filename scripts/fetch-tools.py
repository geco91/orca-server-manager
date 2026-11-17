#!/usr/bin/env python3
"""Install checksummed native provider CLIs from their official release assets."""

import argparse
import hashlib
import io
import re
import tarfile
from pathlib import Path
from urllib.request import urlopen

TOOLS = [
    (
        (
            "https://github.com/openai/codex/releases/download/rust-v0.169.0/"
            "codex-x86_64-unknown-linux-musl.tar.gz"
        ),
        "9af4d751fce183faedea629437d5252dbf458eeb04130cf4f97be844621ea985",
        "codex",
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opencode-version", default="1.19.5")
    parser.add_argument(
        "--opencode-sha256",
        default="588310a336fa3b9df36b3f0225b26f679d453efaad0cf3d66c3651ef3ec1647a",
    )
    args = parser.parse_args()
    if not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]{0,60})?", args.opencode_version
    ):
        parser.error("Choose an official OpenCode version.")
    if not re.fullmatch(r"[a-f0-9]{64}", args.opencode_sha256):
        parser.error("Provide the published OpenCode package checksum.")
    tools = TOOLS + [
        (
            f"https://github.com/anomalyco/opencode/releases/download/v{args.opencode_version}/opencode-linux-x64.tar.gz",
            args.opencode_sha256,
            "opencode",
        )
    ]
    destination = Path("/tools")
    destination.mkdir()
    for url, checksum, name in tools:
        with urlopen(url, timeout=90) as source:
            payload = source.read(300 * 1024 * 1024 + 1)
        if len(payload) > 300 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != checksum:
            raise ValueError("Official provider package checksum mismatch")
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            candidates = [
                member
                for member in archive.getmembers()
                if member.isfile()
                and (
                    Path(member.name).name == name
                    or (name == "codex" and Path(member.name).name.startswith("codex-"))
                )
            ]
            if len(candidates) != 1:
                raise ValueError("Unexpected official provider archive layout")
            binary = destination / name
            with archive.extractfile(candidates[0]) as source, binary.open("wb") as out:
                while block := source.read(1024 * 1024):
                    out.write(block)
            binary.chmod(0o755)
    print("Official Codex and OpenCode packages verified.")


if __name__ == "__main__":
    main()
