#!/usr/bin/env python3
"""Real HTTPS/login/runtime/restart test in disposable Compose volumes, no provider calls."""

import http.client
import http.cookiejar
import json
import os
import re
import secrets
import ssl
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://localhost:18443"


def main():
    project = f"osm-smoke-{os.getpid()}"
    command = ["docker", "compose", "-p", project, "-f", "compose/compose.yaml"]
    environment = dict(
        os.environ,
        OSM_HTTP_PORT="18080",
        OSM_HTTPS_PORT="18443",
        OSM_ORIGIN=ORIGIN,
        ORCA_PORT="16768",
        OSM_BIND_IP="127.0.0.1",
        ORCA_BIND_IP="127.0.0.1",
        OSM_TRUSTED_HOSTS="localhost,127.0.0.1",
    )

    def compose(*args):
        return subprocess.run(
            command + list(args),
            cwd=ROOT,
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        ).stdout

    tls = ssl.create_default_context(cafile=str(ROOT / "state/tls/server.crt"))
    browser = build_opener(
        ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar()), HTTPSHandler(context=tls)
    )

    def page(path):
        with browser.open(ORIGIN + path, timeout=5) as response:
            return response.read().decode()

    def csrf(path):
        return re.search(r'name="csrf_token" value="([^"]+)"', page(path))[1]

    def post(path, values):
        req = Request(
            ORIGIN + path, data=urlencode(values).encode(), headers={"Referer": ORIGIN + path}
        )
        with browser.open(req, timeout=5) as response:
            return response.read().decode()

    def wait_ready():
        for _ in range(60):
            try:
                page("/healthz")
                output = compose("exec", "-T", "runtime", "orca", "status", "--json")
                status = json.loads(output)
                if status.get("result", {}).get("runtime", {}).get("reachable") is not True:
                    raise ValueError("Orca RPC is not reachable")
                return
            except (URLError, OSError, ValueError, subprocess.CalledProcessError):
                time.sleep(1)
        raise RuntimeError("Stack did not become ready within 60 seconds")

    try:
        compose("up", "-d", "--wait", "--wait-timeout", "90")
        wait_ready()
        # Verify the HTTP redirect without following it.
        connection = http.client.HTTPConnection("127.0.0.1", 18080, timeout=5)
        connection.request("GET", "/setup")
        response = connection.getresponse()
        assert response.status == 308
        assert response.getheader("Location") == ORIGIN + "/setup"
        connection.close()
        assert "Willkommen an Bord" in page("/setup")
        token = compose("exec", "-T", "manager", "cat", "/data/bootstrap.token").strip()
        password = secrets.token_urlsafe(24)
        html = post("/setup", {"csrf_token": csrf("/setup"), "token": token, "password": password})
        assert "Setup & Verbindungen" in html
        status = json.loads(page("/api/status"))
        assert status["runtime"]["state"] == "reachable", status
        try:
            post("/steps/github/skip", {"skip": "1"})
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("CSRF-less mutation was accepted")
        post("/steps/github/skip", {"csrf_token": csrf("/"), "skip": "1"})
        compose(
            "exec",
            "-T",
            "runtime",
            "sh",
            "-c",
            "printf 'persistence-smoke' > /workspaces/.osm-smoke-marker",
        )
        compose("up", "-d", "--force-recreate", "runtime", "manager")
        wait_ready()
        assert "Später einrichten" in page("/")
        assert json.loads(page("/api/status"))["runtime"]["state"] == "reachable"
        assert (
            compose("exec", "-T", "runtime", "cat", "/workspaces/.osm-smoke-marker")
            == "persistence-smoke"
        )
        compose("exec", "-T", "runtime", "orca", "worktree", "list", "--json")
        print(
            "PASS: verified TLS, HTTP redirect, admin bootstrap, session, CSRF, real Orca RPC, "
            "runtime web client, container recreation and persistent data"
        )
    finally:
        # Only this script's unique project and its own disposable volumes are removed.
        compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
