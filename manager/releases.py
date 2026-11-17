"""Official Orca release metadata; no local approval or stability classification."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]{0,60})?\Z")
SHA256 = re.compile(r"sha256:([a-f0-9]{64})\Z")
API = "https://api.github.com/repos/stablyai/orca"
ASSET_ARCH = {"amd64": "x64", "arm64": "arm64"}


class ReleaseError(ValueError):
    pass


def validate_version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ReleaseError("Choose an Orca release version.")
    return value


def version_key(value):
    core, separator, prerelease = validate_version(value).partition("-")
    identifiers = (
        tuple((0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split("."))
        if separator
        else ()
    )
    return tuple(map(int, core.split("."))), not separator, identifiers


def require_upgrade(version, installed):
    if version_key(version) <= version_key(installed):
        raise ReleaseError(
            "Choose a newer Orca release. Older software is available only through a saved rollback."
        )


def upgrades_only(catalog, installed):
    """Filter cached upstream metadata against the current installed version."""
    current = version_key(installed)
    releases = [
        release for release in catalog["releases"] if version_key(release["version"]) > current
    ]
    return catalog | {"releases": releases, "has_more": bool(releases) and catalog["has_more"]}


def read_json(url):
    req = Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "orca-server-manager"},
    )
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ReleaseError("The release response is too large.")
            return json.loads(raw)
    except (HTTPError, URLError, OSError, ValueError) as error:
        if isinstance(error, ReleaseError):
            raise
        raise ReleaseError("Official Orca release metadata is currently unavailable.") from error


def normalize_release(item, arch="amd64"):
    tag = item.get("tag_name", "")
    if not tag.startswith("v") or not VERSION.fullmatch(tag[1:]) or item.get("draft"):
        return None
    asset_name = f"orca-server-linux-{ASSET_ARCH[arch]}.tar.gz"
    asset = next((a for a in item.get("assets", []) if a.get("name") == asset_name), {})
    checksum = SHA256.fullmatch(asset.get("digest") or "")
    web_name = f"orca-ide_{tag[1:]}_{arch}.deb"
    web_asset = next((a for a in item.get("assets", []) if a.get("name") == web_name), {})
    web_checksum = SHA256.fullmatch(web_asset.get("digest") or "")
    return {
        "version": tag[1:],
        "tag": tag,
        "name": str(item.get("name") or tag)[:200],
        "prerelease": bool(item.get("prerelease")),
        "published_at": str(item.get("published_at") or ""),
        "url": f"https://github.com/stablyai/orca/releases/tag/{quote(tag)}",
        "server_available": bool(asset and checksum),
        "asset": asset_name if asset else None,
        "sha256": checksum[1] if checksum else None,
        "web_asset": web_name if web_asset else None,
        "web_sha256": web_checksum[1] if web_checksum else None,
        "download_url": (
            f"https://github.com/stablyai/orca/releases/download/{quote(tag)}/{asset_name}"
            if asset
            else None
        ),
    }


def list_releases(page=1, arch="amd64"):
    if arch not in ASSET_ARCH or not isinstance(page, int) or not 1 <= page <= 100:
        raise ReleaseError("Invalid release page or architecture.")
    items = read_json(f"{API}/releases?per_page=30&page={page}")
    if not isinstance(items, list):
        raise ReleaseError("Unexpected official release response.")
    return {
        "releases": [
            release for item in items if (release := normalize_release(item, arch)) is not None
        ],
        "has_more": len(items) == 30,
        "page": page,
    }


def resolve_release(version, arch="amd64"):
    validate_version(version)
    if arch not in ASSET_ARCH:
        raise ReleaseError("Unsupported server architecture.")
    item = read_json(f"{API}/releases/tags/v{quote(version)}")
    release = normalize_release(item, arch)
    if not release or release["version"] != version or not release["server_available"]:
        raise ReleaseError("This Orca release has no checksummed server package for this platform.")
    return release
