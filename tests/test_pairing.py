import json
import os
import time
from urllib.parse import urlencode

import pytest

from deploy.proxmox import pairing as private_pairing
from manager.app import create_app
from manager.control import atomic_document, read_document
from manager.pairing import (
    PAIRING_TTL,
    PairingError,
    manager_origin,
    native_pairing,
    validate_pairing,
)
from tests.test_manager import PASSWORD, bootstrap, csrf, get, post
from tests.test_updates import controller_files

ORIGIN = "https://localhost"
CODE = "test-only-native-offer"


def native_response(origin=ORIGIN):
    pairing = "orca://pair?" + urlencode({"code": CODE})
    return {
        "ok": True,
        "result": {
            "available": True,
            "scope": "runtime",
            "endpoint": origin.replace("https://", "wss://", 1) + "/orca",
            "pairingUrl": pairing,
            "webClientUrl": origin + "/orca/web-index.html#" + urlencode({"pairing": pairing}),
        },
    }


def test_native_browser_url_is_forwarded_without_a_second_pairing_protocol():
    raw = native_response()
    value = native_pairing(json.dumps(raw), ORIGIN, "a" * 32, 3, now=100)
    assert value["browser_url"] == raw["result"]["webClientUrl"]
    assert value["pairing_url"] == raw["result"]["pairingUrl"]
    assert value["code"] == CODE and value["expires_at"] == 100 + PAIRING_TTL
    with pytest.raises(PairingError):
        validate_pairing(value, ORIGIN, "a" * 32, 3, now=221)
    with pytest.raises(PairingError):
        validate_pairing(value, ORIGIN, "a" * 32, 4, now=101)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "https://user:secret@localhost",
        "https://localhost/?code=secret",
        "https://localhost/path",
        "https://localhost/#secret",
    ],
)
def test_only_the_configured_https_origin_can_receive_native_pairing(url):
    with pytest.raises(PairingError):
        manager_origin(url)


@pytest.mark.parametrize(
    "field,value",
    [
        ("webClientUrl", "https://external.invalid/orca/web-index.html#pairing=secret"),
        ("webClientUrl", ORIGIN + "/orca/web-index.html?pairing=secret"),
        ("webClientUrl", ORIGIN + "/orca/web-index.html#pairing=different"),
        ("pairingUrl", "javascript:secret"),
        ("scope", "mobile"),
        ("available", False),
        ("endpoint", "wss://external.invalid/orca"),
    ],
)
def test_invalid_native_payload_cannot_redirect_or_leak_credentials(field, value):
    raw = native_response()
    raw["result"][field] = value
    with pytest.raises(PairingError) as error:
        native_pairing(json.dumps(raw), ORIGIN, "a" * 32, 3)
    assert CODE not in str(error.value) and "secret" not in str(error.value)


@pytest.fixture
def portal(tmp_path):
    control = tmp_path / "control"
    controller_files(control)
    snapshot = read_document(control / "status.json")
    snapshot["runtime"]["web_url"] = "http://192.168.50.25:6768/web-index.html"
    atomic_document(control / "status.json", snapshot)
    app = create_app(
        {
            "TESTING": True,
            "STATE_DIR": str(tmp_path / "state"),
            "CONTROL_DIR": str(control),
            "ORIGIN": ORIGIN,
        }
    )
    return app, control


def prepare(client, open_tab="1"):
    return post(client, "/actions/web-pairing", {"csrf_token": csrf(client, "/"), "open": open_tab})


def finish(control, job_id, expires=None):
    (control / "pairings").mkdir(exist_ok=True)
    payload = native_pairing(json.dumps(native_response()), ORIGIN, job_id, 3)
    if expires is not None:
        payload["expires_at"] = expires
    atomic_document(control / "pairings" / (job_id + ".json"), payload, mode=0o640)
    atomic_document(
        control / "results" / (job_id + ".json"),
        {"id": job_id, "state": "completed", "message": "Native link ready."},
        mode=0o644,
    )
    return payload


