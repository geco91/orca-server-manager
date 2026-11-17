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
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
        # Compose file secrets retain the host UID. The temporary parent is 0700;
        # allow runtime UID 1000 to read this disposable nonce on UID 1001 CI too.
        # Native PVE production secrets remain 0600 with mapped ownership.
        token_file.chmod(0o444)
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
            ORCA_WEB_URL=origin + "/orca/web-index.html",
        )

        def compose(*args, input_data=None):
            result = subprocess.run(
                command + list(args),
                cwd=ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
                input=input_data,
                timeout=180,
            )
            if result.returncode:
                # Do not echo stdout: an exec call deliberately reads a private setup token.
                raise RuntimeError(f"Compose {args[0]} failed; private command output suppressed.")
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
            assert 'minlength="8"' in page("/setup")
            web = page("/orca/web-index.html")
            assert "<html" in web.lower() and "Orca" in web
            asset = re.search(r'src="([^\"]+\.js)"', web)
            assert asset, "Original Orca WebUI script is missing"
            with browser.open(
                urljoin(origin + "/orca/web-index.html", asset[1]), timeout=15
            ) as response:
                assert response.status == 200 and "javascript" in response.headers["Content-Type"]
            from urllib.error import HTTPError

            for path in ["/orca/package.json", "/orca/.orca-web-client-files.json"]:
                try:
                    page(path)
                except HTTPError as error:
                    assert error.code == 404
                else:
                    raise AssertionError("The native WebUI exposed a non-browser file")
            token = compose(
                "exec",
                "-T",
                "--user",
                "1000:1000",
                "manager",
                "cat",
                "/data/manager/bootstrap.token",
            ).strip()
            password = secrets.token_hex(4)
            html = post(
                "/setup",
                {
                    "csrf_token": csrf("/setup"),
                    "token": token,
                    "password": password,
                },
            )
            assert "Connect your Git accounts" in html and "Versions &amp; updates" not in html
            html = post("/welcome/continue", {"csrf_token": csrf("/")})
            assert "Open Orca WebUI" in html and "OpenCode 2" in html
            html = post("/welcome/finish", {"csrf_token": csrf("/welcome")})
            assert "Your Orca workspace" in html
            status = json.loads(page("/api/status"))
            assert status["runtime"]["state"] == "unknown"  # Compose has no Proxmox worker.
            assert not status["controller"]["available"]
            assert "Get a sign-in code" in page("/connections/github")
            assert "OpenAI Secure MCP Tunnel" in page("/connections/tunnel")
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
            assert native["runtime"]["opencode_version"] == "2.3.0"
            assert set(native["runtime"]["git_setup"]) == {"github", "gitlab", "forgejo"}
            assert native["runtime"]["active_terminals"] == 0
            assert native["runtime"]["web_url"].endswith(":6768/web-index.html")
            from pairing_smoke import check_pairing

            check_pairing(compose, native, origin, page, post, csrf, password)
            provider_checks = {
                row["name"]: row["value"] for row in native["integrations"]["providers"]["checks"]
            }
            assert provider_checks["Codex CLI"] == provider_checks["OpenCode CLI"] == "Installed"
            assert provider_checks["Host default agent"] == "OpenCode 2"
            assert provider_checks["Managed OpenCode accounts"] == "0"
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
                    assert "Your Orca workspace" in page("/")
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
            token_file.chmod(0o000)
            compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "120", "runtime")
            native = json.loads(
                compose("exec", "-T", "runtime", "node", "/opt/osm/runtime-status.cjs")
            )
            assert native["runtime"]["reachable"] is True
            assert native["integrations"]["mcp"]["state"] == "error"
            print(
                "PASS: verified TLS/redirect, eight-character English administrator setup, original HTTPS WebUI/assets and native proxy pairing, session, CSRF, native Orca 1.4.261 RPC, installed provider CLIs, real MCP health, persistence after recreation and runtime startup with unreadable optional bridge configuration. No agent dispatched; no tunnel or Proxmox deployment claimed."
            )
        finally:
            compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
