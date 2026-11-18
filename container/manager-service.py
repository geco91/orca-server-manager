#!/usr/bin/env python3
"""Container entrypoint: HTTPS proxy and an unprivileged manager, no host access."""

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

from manager.browser import mobile_endpoint
from manager.control import atomic_document
from manager.pairing import manager_origin
from manager.proxy import proxy_environment

data = Path(os.environ.get("OSM_DATA_DIR", "/data"))
data.mkdir(parents=True, exist_ok=True)
MANAGER_UID = 1001
state = data / "manager"
state.mkdir(mode=0o700, exist_ok=True)
os.chown(state, MANAGER_UID, MANAGER_UID)
certs = data / "tls"
certs.mkdir(mode=0o700, exist_ok=True)
proxy_state = data / "proxy"
proxy_state.mkdir(mode=0o700, exist_ok=True)
address = "127.0.0.1"
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("192.0.2.1", 9))  # Route selection only; no packet is sent.
        address = sock.getsockname()[0]
except OSError:
    pass
origin = manager_origin(os.environ.get("OSM_ORIGIN") or f"https://{address}")
environment = dict(
    os.environ,
    OSM_STATE_DIR=str(state),
    OSM_ORIGIN=origin,
    OSM_TRUSTED_HOSTS=os.environ.get("OSM_TRUSTED_HOSTS") or f"localhost,127.0.0.1,{address}",
)
if not (certs / "server.crt").exists() and not (certs / "server.key").exists():
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-sha256",
            "-nodes",
            "-days",
            "365",
            "-keyout",
            str(certs / "server.key"),
            "-out",
            str(certs / "server.crt"),
            "-subj",
            "/CN=Orca Server Manager",
            "-addext",
            f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{address}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.chmod(certs / "server.key", 0o600)
if not (certs / "server.crt").is_file() or not (certs / "server.key").is_file():
    raise RuntimeError("Incomplete persistent HTTPS certificate; restore it before starting.")
certificate_names = subprocess.check_output(
    [
        "openssl",
        "x509",
        "-in",
        str(certs / "server.crt"),
        "-noout",
        "-nameopt",
        "RFC2253",
        "-subject",
        "-issuer",
    ],
    text=True,
)
phone_endpoint = mobile_endpoint(origin, address, certificate_names)
atomic_document(
    data / "manager-origin.json", {"origin": origin, "mobile_endpoint": phone_endpoint}, mode=0o644
)
environment["OSM_PHONE_ENDPOINT"] = phone_endpoint
upstream = "127.0.0.1:6768"


def start_proxy(target):
    return subprocess.Popen(
        ["/usr/bin/caddy", "run", "--config", "/app/manager.Caddyfile"],
        env=proxy_environment(
            dict(environment, XDG_CONFIG_HOME=str(proxy_state), XDG_DATA_HOME=str(proxy_state)),
            target,
        ),
    )


children = [
    subprocess.Popen(
        [
            "/app/.venv/bin/gunicorn",
            "--bind=127.0.0.1:8080",
            "--workers=1",
            "--threads=4",
            "--umask=0077",
            "--no-control-socket",
            "manager.app:create_app()",
        ],
        cwd="/app",
        env=environment,
        user=MANAGER_UID,
        group=MANAGER_UID,
        extra_groups=[],
    ),
    start_proxy(upstream),
]
if os.environ.get("OSM_DASHBOARD_ONLY") != "1":
    children.append(
        subprocess.Popen(
            ["/opt/orca/node-bin/node", "/opt/osm/runtime-launch.cjs"],
            cwd="/workspaces",
            env={
                **os.environ,
                "HOME": "/home/orca",
                "USER": "orca",
                "LOGNAME": "orca",
                "ORCA_USER_DATA": "/home/orca/.config/Orca",
                "ORCA_USER_DATA_PATH": "/home/orca/.config/Orca",
                "PATH": "/opt/orca/node-bin:/usr/local/bin:/usr/bin:/bin",
            },
            user=1000,
            group=1000,
            extra_groups=[],
        )
    )
stopping = False


def stop(*_):
    global stopping
    stopping = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    while not stopping and all(child.poll() is None for child in children):
        time.sleep(0.25)
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=25)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
if not stopping:
    raise SystemExit("An application service stopped unexpectedly.")
