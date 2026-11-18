import json

from manager import browser
from manager.app import create_app
from tests.test_manager import bootstrap, csrf, get, post


def test_stale_and_invalid_observations_never_enable_pairing(tmp_path):
    for state, observed, expected in [
        ("ready", 500, "ready"),
        ("ready", 425, "offline"),
        ("ready", 501, "offline"),
        ("disconnected", 500, "disconnected"),
        ("invalid", 500, "offline"),
    ]:
        (tmp_path / "status.json").write_text(json.dumps({"state": state, "observed": observed}))
        assert browser.observation(tmp_path, 500)["state"] == expected


def test_phone_qr_needs_login_csrf_and_native_readiness(monkeypatch, tmp_path):
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "BROWSER_DIR": tmp_path}
    )
    client = app.test_client()
    url = "/connections/mobile/pair"
    assert get(client, "/connections/mobile").status_code == 302
    bootstrap(app, client)
    assert post(client, url, {}).status_code == 400
    token = {"csrf_token": csrf(client, "/connections/mobile")}
    assert post(client, url, token).status_code == 503
    monkeypatch.setattr(
        browser,
        "observation",
        lambda path: {"state": "ready", "label": "Ready", "detail": "Native"},
    )
    monkeypatch.setattr(
        browser, "phone_offer", lambda path: ("orca://pair?code=private-qr", "fixture-qr")
    )
    assert (
        "private-qr"
        not in get(client, "/connections/mobile").text + get(client, "/api/status").text
    )
    reply = post(client, url, token)
    assert reply.status_code == 200 and "private-qr" in reply.text
    assert (
        reply.headers["Cache-Control"] == "no-store"
        and reply.headers["Referrer-Policy"] == "no-referrer"
    )

    def unavailable(path):
        raise OSError()

    monkeypatch.setattr(browser, "phone_offer", unavailable)
    assert post(client, url, token).status_code == 503


def test_native_lan_offer_only_for_the_own_pilot_address_and_certificate():
    cert = "subject=CN=Orca Server Manager\nissuer=CN=Orca Server Manager\n"
    origin = "https://192.168.1.12"
    assert browser.mobile_endpoint(origin, "192.168.1.12", cert) == "ws://192.168.1.12:6768"
    for address, interface, names in [
        (origin, "192.168.1.13", cert),
        (origin, "192.168.1.12", "issuer=CN=Private CA"),
        ("https://orca.example", "192.168.1.12", cert),
        ("https://127.0.0.1", "127.0.0.1", cert),
    ]:
        assert (
            browser.mobile_endpoint(address, interface, names)
            == address.replace("https:", "wss:") + "/orca-mobile"
        )
