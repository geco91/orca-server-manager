"""Small file protocol between the unprivileged UI and its scoped deployment worker."""

import json
import os
import re
import secrets
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

from manager.pairing import validate_pairing
from manager.releases import require_upgrade, validate_version

JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
TERMINAL_STATES = {"completed", "failed", "blocked", "interrupted"}
MAX_JSON = 128 * 1024


class ControlError(ValueError):
    pass


def utc_now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_document(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON:
                raise ControlError("The controller document must be a bounded regular file.")
            raw = stream.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ControlError("The controller response is too large.")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ControlError("Unexpected controller response.")
        return result
    except (OSError, ValueError) as error:
        if isinstance(error, ControlError):
            raise
        raise ControlError(
            "The deployment controller has not supplied a readable result."
        ) from error


def atomic_document(path, value, mode=0o600):
    path = Path(path)
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Controller:
    def __init__(self, directory):
        self.directory = Path(directory) if directory else None

    def snapshot(self):
        if not self.directory:
            return {
                "controller": {
                    "available": False,
                    "detail": "Deployment controller not configured.",
                }
            }
        try:
            snapshot = read_document(self.directory / "status.json")
            stamp = datetime.fromisoformat(snapshot["observed_at"]).timestamp()
            if not -5 <= time.time() - stamp <= 90:
                raise ControlError("The last controller observation is stale. Refresh the status.")
            if snapshot.get("schema") != 1:
                raise ControlError("Unsupported controller protocol.")
            if any(
                not isinstance(snapshot.get(key, {}), dict)
                for key in ["runtime", "integrations", "deployment"]
            ):
                raise ControlError("Unexpected controller status shape.")
            snapshot["controller"] = {
                "available": True,
                "detail": "Connected to the scoped Proxmox deployment worker.",
            }
            return snapshot
        except (ControlError, KeyError, TypeError, ValueError) as error:
            return {"controller": {"available": False, "detail": str(error)}}

    def result(self, job_id):
        if not JOB_ID.fullmatch(job_id or "") or not self.directory:
            raise ControlError("Unknown operation.")
        try:
            return read_document(self.directory / "results" / f"{job_id}.json")
        except ControlError:
            return {
                "id": job_id,
                "state": "queued",
                "message": "Waiting for the deployment worker.",
            }

    def submit(self, action, version=None, restore_data=False):
        if action not in {"refresh", "update", "rollback", "pair_web"}:
            raise ControlError("Unsupported deployment action.")
        if action == "update":
            validate_version(version)
        elif version is not None:
            raise ControlError("This action does not take a version.")
        if action != "rollback" and restore_data:
            raise ControlError("Data restoration is only available during a rollback.")
        snapshot = self.snapshot()
        if not snapshot["controller"]["available"]:
            raise ControlError(
                "The deployment controller is unavailable. No operation was started."
            )
        deployment = snapshot.get("deployment", {})
        if action == "pair_web" and (
            snapshot.get("runtime", {}).get("reachable") is not True
            or not snapshot.get("runtime", {}).get("web_url")
        ):
            raise ControlError(
                "The Orca WebUI is not reachable yet. Refresh the server status and try again."
            )
        if action == "update":
            require_upgrade(version, deployment.get("version"))
        if action == "rollback" and not deployment.get("previous_version"):
            raise ControlError("There is no saved previous version to roll back to.")
        job_id = secrets.token_hex(16)
        request = {
            "schema": 1,
            "id": job_id,
            "action": action,
            "version": version,
            "restore_data": bool(restore_data),
            "created_at": utc_now(),
            "generation": snapshot.get("deployment", {}).get("generation", 0),
        }
        atomic_document(self.directory / "requests" / f"{job_id}.json", request)
        return request

    def pairing(self, job_id, origin):
        if not JOB_ID.fullmatch(job_id or "") or not self.directory:
            raise ControlError("Unknown pairing request.")
        snapshot = self.snapshot()
        if not snapshot["controller"]["available"]:
            raise ControlError("Refresh the runtime status before opening this pairing link.")
        payload = read_document(self.directory / "pairings" / (job_id + ".json"))
        return validate_pairing(
            payload, origin, job_id, snapshot.get("deployment", {}).get("generation")
        )
