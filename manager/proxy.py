"""Resolve the assigned native WebUI upstream for the existing HTTPS proxy."""

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

from manager.control import ControlError, read_document
from manager.links import public_web_url


def proxy_environment(environment, target):
    result = dict(environment, OSM_ORCA_UPSTREAM=target or "127.0.0.1:9")
    host = result["OSM_ORCA_UPSTREAM"].rsplit(":", 1)[0]
    bypass = ",".join(filter(None, [result.get("NO_PROXY"), result.get("no_proxy"), host]))
    result.update(NO_PROXY=bypass, no_proxy=bypass)
    return result


def proxy_target(directory, configured=""):
    if configured:
        if not re.fullmatch(r"[A-Za-z0-9.-]+:6768", configured):
            raise ValueError("Use the assigned Orca hostname or IPv4 address on port 6768.")
        return configured
    if not directory:
        return None
    try:
        snapshot = read_document(Path(directory) / "status.json")
        url = public_web_url(snapshot.get("runtime", {}).get("web_url"))
        if not url:
            return None
        parts = urlsplit(url)
        address = ipaddress.IPv4Address(parts.hostname)
        if not address.is_private or address.is_loopback or address.is_unspecified:
            return None
        if parts.scheme != "http" or parts.port != 6768 or parts.path != "/web-index.html":
            return None
        return f"{address}:6768"
    except (ControlError, ValueError, TypeError, AttributeError):
        return None
