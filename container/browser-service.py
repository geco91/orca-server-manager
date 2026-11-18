#!/usr/bin/env python3
"""Run Orca's private virtual display and expose one local mobile-pairing operation."""

import json
import os
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path

from manager.browser import PAIR_URL, SOCKET_DIR, STATES, observation
from manager.control import atomic_document

HOME_DIR = Path("/data/browser")
PROFILE = HOME_DIR / "profile"
ENVIRONMENT = HOME_DIR / "workspace-server.json"
ELECTRON = "/opt/Orca/orca-ide"


def native_environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(HOME_DIR),
        "LANG": "C.UTF-8",
        "XDG_RUNTIME_DIR": str(SOCKET_DIR / "display"),
        "ORCA_USER_DATA_PATH": str(PROFILE),
        "ORCA_TELEMETRY_DISABLED": "1",
        "OSM_PHONE_ENDPOINT": os.environ.get("OSM_PHONE_ENDPOINT", ""),
        "NO_PROXY": "127.0.0.1,localhost",
    }


def native(action, *args, payload=None, timeout=12):
    result = subprocess.run(
        [ELECTRON, "/app/browser-native.cjs", action, *args],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        timeout=timeout,
        env={**native_environment(), "ELECTRON_RUN_AS_NODE": "1"},
    )
    return json.loads(result.stdout)


def environment_id():
    try:
        value = json.loads(ENVIRONMENT.read_bytes())["id"]
        return value if isinstance(value, str) and 0 < len(value) <= 128 else ""
    except (ValueError, OSError, TypeError, KeyError):
        return ""


def needs_enrollment():
    return not environment_id() or observation()["state"] == "revoked"


def enroll():
    if needs_enrollment():
        raw = sys.stdin.buffer.readline(16385)
        if len(raw) > 16384:
            raise ValueError()
        result = native("enroll", payload=raw.decode(), timeout=20)
        atomic_document(ENVIRONMENT, {"id": result["id"]})
        # Restart this private display when the catalog changes, including renewals.
        (SOCKET_DIR / "reload").touch()


def launch():
    args = [
        "xvfb-run",
        "-a",
        "-s",
        "-screen 0 1280x800x24 -nolisten tcp",
        "dbus-run-session",
        "--",
        ELECTRON,
        f"--user-data-dir={PROFILE}",
        "--disable-gpu",
        "--disable-dev-shm-usage",
    ]
    # Unprivileged PVE containers can block userns while allowing Chromium's
    # packaged setuid sandbox. The helper creates isolated PID/network namespaces.
    if subprocess.run(["unshare", "-Ur", "true"], check=False, capture_output=True).returncode:
        helper = Path("/opt/Orca/chrome-sandbox").stat()
        if helper.st_uid != 0 or stat.S_IMODE(helper.st_mode) != 0o4755:
            raise OSError("The packaged Chromium sandbox helper is unavailable.")
        args.append("--disable-namespace-sandbox")
    return subprocess.Popen(
        args,
        env=native_environment(),
        cwd=HOME_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_display(process):
    if process:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=6)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def pair_client(client, state):
    client.settimeout(1)
    _, uid, _ = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    with client.makefile("rb") as reader:
        if uid != 1000 or state != "ready" or reader.readline(16) != b"pair\n":
            return
    result = native("offer")
    if PAIR_URL.fullmatch(result.get("pairing_url", "")):
        client.sendall(json.dumps(result).encode() + b"\n")


def supervise():
    os.umask(0o077)
    (SOCKET_DIR / "display").mkdir(exist_ok=True, mode=0o700)
    PROFILE.mkdir(exist_ok=True, mode=0o700)
    endpoint = SOCKET_DIR / "pair.sock"
    endpoint.unlink(missing_ok=True)
    process = None
    state, stopping = "starting", False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(endpoint))
        endpoint.chmod(0o660)
        listener.listen(4)
        listener.settimeout(0.5)
        next_start = next_probe = next_report = 0
        try:
            while not stopping:
                now = time.monotonic()
                if (SOCKET_DIR / "reload").exists():
                    (SOCKET_DIR / "reload").unlink(missing_ok=True)
                    stop_display(process)
                    process, next_start = None, 0
                if process and process.poll() is not None:
                    stop_display(process)
                    process, state, next_start, next_report = None, "sandbox", now + 30, 0
                identity = environment_id()
                if not identity:
                    state = "enrollment"
                elif not process and now >= next_start:
                    try:
                        process = launch()
                        state, next_probe = "starting", now + 3
                    except (OSError, subprocess.SubprocessError):
                        state, next_start = "sandbox", now + 30
                    next_report = 0
                elif process and now >= next_probe:
                    try:
                        state = native("probe", identity)["state"]
                        if state not in STATES:
                            state = "display"
                    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                        state = "display"
                    next_probe, next_report = now + 15, 0
                if now >= next_report:
                    atomic_document(
                        SOCKET_DIR / "status.json",
                        {
                            "state": state,
                            "observed": time.time(),
                            "transport": "lan"
                            if os.environ.get("OSM_PHONE_ENDPOINT", "").startswith("ws://")
                            else "https",
                        },
                        mode=0o640,
                    )
                    next_report = now + 10
                try:
                    client, _ = listener.accept()
                except TimeoutError:
                    continue
                with client:
                    try:
                        pair_client(client, state)
                    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
                        pass
        finally:
            stop_display(process)
            endpoint.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["supervise"]:
            supervise()
        elif sys.argv[1:] == ["enrollment-needed"]:
            print("needed" if needs_enrollment() else "stored")
        elif sys.argv[1:] == ["enroll"]:
            enroll()
        else:
            sys.exit(2)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError):
        sys.exit("Native browser operation unavailable.")
