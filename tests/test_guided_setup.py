import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path

import pytest

from deploy.proxmox import forge
from deploy.proxmox.worker import validate_request
from manager.app import create_app
from manager.control import atomic_document, read_document, utc_now
from manager.forge import LIFETIME, private_offer, public_state
from tests.test_manager import PASSWORD, bootstrap, csrf, get, post
from tests.test_updates import controller_files


def manager_fixture(tmp_path):
    control = tmp_path / "control"
    controller_files(control)
    status = read_document(control / "status.json")
    status["runtime"].update(
        git_setup=["github", "gitlab", "forgejo"],
        web_url="http://192.168.50.25:6768/web-index.html",
    )
    atomic_document(control / "status.json", status)
    (control / "pairings").mkdir()
    return create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    ), control


def test_github_copy_url_matches_the_authorize_button_and_has_its_own_target(tmp_path):
    app, _ = manager_fixture(tmp_path)
    client = app.test_client()
    bootstrap(app, client)
    html = get(client, "/git/github?setup=1").text
    link = re.search(r'<a [^>]*href="([^"]+)"[^>]*>Authorize on github\.com', html)
    assert link and link[1] == "https://github.com/login/device"
    assert f'id="authorization-url" value="{link[1]}" readonly' in html[link.end() :]
    assert 'data-copy="authorization-url" class="quiet">Copy URL</button>' in html
    assert 'data-copy="offer-value" class="quiet">Copy code</button>' in html


@pytest.mark.parametrize("provider", ["github", "gitlab"])
def test_guided_provider_prioritizes_continue_when_server_is_signed_in(tmp_path, provider):
    app, control = manager_fixture(tmp_path)
    client = app.test_client()
    bootstrap(app, client)
    path = f"/git/{provider}?setup=1"
    assert 'id="forge-continue" class="quiet"' in get(client, path).text
    status = read_document(control / "status.json")
    status["integrations"][provider] = {
        "state": "ready",
        "checks": [{"name": "Server identity", "value": "example-account"}],
    }
    atomic_document(control / "status.json", status)
    html = get(client, path).text
    assert 'id="git-setup" class="setup-shell signed-in"' in html
    assert 'id="forge-continue">Continue to Orca' in html
    assert html.index('id="forge-continue"') < html.index("Sign in again")
    assert 'form="forge-start" class="quiet sign-in-again"' in html
    assert post(client, "/welcome/continue", {"csrf_token": csrf(client, path)}).location.endswith(
        "/welcome?step=launch"
    )
    assert not list((control / "requests").iterdir())


def test_first_run_resumes_and_can_finish_without_a_git_account(tmp_path):
    app, _ = manager_fixture(tmp_path)
    client = app.test_client()
    bootstrap(app, client)
    html = get(client, "/").text
    assert "Connect your Git accounts" in html and 'id="main-nav"' not in html
    assert all(f'href="/git/{p}?setup=1"' in html for p in ["github", "gitlab", "forgejo"])
    assert post(client, "/welcome/continue", {}).status_code == 400
    assert post(client, "/welcome/continue", {"csrf_token": csrf(client, "/")}).status_code == 303
    resumed = create_app(app.config.copy()).test_client()
    post(resumed, "/login", {"password": PASSWORD, "csrf_token": csrf(resumed, "/login")})
    html = get(resumed, "/").text
    assert (
        "Open your Orca workspace" in html
        and 'action="/actions/web-pairing" target="_blank"' in html
    )
    assert post(resumed, "/welcome/finish", {"csrf_token": csrf(resumed, "/")}).status_code == 303
    html = get(client, "/").text
    assert "Your Orca workspace" in html and 'id="main-nav"' in html
    assert "Connect your Git accounts" in get(client, "/welcome").text
    assert "Your Orca workspace" in get(client, "/").text


