"""Local, authenticated access to the native browser service."""

import ipaddress
import re
import subprocess
import time
from urllib.parse import urlsplit

from manager.pairing import PAIRING_TTL, PairingError, manager_origin

DESKTOP_PORT = 6770
PAIR_URL = re.compile(r"orca://pair\?code=[A-Za-z0-9_-]{16,8192}={0,2}")
STATES = {
    "ready": (
        "Ready",
        "The desktop can stream a browser and has authenticated to the workspace server.",
    ),
    "starting": ("Starting", "Orca is starting its private display."),
    "enrollment": (
        "Connecting",
        "Orca is pairing the browser service with the assigned workspace server.",
    ),
    "display": (
        "Display unavailable",
        "The native desktop has not reported browser streaming and mobile relay support.",
    ),
    "sandbox": (
        "Browser could not start",
        "The sandboxed desktop exited during startup. Check the runtime container’s browser sandbox and memory.",
    ),
    "disconnected": (
        "Server offline",
        "The browser service cannot reach its paired workspace server. It will retry automatically.",
    ),
    "incompatible": (
        "Update needed",
        "This workspace server does not advertise delegated mobile access.",
    ),
    "revoked": (
        "Reconnecting",
        "Orca refused the saved device grant. The browser service will renew the internal pairing.",
    ),
    "offline": ("Unavailable", "The manager has no recent observation from the browser service."),
}


def mobile_endpoint(origin, interface_address, certificate_names):
    origin = manager_origin(origin)
    local = ipaddress.ip_address(interface_address)
    # Orca Mobile pins the host key from its QR and encrypts native LAN traffic.
    # Use this mode only for our own self-signed certificate at this guest's RFC1918 IP.
    networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    if (
        urlsplit(origin).hostname == str(local)
        and set(certificate_names.splitlines())
        == {"subject=CN=Orca Server Manager", "issuer=CN=Orca Server Manager"}
        and any(local in ipaddress.ip_network(network) for network in networks)
    ):
        return f"ws://{local}:{DESKTOP_PORT}"
    return origin.replace("https://", "wss://", 1) + "/orca-mobile"


def observation(value, now=None, *, endpoint=""):
    try:
        if not isinstance(value, dict):
            raise TypeError
        age = (time.time() if now is None else now) - value["observed"]
        state = value["state"] if 0 <= age < 75 and value["state"] in STATES else "offline"
    except (OSError, KeyError, TypeError, ValueError):
        state = "offline"
    label, detail = STATES[state]
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "transport": "lan" if endpoint.startswith("ws://") else "https",
    }


def validate_offer(value, endpoint, job_id, generation, now=None):
    try:
        if (
            value["schema"] != 1
            or value["id"] != job_id
            or value["generation"] != generation
            or value["endpoint"] != endpoint
            or not PAIR_URL.fullmatch(value["pairing_url"])
            or not 0 < value["expires_at"] - (time.time() if now is None else now) <= PAIRING_TTL
        ):
            raise ValueError
        return value["pairing_url"]
    except (TypeError, KeyError, ValueError):
        raise PairingError("The mobile pairing code is unavailable or has expired.") from None


def pairing_qr(value):
    from markupsafe import Markup

    # qrencode receives the credential on stdin. Its SVG stays in this private response.
    svg = subprocess.run(
        ["qrencode", "-t", "SVG", "--inline", "-m", "4", "-o", "-"],
        input=value,
        text=True,
        capture_output=True,
        check=True,
        timeout=4,
    ).stdout
    if "<svg" not in svg:
        raise ValueError("QR code unavailable.")
    return Markup(svg)
