"""Validate native pairing links without inventing a second pairing protocol."""

import json
import time
from urllib.parse import parse_qs, urlsplit, urlunsplit

from manager.links import public_web_url

PAIRING_TTL = 120


class PairingError(ValueError):
    pass


def manager_origin(value):
    try:
        parts = urlsplit(public_web_url(value))
        if parts.scheme != "https" or not parts.hostname or parts.path not in {"", "/"}:
            raise ValueError
        host = parts.hostname.encode("idna").decode().lower()
        host = f"[{host}]" if ":" in host else host
        authority = host if parts.port in {None, 443} else f"{host}:{parts.port}"
        return urlunsplit(("https", authority, "", "", ""))
    except (ValueError, UnicodeError):
        raise PairingError(
            "The manager needs a valid HTTPS origin before preparing browser pairing."
        ) from None


def native_pairing(raw, origin, job_id, generation, now=None):
    """Forward Orca's own fragment URL; secrets never enter ordinary job results."""
    origin = manager_origin(origin)
    try:
        if len(raw) > 64 * 1024:
            raise ValueError
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise TypeError
        offer = response["result"]
        if not isinstance(offer, dict):
            raise TypeError
        if (
            response.get("ok") is not True
            or offer.get("available") is not True
            or offer.get("scope") != "runtime"
        ):
            raise ValueError
        if offer.get("endpoint") != origin.replace("https://", "wss://", 1) + "/orca":
            raise ValueError
        return validate_pairing(
            {
                "schema": 1,
                "id": job_id,
                "generation": generation,
                "origin": origin,
                "pairing_url": offer["pairingUrl"],
                "browser_url": offer["webClientUrl"],
                "expires_at": (time.time() if now is None else now) + PAIRING_TTL,
            },
            origin,
            job_id,
            generation,
            now,
        )
    except (KeyError, TypeError, ValueError):
        raise PairingError(
            "Orca did not return a usable browser pairing link. Try preparing it again."
        ) from None


def validate_pairing(value, origin, job_id, generation, now=None):
    try:
        origin = manager_origin(origin)
        if not isinstance(value, dict) or set(value) - {
            "schema",
            "id",
            "generation",
            "origin",
            "pairing_url",
            "browser_url",
            "expires_at",
            "code",
        }:
            raise TypeError
        if type(value.get("generation")) is not int:
            raise TypeError
        if (
            value.get("schema") != 1
            or value.get("id") != job_id
            or value.get("generation") != generation
        ):
            raise ValueError
        if value.get("origin") != origin:
            raise ValueError
        pairing_url, browser_url = value["pairing_url"], value["browser_url"]
        if any(
            not isinstance(link, str)
            or len(link) > 16384
            or "\\" in link
            or any(ord(c) <= 32 for c in link)
            for link in (pairing_url, browser_url)
        ):
            raise ValueError
        native = urlsplit(pairing_url)
        code = parse_qs(native.query)
        if (
            native.scheme != "orca"
            or native.netloc != "pair"
            or native.path not in {"", "/"}
            or native.fragment
        ):
            raise ValueError
        if set(code) != {"code"} or len(code["code"]) != 1 or not code["code"][0]:
            raise ValueError
        web = urlsplit(browser_url)
        if manager_origin(urlunsplit((web.scheme, web.netloc, "", "", ""))) != origin:
            raise ValueError
        if (
            web.path != "/orca/web-index.html"
            or web.query
            or parse_qs(web.fragment) != {"pairing": [pairing_url]}
        ):
            raise ValueError
        expires = value["expires_at"]
        if isinstance(expires, bool) or not isinstance(expires, (float, int)):
            raise TypeError
        remaining = expires - (time.time() if now is None else now)
        if not 0 < remaining <= PAIRING_TTL + 5:
            raise ValueError
        return {**value, "code": code["code"][0]}
    except (KeyError, TypeError, ValueError):
        raise PairingError(
            "This pairing link is unavailable or expired. Prepare another link."
        ) from None
