#!/usr/bin/env python3
"""Disposable container smoke test: verified TLS, English UI, native RPC, MCP and persistence."""

import http.client
import http.cookiejar
import json
import os
import re
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    project = f"osm-smoke-{os.getpid()}"
    http_port, https_port = free_port(), free_port()
    origin = f"https://localhost:{https_port}"
    command = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        "compose/compose.yaml",
        "-f",
        "compose/mcp.yaml",
    ]
    with tempfile.TemporaryDirectory(prefix="osm-smoke-") as directory:
        temporary = Path(directory)
        token_file = temporary / "bridge-token"
        token_file.write_text(secrets.token_urlsafe(36))
        token_file.chmod(0o600)
        environment = dict(
            os.environ,
            OSM_HTTP_PORT=str(http_port),
            OSM_HTTPS_PORT=str(https_port),
            OSM_ORIGIN=origin,
            ORCA_PORT=str(free_port()),
            OSM_BIND_IP="127.0.0.1",
            ORCA_BIND_IP="127.0.0.1",
            OSM_TRUSTED_HOSTS="localhost,127.0.0.1",
            OSM_BRIDGE_TOKEN_FILE=str(token_file),
        )

        def compose(*args):
            result = subprocess.run(
                command + list(args),
                cwd=ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
                timeout=180,
            )
            if result.returncode:
                # Do not echo stdout: an exec call deliberately reads a private setup token.
                raise RuntimeError(f"Compose {args[0]} failed: {result.stderr.strip()}")
            return result.stdout

        try:
            compose("up", "-d", "--wait", "--wait-timeout", "120")
            certificate = temporary / "server.crt"
            compose("cp", "manager:/data/tls/server.crt", str(certificate))
            browser = build_opener(
                ProxyHandler({}),
                HTTPCookieProcessor(http.cookiejar.CookieJar()),
                HTTPSHandler(context=ssl.create_default_context(cafile=str(certificate))),
            )

            def page(path):
                with browser.open(origin + path, timeout=40) as response:
                    return response.read().decode()

            def csrf(path):
                return re.search(r'name="csrf_token" value="([^"]+)"', page(path))[1]

            def post(path, values):
                req = Request(
                    origin + path,
                    data=urlencode(values).encode(),
                    headers={"Referer": origin + path},
                )
                with browser.open(req, timeout=15) as response:
                    return response.read().decode()

            connection = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
            connection.request("GET", "/setup")
            response = connection.getresponse()
            assert response.status == 308 and response.getheader("Location") == origin + "/setup"
            connection.close()
            assert '<html lang="en">' in page("/setup")
            token = compose(
                "exec",
                "-T",
                "--user",
                "1000:1000",
                "manager",
                "cat",
                "/data/manager/bootstrap.token",
            ).strip()
            html = post(
                "/setup",
                {
                    "csrf_token": csrf("/setup"),
                    "token": token,
                    "password": secrets.token_urlsafe(24),
                },
            )
            assert "Run Orca. Keep connections in view." in html
            status = json.loads(page("/api/status"))
            assert status["runtime"]["state"] == "unknown"  # Compose has no Proxmox worker.
            assert not status["controller"]["available"]
            assert "optional" in page("/connections/github").lower()
            assert "OpenAI Secure MCP Tunnel" in page("/connections/tunnel")
            from urllib.error import HTTPError

            try:
                post("/actions/refresh", {})
            except HTTPError as error:
                assert error.code == 400
            else:
                raise AssertionError("CSRF-less mutation was accepted")
            native = json.loads(
                compose("exec", "-T", "runtime", "node", "/opt/osm/runtime-status.cjs")
            )
            assert native["runtime"]["reachable"] is True
            assert native["runtime"]["version"] == "1.4.261"
            assert native["runtime"]["active_terminals"] == 0
            provider_checks = {
                row["name"]: row["value"] for row in native["integrations"]["providers"]["checks"]
            }
            assert provider_checks["Codex CLI"] == provider_checks["OpenCode CLI"] == "Installed"
            assert native["integrations"]["providers"]["state"] != "ready"
            assert native["integrations"]["mcp"]["state"] == "ready", native["integrations"]["mcp"]
            assert native["integrations"]["tunnel"]["state"] == "unknown"
            compose(
                "exec",
                "-T",
                "runtime",
                "sh",
                "-c",
                "printf 'persistence-smoke' > /workspaces/.osm-smoke-marker",
            )
            compose(
                "up",
                "-d",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "120",
                "runtime",
                "manager",
            )
            for _ in range(20):
                try:
                    assert "Run Orca." in page("/")
                    break
                except (OSError, AssertionError):
                    time.sleep(0.5)
            else:
                raise AssertionError("Manager session did not survive recreation")
            assert (
                compose("exec", "-T", "runtime", "cat", "/workspaces/.osm-smoke-marker")
                == "persistence-smoke"
            )
            native = json.loads(
                compose("exec", "-T", "runtime", "node", "/opt/osm/runtime-status.cjs")
            )
            assert (
                native["runtime"]["reachable"] and native["integrations"]["mcp"]["state"] == "ready"
            )
            print(
                "PASS: verified TLS/redirect, English administrator setup, session, CSRF, native Orca 1.4.261 RPC, installed provider CLIs, real MCP health and persistent data after recreation. No agent dispatched; no tunnel or Proxmox deployment claimed."
            )
        finally:
            compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
