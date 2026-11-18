import re
import sqlite3

import pytest

from manager.app import create_app

PASSWORD = "test-only-long-password"


@pytest.fixture
def app(tmp_path):
    return create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path), "ORCA_INTERNAL_URL": "http://127.0.0.1:9"}
    )


def get(client, path):
    return client.get(path, base_url="https://localhost")


def csrf(client, path):
    response = get(client, path)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text)[1]


def post(client, path, data):
    return client.post(
        path,
        data=data,
        base_url="https://localhost",
        headers={"Referer": "https://localhost" + path},
    )


def bootstrap(app, client):
    from pathlib import Path

    token = (Path(app.config["STATE_DIR"]) / "bootstrap.token").read_text()
    return post(
        client,
        "/setup",
        {"csrf_token": csrf(client, "/setup"), "token": token, "password": PASSWORD},
    )


def test_protected_routes_require_login_and_https(app):
    with app.test_client() as client:
        assert get(client, "/").status_code == 302
        assert get(client, "/api/status").status_code == 302
        assert get(client, "/connections/github").status_code == 302
        assert client.get("/").status_code == 400
        assert client.get("/healthz").json == {"status": "ok", "service": "orca-server-manager"}
        assert client.get("/healthz", base_url="https://evil.example").status_code == 400


def test_setup_requires_token_strong_password_and_csrf(app):
    with app.test_client() as client:
        assert post(client, "/setup", {"token": "bad", "password": PASSWORD}).status_code == 400
        response = post(
            client,
            "/setup",
            {"csrf_token": csrf(client, "/setup"), "token": "bad", "password": PASSWORD},
        )
        assert "Setup failed" in response.text
        assert get(client, "/").status_code == 302
        assert bootstrap(app, client).status_code == 302
        from pathlib import Path

        assert not (Path(app.config["STATE_DIR"]) / "bootstrap.token").exists()
        assert get(client, "/setup").status_code == 302
        with sqlite3.connect(Path(app.config["STATE_DIR"]) / "manager.sqlite3") as db:
            hashed = db.execute("SELECT hash FROM admin").fetchone()[0]
        assert PASSWORD not in hashed
        assert hashed.startswith("scrypt:")


def test_native_guides_are_optional_and_unobserved_status_stays_unknown(app):
    with app.test_client() as client:
        bootstrap(app, client)
        page = get(client, "/overview")
        assert '<html lang="en">' in page.text
        assert "Not verified" in page.text
        assert "GitHub" in page.text and "Revisit setup" in page.text
        assert "0%" not in page.text
        assert post(client, "/actions/refresh", {}).status_code == 400
        status = get(client, "/api/status").json
        assert status["runtime"]["state"] == "unknown"
        assert not status["controller"]["available"]
        assert {row["state"] for row in status["integrations"].values()} == {"unknown"}
        for key in status["integrations"]:
            assert (
                client.get(
                    f"/connections/{key}", base_url="https://localhost", follow_redirects=True
                ).status_code
                == 200
            )
        assert "OpenAI Secure MCP Tunnel" in get(client, "/connections/tunnel").text
        assert "Show pairing QR code" in get(client, "/connections/mobile").text
        result = post(client, "/actions/refresh", {"csrf_token": csrf(client, "/")})
        assert result.status_code == 503


def test_login_logout_cookie_flags_and_persistence(app):
    with app.test_client() as client:
        response = bootstrap(app, client)
        cookie = response.headers["Set-Cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
        assert "Content-Security-Policy" in response.headers
        assert "Strict-Transport-Security" in response.headers
        assert post(client, "/logout", {"csrf_token": csrf(client, "/")}).status_code == 302
        assert get(client, "/").status_code == 302
    # New app process, same files: no new bootstrap, same administrator and session key.
    restarted = create_app(
        {
            "TESTING": True,
            "STATE_DIR": app.config["STATE_DIR"],
            "ORCA_INTERNAL_URL": "http://127.0.0.1:9",
        }
    )
    assert restarted.secret_key == app.secret_key
    with restarted.test_client() as client:
        assert get(client, "/setup").status_code == 302
        response = post(
            client, "/login", {"csrf_token": csrf(client, "/login"), "password": PASSWORD}
        )
        assert response.status_code == 302
        assert get(client, "/").status_code == 200


def test_repeated_bad_bootstrap_is_throttled(app):
    with app.test_client() as client:
        token = csrf(client, "/setup")
        for _ in range(5):
            assert (
                post(
                    client, "/setup", {"csrf_token": token, "token": "wrong", "password": PASSWORD}
                ).status_code
                == 200
            )
        assert bootstrap(app, client).status_code == 429


def test_local_password_reset_invalidates_old_sessions(app):
    with app.test_client() as client:
        bootstrap(app, client)
        result = app.test_cli_runner().invoke(
            args=["reset-admin", "--password", "replacement-test-password"]
        )
        assert result.exit_code == 0, result.output
        assert get(client, "/").status_code == 302


@pytest.mark.parametrize("length,accepted", [(7, False), (8, True), (256, True), (257, False)])
def test_admin_setup_accepts_eight_characters_and_keeps_the_length_bounds(app, length, accepted):
    from pathlib import Path

    with app.test_client() as client:
        token = (Path(app.config["STATE_DIR"]) / "bootstrap.token").read_text()
        html = get(client, "/setup").text
        assert 'minlength="8"' in html and "8–256 characters" in html
        response = post(
            client,
            "/setup",
            {
                "csrf_token": csrf(client, "/setup"),
                "token": token,
                "password": "x" * length,
            },
        )
        assert (response.status_code == 302) is accepted
        assert (Path(app.config["STATE_DIR"]) / "bootstrap.token").exists() is not accepted


def test_local_password_reset_accepts_eight_characters(app):
    with app.test_client() as client:
        bootstrap(app, client)
        result = app.test_cli_runner().invoke(args=["reset-admin", "--password", "testpass"])
        assert result.exit_code == 0
        assert (
            post(
                client, "/login", {"csrf_token": csrf(client, "/login"), "password": "testpass"}
            ).status_code
            == 302
        )
