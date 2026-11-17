"""Public provider destinations and the only Git setup data shared with the browser."""

import math
import re
import time

PROVIDERS = {
    "github": {
        "name": "GitHub",
        "host": "github.com",
        "signup": "https://github.com/signup",
        "verify": "https://github.com/login/device",
        "action": "login_github",
    },
    "gitlab": {
        "name": "GitLab",
        "host": "gitlab.com",
        "signup": "https://gitlab.com/users/sign_up",
        "verify": "https://gitlab.com/oauth/device",
        "action": "login_gitlab",
    },
    "forgejo": {"name": "Forgejo", "action": "forgejo_key"},
}
ACTIONS = {provider["action"]: key for key, provider in PROVIDERS.items()}
LIFETIME = 600
CODE = re.compile(r"[A-Z0-9]{4}-?[A-Z0-9]{4}")
PUBLIC_KEY = re.compile(r"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI[A-Za-z0-9+/]{43}")


class OfferError(ValueError):
    pass


def public_state(provider, value):
    if not isinstance(value, dict):
        raise OfferError("The runtime returned an invalid Git setup response.")
    state = value.get("state")
    if not isinstance(state, str):
        raise OfferError("Missing Git setup state.")
    if provider in {"github", "gitlab"}:
        if (
            state == "waiting"
            and isinstance(value.get("code"), str)
            and CODE.fullmatch(value["code"])
        ):
            return {"state": state, "code": value["code"]}
        if state in {"starting", "authorized", "failed", "expired"}:
            return {"state": state}
    if (
        provider == "forgejo"
        and state == "key_ready"
        and isinstance(value.get("public_key"), str)
        and PUBLIC_KEY.fullmatch(value["public_key"])
    ):
        return {"state": state, "public_key": value["public_key"]}
    raise OfferError("The runtime returned an invalid Git setup response.")


def private_offer(document, provider, job_id, generation):
    expires = document.get("expires_at")
    if (
        document.get("kind") != "git_setup"
        or document.get("id") != job_id
        or document.get("provider") != provider
        or type(generation) is not int
        or type(document.get("generation")) is not int
        or document.get("generation") != generation
        or type(expires) not in {int, float}
        or not math.isfinite(expires)
        or not 0 < expires - time.time() <= LIFETIME + 5
    ):
        raise ValueError("This Git setup attempt expired. Start a new one.")
    return public_state(provider, document)
