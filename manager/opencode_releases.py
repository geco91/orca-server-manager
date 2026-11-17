"""Official OpenCode packages; version choice is not a local release approval."""

from urllib.parse import quote

from manager.releases import SHA256, VERSION, ReleaseError, read_json, version_key

DEFAULT_VERSION = "2.3.0"
LEGACY_VERSION = "1.19.5"
API = "https://api.github.com/repos/anomalyco/opencode"
ASSETS = {"amd64": "opencode-linux-x64.tar.gz", "arm64": "opencode-linux-arm64.tar.gz"}


def validate_version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ReleaseError("Choose an OpenCode release version.")
    return value


def require_upgrade(version, installed):
    validate_version(version)
    validate_version(installed)
    if version_key(version) <= version_key(installed):
        raise ReleaseError(
            "Choose a newer OpenCode release. Older software is available only through a saved rollback."
        )


def normalize_release(item, arch="amd64"):
    if not isinstance(item, dict):
        return None
    tag = item.get("tag_name", "")
    if (
        not isinstance(tag, str)
        or not tag.startswith("v")
        or not VERSION.fullmatch(tag[1:])
        or item.get("draft")
    ):
        return None
    name = ASSETS[arch]
    assets = item.get("assets") or []
    asset = next((a for a in assets if isinstance(a, dict) and a.get("name") == name), {})
    digest = SHA256.fullmatch(asset.get("digest") or "")
    return {
        "version": tag[1:],
        "tag": tag,
        "name": str(item.get("name") or tag)[:200],
        "prerelease": bool(item.get("prerelease")),
        "published_at": str(item.get("published_at") or ""),
        "url": f"https://github.com/anomalyco/opencode/releases/tag/{quote(tag)}",
        "package_available": bool(asset and digest),
        "asset": name if asset else None,
        "sha256": digest[1] if digest else None,
        "download_url": f"https://github.com/anomalyco/opencode/releases/download/{quote(tag)}/{name}"
        if asset
        else None,
    }


def list_releases(page=1, arch="amd64"):
    if arch not in ASSETS or not isinstance(page, int) or not 1 <= page <= 100:
        raise ReleaseError("Invalid OpenCode release page or architecture.")
    try:
        items = read_json(f"{API}/releases?per_page=30&page={page}")
    except ReleaseError:
        raise ReleaseError("Official OpenCode release metadata is currently unavailable.") from None
    if not isinstance(items, list):
        raise ReleaseError("Unexpected official OpenCode release response.")
    return {
        "releases": [r for item in items if (r := normalize_release(item, arch)) is not None],
        "has_more": len(items) == 30,
        "page": page,
    }


def resolve_release(version, arch="amd64"):
    validate_version(version)
    if arch not in ASSETS:
        raise ReleaseError("Unsupported OpenCode platform.")
    try:
        item = read_json(f"{API}/releases/tags/v{quote(version)}")
    except ReleaseError:
        raise ReleaseError("Official OpenCode release metadata is currently unavailable.") from None
    release = normalize_release(item, arch)
    if not release or release["version"] != version or not release["package_available"]:
        raise ReleaseError("This OpenCode release has no checksummed package for this platform.")
    return release
