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
    (
        "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/packages/generic/glab/1.131.0/glab_1.131.0_linux_amd64.tar.gz",
        "580dbca43835b47267e512476a442f6b2e8785a82b26ccacee22bd7010662b2d",
        "glab",
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opencode-version", default="2.3.0")
    parser.add_argument(
        "--opencode-sha256",
        default="fc0f81522aceeabac47693d88389efa2bc517ce74c2c38fd6967819fcc6e4d3b",
    )
    args = parser.parse_args()
    if not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]{0,60})?", args.opencode_version
    ):
        parser.error("Choose an official OpenCode version.")
    if not re.fullmatch(r"[a-f0-9]{64}", args.opencode_sha256):
        parser.error("Provide the published OpenCode package checksum.")
    is_v2 = args.opencode_version.startswith("2.")
    tools = TOOLS + [
        (
            f"https://github.com/anomalyco/opencode/releases/download/v{args.opencode_version}/opencode-linux-x64.tar.gz",
            args.opencode_sha256,
            "opencode2" if is_v2 else "opencode",
        )
    ]
    if is_v2:
        # Orca detects v1 and v2 by separate executable names.
        tools.append(
            (
                "https://github.com/anomalyco/opencode/releases/download/v1.19.5/opencode-linux-x64.tar.gz",
                "588310a336fa3b9df36b3f0225b26f679d453efaad0cf3d66c3651ef3ec1647a",
                "opencode",
            )
        )
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
                    Path(member.name).name == ("opencode" if name == "opencode2" else name)
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
    print("Official provider and GitLab CLI packages verified.")


if __name__ == "__main__":
    main()