@pytest.mark.parametrize(
    ("provider", "action", "code"),
    [
        ("github", "login_github", "ABCD-1234"),
        ("gitlab", "login_gitlab", "ABCD1234"),
    ],
)
def test_private_user_code_belongs_to_original_session_and_deployment(
    tmp_path, provider, action, code
):
    app, control = manager_fixture(tmp_path)
    first, second = app.test_client(), app.test_client()
    bootstrap(app, first)
    post(second, "/login", {"password": PASSWORD, "csrf_token": csrf(second, "/login")})
    route = f"/git/{provider}"
    assert post(first, route + "/start", {}).status_code == 400
    assert post(first, route + "/start", {"csrf_token": csrf(first, route)}).status_code == 303
    assert post(first, route + "/start", {"csrf_token": csrf(first, route)}).status_code == 303
    assert post(second, route + "/start", {"csrf_token": csrf(second, route)}).status_code == 409
    jobs = list((control / "requests").iterdir())
    assert len(jobs) == 1
    job = read_document(jobs[0])
    assert validate_request(job, job["id"])["action"] == action
    progress = f"/api/git/{provider}/" + job["id"]
    assert get(first, progress).json == {"state": "starting"}
    assert get(second, progress).status_code == 404
    payload = {
        "kind": "git_setup",
        "id": job["id"],
        "provider": provider,
        "generation": 3,
        "expires_at": time.time() + 300,
        "state": "waiting",
        "code": code,
        "access_token": "never-forward",
    }
    atomic_document(control / "pairings" / jobs[0].name, payload)
    response = get(first, progress)
    assert response.json == {"state": "waiting", "code": code}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert code not in get(first, "/api/status").text and code not in get(first, route).text
    snapshot = read_document(control / "status.json")
    snapshot["deployment"]["generation"] += 1
    atomic_document(control / "status.json", snapshot)
    assert get(first, progress).json == {"state": "expired"}


def test_host_forwards_only_human_code_and_resumes_native_signin(tmp_path, monkeypatch):
    calls = []
    private = []
    states = iter(
        [
            {"state": "waiting", "code": "ABCD-1234", "device_code": "private-fixture"},
            {"state": "authorized", "access_token": "private-fixture"},
        ]
    )

    class ScopedWorker:
        def __init__(self):
            self.cfg = {"runtime_id": 201, "manager_id": 202, "generation": 3}
            self.private = tmp_path
            self.control = tmp_path / "control"
            self.results = []

        def own_container(self, vmid, role="runtime"):
            assert (vmid, role) in {(201, "runtime"), (202, "manager")}

        def run(self, args, **_):
            calls.append(args)
            return json.dumps(next(states))

        def result(self, job, state, message):
            self.results.append((state, message))

    monkeypatch.setattr(forge, "publish_pairing", lambda _, value: private.append(value))
    worker = ScopedWorker()
    job = {
        "schema": 1,
        "id": secrets.token_hex(16),
        "action": "login_github",
        "version": None,
        "generation": 3,
        "restore_data": False,
        "created_at": utc_now(),
    }
    forge.start(worker, job)
    assert worker.results[-1][0] == "running"
    assert calls[0][-4:] == ["/opt/osm/forge.cjs", "start", "github", job["id"]]
    assert "orca" in calls[0] and "shell" not in calls[0]
    assert private_offer(private[0], "github", job["id"], 3) == {
        "state": "waiting",
        "code": "ABCD-1234",
    }
    forge.poll(worker)
    assert worker.results[-1][0] == "completed" and calls[-1][-3] == "read"
    assert not list((tmp_path / "git-setup").iterdir())
    assert "ABCD-1234" not in str(worker.results)
    assert "private-fixture" not in str(private) + str(worker.results)


@pytest.mark.parametrize(
    "value",
    [
        {"state": "waiting", "code": "secret-not-a-user-code"},
        {"state": "waiting", "code": 12345678},
        {"state": "key_ready", "public_key": "-----BEGIN OPENSSH PRIVATE KEY-----"},
        {"state": "approved"},
    ],
)
def test_unknown_or_secret_responses_are_never_published(value):
    with pytest.raises(ValueError):
        public_state("github", value)


def test_forgejo_returns_only_a_reusable_public_identity(tmp_path):
    module = Path(__file__).parents[1] / "container" / "forge.cjs"

    def prepare():
        r = subprocess.run(
            ["node", str(module), "start", "forgejo", secrets.token_hex(16)],
            env={**os.environ, "HOME": str(tmp_path)},
            capture_output=True,
            text=True,
            check=True,
        )
        assert not r.stderr
        return public_state("forgejo", json.loads(r.stdout))

    first = prepare()
    assert first == prepare()
    public = (tmp_path / ".ssh/id_ed25519.pub").read_text().split()
    assert first == {"state": "key_ready", "public_key": " ".join(public[:2])}
    assert (tmp_path / ".ssh/id_ed25519").stat().st_mode & 0o077 == 0


