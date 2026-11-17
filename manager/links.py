"""Public browser links, without native pairing credentials."""

from urllib.parse import urlsplit


def public_web_url(value):
    if not isinstance(value, str) or len(value) > 2048 or "\\" in value:
        return ""
    if any(ord(char) <= 32 or ord(char) == 127 for char in value):
        return ""
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
        ):
            return ""
        _ = parts.port
    except ValueError:
        return ""
    return value
