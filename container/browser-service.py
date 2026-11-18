#!/usr/bin/env python3
"""Supervise the native Orca browser inside the workspace runtime."""

import fcntl
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STATE = Path.home() / ".local/share/osm-browser"
PRIVATE_HOME = STATE / "home"
PROFILE = STATE / "profile"
ENROLLMENT = STATE / "workspace-server.json"
ELECTRON = "/opt/Orca/orca-ide"
INTERNAL = "ws://127.0.0.1:6768"
DESKTOP_PORT = 6770


def document(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
        json.dump(value, stream)
    Path(stream.name).replace(path)


def environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(PRIVATE_HOME),
        "LANG": "C.UTF-8",
        "XDG_RUNTIME_DIR": str(STATE / "display"),
        "ORCA_USER_DATA_PATH": str(PROFILE),
        "ORCA_TELEMETRY_DISABLED": "1",
        "NO_PROXY": "127.0.0.1,localhost",
    }


def native(action, *args, payload=None, timeout=12):
    result = subprocess.run(
        [ELECTRON, "/opt/osm/browser-native.cjs", action, *args],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        timeout=timeout,
        env={**environment(), "ELECTRON_RUN_AS_NODE": "1"},
        cwd=STATE,
    )
    return json.loads(result.stdout)


def enrollment():
    try:
        return json.loads(ENROLLMENT.read_bytes())["id"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def enroll():
    result = subprocess.run(
        ["/usr/local/bin/orca", "pair", "--address", INTERNAL, "--json"],
        capture_output=True,
        text=True,
        timeout=12,
        check=True,
    )
    offer = json.loads(result.stdout)["result"]
    paired = native(
        "enroll", enrollment(), payload=json.dumps({"pairingUrl": offer["pairingUrl"]}), timeout=20
    )
    document(ENROLLMENT, {"id": paired["id"], "endpoint": INTERNAL})


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
    if subprocess.run(["unshare", "-Ur", "true"], check=False, capture_output=True).returncode:
        helper = Path("/opt/Orca/chrome-sandbox").stat()
        if helper.st_uid != 0 or stat.S_IMODE(helper.st_mode) != 0o4755:
            raise OSError("The packaged Chromium sandbox helper is unavailable.")
        args.append("--disable-namespace-sandbox")
    # Orca's native fallback keeps its mobile listener separate from orcad on 6768.
    document(PROFILE / "mobile-ws-fallback-port.json", {"port": DESKTOP_PORT})
    return subprocess.Popen(
        args,
        env=environment(),
        cwd=PRIVATE_HOME,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_display(process):
    if process is not None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=6)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def supervise():
    os.umask(0o077)
    for directory in (PROFILE, PRIVATE_HOME, STATE / "display"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # The same lock covers normal OCI startup and a live migration of an existing guest.
    with (STATE / "service.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_display()


def run_display():
    process = None
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def report(state):
        document(STATE / "status.json", {"state": state, "observed": time.time()})

    try:
        while not stopping:
            next_probe = time.monotonic() + 15
            try:
                saved = json.loads(ENROLLMENT.read_bytes()) if ENROLLMENT.is_file() else {}
                if saved.get("endpoint") != INTERNAL:
                    report("enrollment")
                    enroll()
                if process is None:
                    report("starting")
                    process = launch()
                    next_probe = time.monotonic() + 4
                elif process.poll() is not None:
                    stop_display(process)
                    process = None
                    report("sandbox")
                else:
                    status = native("probe", enrollment())["state"]
                    report(status)
                    if status == "revoked":
                        stop_display(process)
                        process = None
                        enroll()
            except (OSError, TypeError, ValueError, KeyError, subprocess.SubprocessError):
                if process is not None:
                    report("display")
            while not stopping and time.monotonic() < next_probe:
                time.sleep(0.25)
    finally:
        stop_display(process)
        (STATE / "status.json").unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["supervise"]:
            supervise()
        elif sys.argv[1:] == ["offer"]:
            print(json.dumps(native("offer", sys.stdin.readline(4096).strip())))
        else:
            sys.exit(2)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        sys.exit("Native browser operation unavailable.")
