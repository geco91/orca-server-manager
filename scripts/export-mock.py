#!/usr/bin/env python3
"""Export the isolated UI prototype as a single offline HTML file."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(destination):
    template = (ROOT / "mock/index.html").read_text()
    styles = "\n".join(
        path.read_text() for path in (ROOT / "manager/static/style.css", ROOT / "mock/style.css")
    )
    result = template.replace("/* MOCK_STYLES */", styles).replace(
        "/* MOCK_SCRIPT */", (ROOT / "mock/app.js").read_text()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result)
    print(f"Offline demo: {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", nargs="?", type=Path, default=ROOT / "dist/orca-manager-mock.html"
    )
    export(parser.parse_args().output.resolve())
