#!/usr/bin/env python3
"""Install checksummed native provider CLIs from their official release assets."""

import hashlib
import io
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
    (
        "https://github.com/anomalyco/opencode/releases/download/v1.19.5/opencode-linux-x64.tar.gz",
        "588310a336fa3b9df36b3f0225b26f679d453efaad0cf3d66c3651ef3ec1647a",
        "opencode",
    ),
]


def main():
    destination = Path("/tools")
    destination.mkdir()
    for url, checksum, name in TOOLS:
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
