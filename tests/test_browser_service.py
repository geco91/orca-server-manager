import time

from manager import browser
from manager.app import create_app
from manager.control import atomic_document, read_document
from tests.test_manager import bootstrap, csrf, get, post
from tests.test_updates import controller_files


def test_stale_and_invalid_observations_never_enable_pairing():
    for state, observed, expected in [
        ("ready", 500, "ready"),
        ("ready", 425, "offline"),
        ("ready", 501, "offline"),
        ("disconnected", 500, "disconnected"),
        ("invalid", 500, "offline"),
    ]:
        assert browser.observation({"state": state, "observed": observed}, 500)["state"] == expected


def test_phone_qr_needs_login_csrf_and_native_readiness(monkeypatch, tmp_path):
    control = tmp_path / "control"
    controller_files(control)
    endpoint = "wss://localhost/orca-mobile"
    app = create_app(
        {
            "TESTING": True,
            "STATE_DIR": str(tmp_path / "state"),
            "CONTROL_DIR": control,
            "PHONE_ENDPOINT": endpoint,
        }
    )
    client = app.test_client()
    url = "/connections/mobile/pair"
    assert get(client, "/connections/mobile").status_code == 302
    bootstrap(app, client)
    assert post(client, url, {}).status_code == 400
    token = {"csrf_token": csrf(client, "/connections/mobile")}
    assert post(client, url, token).status_code == 503

    status = read_document(control / "status.json")
    status["browser"] = {"state": "ready", "observed": time.time()}
    atomic_document(control / "status.json", status)
    reply = post(client, url, token)
    assert reply.status_code == 303
    job_url = reply.location
    job = job_url.rsplit("/", 1)[-1]
    assert read_document(control / "requests" / f"{job}.json")["action"] == "pair_mobile"
    assert "Preparing QR code" in get(client, job_url).text
    other = app.test_client()
    from tests.test_manager import PASSWORD

    path = "/login"
    assert (
        post(other, path, {"csrf_token": csrf(other, path), "password": PASSWORD}).status_code
        == 302
    )
    assert get(other, job_url).status_code == 404

    secret = "orca://pair?code=private-fixture-code"
    (control / "pairings").mkdir(exist_ok=True)
    atomic_document(
        control / "pairings" / f"{job}.json",
        {
            "schema": 1,
            "id": job,
            "generation": status["deployment"]["generation"],
            "endpoint": endpoint,
            "pairing_url": secret,
            "expires_at": time.time() + 40,
        },
    )
    atomic_document(control / "results" / f"{job}.json", {"state": "completed"})
    monkeypatch.setattr(browser, "pairing_qr", lambda link: "fixture QR")
    result = get(client, job_url)
    assert result.status_code == 200 and secret in result.text
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["Referrer-Policy"] == "no-referrer"
    assert secret not in get(client, "/api/status").text


def test_native_lan_offer_only_for_the_own_pilot_address_and_certificate():
    cert = "subject=CN=Orca Server Manager\nissuer=CN=Orca Server Manager\n"
    origin = "https://192.168.1.12"
    assert browser.mobile_endpoint(origin, "192.168.1.12", cert) == "ws://192.168.1.12:6770"
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