def test_native_login_completes_git_helper_before_reporting_success(tmp_path):
    module = Path(__file__).parents[1] / "container" / "forge.cjs"
    fake = tmp_path / "gh"
    fake.write_text("""#!/bin/sh
case "$2" in
  login) printf 'First copy your one-time code: ABCD-1234\ncredential-format-test-only\n' >&2
         while [ ! -f "$HOME/authorize-test" ]; do sleep 0.1; done ;;
  setup-git) touch "$HOME/credential-helper-called" ;;
  *) exit 1 ;;
esac
""")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "TMPDIR": str(tmp_path),
        "HOME": str(tmp_path),
        "PATH": str(tmp_path) + ":" + os.environ["PATH"],
    }
    job = secrets.token_hex(16)

    def call(verb):
        r = subprocess.run(
            ["node", str(module), verb, "github", job],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        assert not r.stderr and "credential-format-test-only" not in r.stdout
        return json.loads(r.stdout)

    try:
        assert call("start") == {"state": "waiting", "code": "ABCD-1234"}
    finally:
        (tmp_path / "authorize-test").touch()
    for _ in range(20):
        if call("read") == {"state": "authorized"}:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Native login did not complete")
    assert (tmp_path / "credential-helper-called").is_file()


def test_expired_grant_never_yields_a_code():
    with pytest.raises(ValueError):
        private_offer(
            {
                "kind": "git_setup",
                "provider": "github",
                "generation": 3,
                "id": "a" * 32,
                "state": "waiting",
                "code": "ABCD-1234",
                "expires_at": time.time() - LIFETIME,
            },
            "github",
            "a" * 32,
            3,
        )


def test_forgejo_rejects_a_link_in_place_of_a_public_key(tmp_path):
    ssh = tmp_path / ".ssh"
    ssh.mkdir(mode=0o700)
    (ssh / "id_ed25519").touch(mode=0o600)
    (ssh / "id_ed25519.pub").symlink_to(ssh / "id_ed25519")
    reply = subprocess.run(
        [
            "node",
            str(Path(__file__).parents[1] / "container/forge.cjs"),
            "start",
            "forgejo",
            secrets.token_hex(16),
        ],
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert reply.returncode != 0 and not reply.stdout


def test_corrupt_pending_native_login_does_not_block_the_worker(tmp_path):
    from types import SimpleNamespace

    directory = tmp_path / "git-setup"
    directory.mkdir()
    (directory / "gitlab.json").write_text("invalid")
    forge.poll(SimpleNamespace(private=tmp_path))
    assert (directory / "gitlab.invalid").is_file()
    assert not (directory / "gitlab.json").exists()


def test_revisiting_git_setup_keeps_the_return_to_orca_after_requesting_a_code(tmp_path):
    app, _ = manager_fixture(tmp_path)
    client = app.test_client()
    bootstrap(app, client)
    assert post(client, "/welcome/finish", {"csrf_token": csrf(client, "/")}).status_code == 303
    assert "Continue to Orca" not in get(client, "/git/github").text
    path = "/git/github?setup=1"
    assert "Continue to Orca" in get(client, path).text
    reply = post(client, "/git/github/start?setup=1", {"csrf_token": csrf(client, path)})
    assert reply.status_code == 303 and reply.location == path
    assert "Continue to Orca" in get(client, reply.location).text
    assert "Your Orca workspace" in get(client, "/").text


def test_old_image_guides_show_its_installed_agent_after_a_rollback(tmp_path):
    app, control = manager_fixture(tmp_path)
    client = app.test_client()
    bootstrap(app, client)
    snapshot = read_document(control / "status.json")
    snapshot["runtime"]["opencode_version"] = "1.19.5"
    atomic_document(control / "status.json", snapshot)
    assert "To use <strong>OpenCode</strong>" in get(client, "/welcome?step=launch").text
    snapshot["runtime"]["opencode_version"] = None
    atomic_document(control / "status.json", snapshot)
    assert "has not reported an installed OpenCode" in get(client, "/welcome?step=launch").text
