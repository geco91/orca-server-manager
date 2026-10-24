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
        assert "Einrichtung fehlgeschlagen" in response.text
        assert get(client, "/").status_code == 302
        assert bootstrap(app, client).status_code == 302
        from pathlib import Path

        assert not (Path(app.config["STATE_DIR"]) / "bootstrap.token").exists()
        assert get(client, "/setup").status_code == 302
        with sqlite3.connect(Path(app.config["STATE_DIR"]) / "manager.sqlite3") as db:
            hashed = db.execute("SELECT hash FROM admin").fetchone()[0]
        assert PASSWORD not in hashed
        assert hashed.startswith("scrypt:")


def test_skip_is_csrf_protected_and_status_never_claims_integrations_work(app):
    with app.test_client() as client:
        bootstrap(app, client)
        page = get(client, "/")
        assert "Nicht erreichbar" in page.text
        assert "Nicht verifiziert" in page.text
        assert post(client, "/steps/github/skip", {"skip": "1"}).status_code == 400
        assert (
            post(
                client, "/steps/github/skip", {"skip": "1", "csrf_token": csrf(client, "/")}
            ).status_code
            == 302
        )
        assert "Später einrichten" in get(client, "/").text
        assert (
            post(client, "/steps/server/skip", {"csrf_token": csrf(client, "/")}).status_code == 404
        )
        status = get(client, "/api/status").json
        assert status["runtime"]["state"] == "error"
        assert set(status["integrations"].values()) == {"unverified"}
        for key in status["integrations"]:
            assert get(client, f"/connections/{key}").status_code == 200


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
