#!/usr/bin/env python3
"""Container entrypoint: HTTPS proxy and an unprivileged manager, no host access."""

import ipaddress
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

from manager.browser import SOCKET_DIR, mobile_endpoint
from manager.control import atomic_document
from manager.pairing import manager_origin
from manager.proxy import proxy_environment, proxy_target

data = Path(os.environ.get("OSM_DATA_DIR", "/data"))
data.mkdir(parents=True, exist_ok=True)
state = data / "manager"
state.mkdir(mode=0o700, exist_ok=True)
os.chown(state, 1000, 1000)
certs = data / "tls"
certs.mkdir(mode=0o700, exist_ok=True)
address = "127.0.0.1"
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("192.0.2.1", 9))  # Route selection only; no packet is sent.
        address = sock.getsockname()[0]
except OSError:
    pass
ipaddress.ip_address(address)
origin = manager_origin(os.environ.get("OSM_ORIGIN") or f"https://{address}")
atomic_document(data / "manager-origin.json", {"origin": origin}, mode=0o644)
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
upstream = proxy_target(os.environ.get("OSM_CONTROL_DIR"), os.environ.get("OSM_ORCA_UPSTREAM", ""))


def start_proxy(target):
    return subprocess.Popen(
        ["/usr/bin/caddy", "run", "--config", "/etc/caddy/Caddyfile"],
        env=proxy_environment(environment, target),
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
        user=1000,
        group=1000,
        extra_groups=[],
    ),
    start_proxy(upstream),
]
browser_home = data / "browser"
browser_home.mkdir(mode=0o700, exist_ok=True)
os.chown(browser_home, 1001, 1001)
SOCKET_DIR.mkdir(exist_ok=True)
os.chown(SOCKET_DIR, 1001, 1000)
os.chmod(SOCKET_DIR, 0o2750)
browser = None
retry_browser = 0
stopping = False


def stop(*_):
    global stopping
    stopping = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    observed_proxy = 0
    while not stopping and all(child.poll() is None for child in children):
        if (browser is None or browser.poll() is not None) and time.monotonic() >= retry_browser:
            browser = subprocess.Popen(
                ["/usr/local/bin/python3", "/app/browser-service.py", "supervise"],
                user=1001,
                group=1001,
                extra_groups=[],
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "OSM_ORIGIN": origin,
                    "OSM_PHONE_ENDPOINT": phone_endpoint,
                },
            )
            retry_browser = time.monotonic() + 15
        if time.monotonic() - observed_proxy > 2:
            observed_proxy = time.monotonic()
            candidate = proxy_target(
                os.environ.get("OSM_CONTROL_DIR"), os.environ.get("OSM_ORCA_UPSTREAM", "")
            )
            if candidate and candidate != upstream:
                # Reuse Caddy; only a changed assigned runtime address restarts this child.
                children[1].terminate()
                children[1].wait(timeout=15)
                children[1] = start_proxy(candidate)
                upstream = candidate
        time.sleep(0.25)
finally:
    if browser is not None:
        children.append(browser)
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