def test_authenticated_post_prepares_a_native_connection_and_keeps_links_out_of_html(portal):
    app, control = portal
    with app.test_client() as client:
        bootstrap(app, client)
        assert post(client, "/actions/web-pairing", {}).status_code == 400
        response = prepare(client)
        assert response.status_code == 303 and "open=1" in response.location
        job_id = response.location.split("/")[-1].split("?")[0]
        queued = read_document(control / "requests" / (job_id + ".json"))
        assert queued["action"] == "pair_web" and queued["generation"] == 3
        assert "origin" not in queued and CODE not in json.dumps(queued)
        assert prepare(client).location == response.location
        payload = finish(control, job_id)
        page = get(client, response.location)
        assert CODE not in page.text and payload["pairing_url"] not in page.text
        assert "Manual fallback" in page.text
        # Same-origin form submissions must retain Referer for Flask-WTF's strict HTTPS check.
        assert page.headers["Referrer-Policy"] == "same-origin"
        result = get(client, "/api/web-pairing/" + job_id)
        assert result.json["state"] == "ready" and result.json["pairing"]["code"] == CODE
        assert result.headers["Cache-Control"] == "no-store"
        assert result.headers["Referrer-Policy"] == "no-referrer"
        assert CODE not in get(client, "/api/status").text
        again = prepare(client)
        assert again.location != response.location


def test_pairing_results_are_owned_by_the_requesting_browser_session(portal):
    app, control = portal
    with app.test_client() as first, app.test_client() as second:
        bootstrap(app, first)
        response = prepare(first)
        job_id = response.location.split("/")[-1].split("?")[0]
        finish(control, job_id)
        assert (
            post(
                second, "/login", {"csrf_token": csrf(second, "/login"), "password": PASSWORD}
            ).status_code
            == 302
        )
        get(second, "/")
        assert get(second, "/api/web-pairing/" + job_id).status_code == 404
        assert get(second, "/web-ui/" + job_id).status_code == 404
    with app.test_client() as anonymous:
        assert get(anonymous, "/api/web-pairing/" + job_id).status_code == 302


def test_expired_pairing_and_changed_runtime_never_return_a_code(portal):
    app, control = portal
    with app.test_client() as client:
        bootstrap(app, client)
        response = prepare(client)
        job_id = response.location.split("/")[-1].split("?")[0]
        finish(control, job_id, time.time() - 1)
        result = get(client, "/api/web-pairing/" + job_id)
        assert result.json["state"] == "expired" and CODE not in result.text
        finish(control, job_id)
        snapshot = read_document(control / "status.json")
        snapshot["deployment"]["generation"] += 1
        atomic_document(control / "status.json", snapshot)
        assert CODE not in get(client, "/api/web-pairing/" + job_id).text


def test_pairing_does_not_compete_with_an_active_version_change(portal):
    app, _ = portal
    with app.test_client() as client:
        bootstrap(app, client)
        response = post(
            client,
            "/actions/update",
            {"csrf_token": csrf(client, "/"), "version": "1.4.261", "work_stopped": "1"},
        )
        assert response.status_code == 302
        assert prepare(client).status_code == 409


@pytest.fixture
def protected_origin(tmp_path, monkeypatch):
    parent = tmp_path / "manager"
    parent.mkdir(mode=0o711)
    descriptor = parent / "manager-origin.json"
    atomic_document(descriptor, {"origin": ORIGIN}, mode=0o644)
    original = os.fstat

    def mapped_stat(fd):
        info = list(original(fd))
        info[4] = 100000
        return os.stat_result(info)

    monkeypatch.setattr(private_pairing.os, "fstat", mapped_stat)
    return tmp_path, descriptor


def test_worker_origin_comes_from_the_supervisor_descriptor(protected_origin):
    data, _ = protected_origin
    assert private_pairing.read_manager_origin(data) == ORIGIN


@pytest.mark.parametrize("replacement", ["symlink", "hardlink", "writable", "oversized", "bad"])
def test_untrusted_origin_descriptor_never_selects_a_pairing_destination(
    protected_origin, replacement
):
    data, descriptor = protected_origin
    if replacement == "symlink":
        descriptor.unlink()
        descriptor.symlink_to("/etc/passwd")
    elif replacement == "hardlink":
        os.link(descriptor, descriptor.with_name("another-link"))
    elif replacement == "writable":
        descriptor.chmod(0o666)
    elif replacement == "oversized":
        descriptor.write_text("x" * 4097)
    else:
        descriptor.write_text(json.dumps({"origin": "https://localhost/private?secret"}))
    with pytest.raises(PairingError) as error:
        private_pairing.read_manager_origin(data)
    assert "secret" not in str(error.value)
