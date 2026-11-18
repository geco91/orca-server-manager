"""A private, short-lived channel from the scoped worker to the manager."""

import json
import os
import stat
import time
from pathlib import Path

from manager.control import JOB_ID, atomic_document, read_document
from manager.pairing import PairingError, manager_origin


def private_channel(control):
    control = Path(control)
    parent = control.stat(follow_symlinks=False)
    if control.is_symlink() or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise PairingError("The private pairing channel is not administrator-owned.")
    path = control / "pairings"
    if not path.exists():
        path.mkdir(mode=0o700)
        os.chown(path, 0, 101000)
        os.chmod(path, 0o2710)
    info = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != 0
        or info.st_gid != 101000
        or stat.S_IMODE(info.st_mode) != 0o2710
    ):
        raise PairingError("The private pairing channel has unexpected permissions.")
    return path


def read_manager_settings(data):
    parent = os.open(Path(data) / "manager", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != 100000 or info.st_mode & 0o022:
            raise PairingError("The manager origin is not protected by its administrator.")
        fd = os.open(
            "manager-origin.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != 100000
                or info.st_mode & 0o022
                or info.st_size > 4096
                or info.st_nlink != 1
            ):
                raise PairingError("The manager origin has unexpected ownership or permissions.")
            document = json.loads(stream.read(4097))
            document["origin"] = manager_origin(document["origin"])
            return document
    except (OSError, ValueError, KeyError, TypeError):
        raise PairingError(
            "The manager's HTTPS origin is not ready. Refresh and try again."
        ) from None
    finally:
        os.close(parent)


def read_manager_origin(data):
    return read_manager_settings(data)["origin"]


def publish_pairing(control, value):
    path = private_channel(control)
    if not JOB_ID.fullmatch(value.get("id", "")):
        raise PairingError("Invalid pairing request.")
    # setgid on the root-owned directory maps group access to manager GID 1000.
    atomic_document(path / (value["id"] + ".json"), value, mode=0o640)


def prune_pairings(control, now=None):
    path = Path(control) / "pairings"
    if not path.exists():
        return
    path = private_channel(control)
    for item in path.glob("*.json"):
        if not JOB_ID.fullmatch(item.stem):
            continue
        try:
            expired = read_document(item).get("expires_at", 0) <= (
                time.time() if now is None else now
            )
        except (ValueError, TypeError):
            expired = True
        if expired:
            item.unlink()
