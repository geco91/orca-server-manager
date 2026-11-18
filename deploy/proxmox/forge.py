"""Advance a native CLI sign-in while keeping the normal Proxmox worker available."""

import json
import subprocess
import time
from datetime import datetime

from deploy.proxmox.pairing import publish_pairing
from manager.control import JOB_ID, atomic_document, read_document
from manager.forge import ACTIONS, LIFETIME, public_state


def observe(worker, job, provider, operation):
    job_id = job["id"]
    created = datetime.fromisoformat(str(job["created_at"]))
    if created.tzinfo is None or not -5 <= time.time() - created.timestamp() < LIFETIME:
        raise ValueError("This sign-in request expired. Start a new one.")
    if job["generation"] != worker.cfg["generation"]:
        raise ValueError("The runtime changed. Start a new sign-in.")
    worker.own_manager()
    runtime_id = worker.cfg["runtime_id"]
    worker.own_container(runtime_id)
    raw = worker.run(
        [
            "pct",
            "exec",
            str(runtime_id),
            "--",
            "/usr/sbin/runuser",
            "-u",
            "orca",
            "--",
            "/usr/bin/env",
            "--chdir=/workspaces",
            "/opt/orca/node-bin/node",
            "/opt/osm/forge.cjs",
            operation,
            provider,
            job_id,
        ],
        timeout=20,
    )
    if len(raw) > 2048:
        raise ValueError("Unexpected Git setup response.")
    reply = public_state(provider, json.loads(raw))
    publish_pairing(
        worker.control,
        {
            "kind": "git_setup",
            "id": job_id,
            "generation": job["generation"],
            "provider": provider,
            "expires_at": created.timestamp() + LIFETIME,
            **reply,
        },
        group=worker.manager_gid,
    )
    if reply["state"] in {"starting", "waiting"}:
        worker.result(job, "running", "Waiting for authorization at the Git provider.")
        return False
    completed = reply["state"] in {"authorized", "key_ready"}
    worker.result(
        job,
        "completed" if completed else "failed",
        "Native Git setup finished."
        if completed
        else "Sign-in ended. Start a new code or use the runtime instructions.",
    )
    return True


def start(worker, job):
    provider = ACTIONS[job["action"]]
    directory = worker.private / "git-setup"
    directory.mkdir(mode=0o700, exist_ok=True)
    pending = directory / (provider + ".json")
    if pending.exists():
        raise ValueError("A sign-in is already in progress for this provider.")
    atomic_document(pending, job)
    try:
        done = observe(worker, job, provider, "start")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pending.unlink(missing_ok=True)
        raise
    if done:
        pending.unlink(missing_ok=True)


def poll(worker):
    for action, provider in ACTIONS.items():
        pending = worker.private / "git-setup" / (provider + ".json")
        if not pending.exists():
            continue
        try:
            job = read_document(pending)
            if (
                not isinstance(job.get("id"), str)
                or not JOB_ID.fullmatch(job["id"])
                or job.get("action") != action
                or not isinstance(job.get("created_at"), str)
                or type(job.get("generation")) is not int
            ):
                raise ValueError("Invalid pending sign-in.")
        except ValueError:
            pending.replace(pending.with_suffix(".invalid"))
            continue
        try:
            done = observe(worker, job, provider, "read")
        except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
            worker.result(
                job, "failed", "Sign-in expired or the runtime changed. Start a new attempt."
            )
            done = True
        if done:
            pending.unlink(missing_ok=True)
