import os
from datetime import UTC, datetime, timedelta

import pytest

from manager.app import create_app
from manager.control import ControlError, Controller, atomic_document, read_document, utc_now
from manager.releases import ReleaseError, normalize_release, resolve_release, validate_version
from tests.test_manager import bootstrap, csrf, get, post


def release_item(tag="v1.4.261", prerelease=False, digest="sha256:" + "a" * 64):
    return {
        "tag_name": tag,
        "name": "Orca's own label",
        "prerelease": prerelease,
        "published_at": "2026-11-16T00:00:00Z",
        "assets": [
            {
                "name": "orca-server-linux-x64.tar.gz",
                "digest": digest,
                "browser_download_url": "https://untrusted.example/archive",
            }
        ],
    }


def controller_files(path):
    path.mkdir()
    (path / "requests").mkdir()
    (path / "results").mkdir()
    atomic_document(
        path / "status.json",
        {
            "schema": 1,
            "observed_at": utc_now(),
            "runtime": {
                "reachable": True,
                "version": "1.4.259",
                "opencode_version": "1.19.5",
                "active_terminals": 0,
            },
            "integrations": {"github": {"state": "partial", "label": "Not signed in"}},
            "deployment": {
                "version": "1.4.259",
                "runtime_id": 201,
                "generation": 3,
                "previous_version": "1.4.258",
                "opencode_version": "1.19.5",
                "previous_opencode_version": "1.19.4",
                "backup_at": utc_now(),
            },
        },
    )
    return Controller(path)


def test_release_metadata_preserves_upstream_labels_without_local_ratings():
    result = normalize_release(release_item("v1.5.0-beta.1", True))
    assert result["prerelease"] is True
    assert result["name"] == "Orca's own label"
    assert result["server_available"]
    assert result["download_url"].startswith("https://github.com/stablyai/orca/releases/download/")
    assert not {"approved", "stable", "tested"} & result.keys()
    assert normalize_release(release_item("android-v1")) is None
    draft = release_item()
    draft["draft"] = True
    assert normalize_release(draft) is None
    assert not normalize_release(release_item(digest=None))["server_available"]
    assert not normalize_release(release_item(), "arm64")["server_available"]
    with_web = release_item()
    with_web["assets"].append(
        {"name": "orca-ide_1.4.261_amd64.deb", "digest": "sha256:" + "b" * 64}
    )
    assert normalize_release(with_web)["web_sha256"] == "b" * 64
    with_web["assets"][-1]["name"] = "orca-ide_1.4.258_amd64.deb"
    assert normalize_release(with_web)["web_sha256"] is None


@pytest.mark.parametrize("value", ["latest", "../1.4.261", "1.4.261;id", "1.4.261\n", None])
def test_version_cannot_select_an_arbitrary_source_or_shell_command(value):
    with pytest.raises(ReleaseError):
        validate_version(value)


def test_release_resolution_uses_exact_official_tag_and_requires_published_checksum(monkeypatch):
    seen = []

    def fetch(url):
        seen.append(url)
        return release_item()

    monkeypatch.setattr("manager.releases.read_json", fetch)
    assert resolve_release("1.4.261")["sha256"] == "a" * 64
    assert seen == ["https://api.github.com/repos/stablyai/orca/releases/tags/v1.4.261"]
    monkeypatch.setattr("manager.releases.read_json", lambda _: release_item(digest=None))
    with pytest.raises(ReleaseError):
        resolve_release("1.4.261")


def test_queue_fences_generation_and_does_not_run_commands(tmp_path):
    controller = controller_files(tmp_path / "control")
    job = controller.submit("update", "1.4.261")
    assert job["generation"] == 3
    assert read_document(tmp_path / "control/requests" / f"{job['id']}.json") == job
    assert controller.result(job["id"])["state"] == "queued"
    assert (
        oct((tmp_path / "control/requests" / f"{job['id']}.json").stat().st_mode & 0o777) == "0o600"
    )
    for action in ["exec", "shell", "delete"]:
        with pytest.raises(ControlError):
            controller.submit(action)


def test_stale_or_malformed_observations_never_enable_operations(tmp_path):
    controller = controller_files(tmp_path / "control")
    path = tmp_path / "control/status.json"
    snapshot = read_document(path)
    snapshot["observed_at"] = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()
    atomic_document(path, snapshot)
    assert not controller.snapshot()["controller"]["available"]
    with pytest.raises(ControlError):
        controller.submit("rollback", restore_data=True)
    snapshot.update(observed_at=utc_now(), runtime=[])
    atomic_document(path, snapshot)
    assert not controller.snapshot()["controller"]["available"]
    assert not list((tmp_path / "control/requests").iterdir())


def test_file_protocol_rejects_links_fifos_and_oversized_documents(tmp_path):
    secret = tmp_path / "private"
    secret.write_text('{"credential":"never return this"}')
    linked = tmp_path / "linked"
    linked.symlink_to(secret)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    large = tmp_path / "large"
    large.write_bytes(b"x" * (128 * 1024 + 1))
    for path in [linked, fifo, large]:
        with pytest.raises(ControlError):
            read_document(path)


def test_versions_ui_queues_one_operation_and_requires_explicit_rollback_scope(
    tmp_path, monkeypatch
):
    control = tmp_path / "control"
    controller = controller_files(control)
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    )
    monkeypatch.setattr(
        "manager.app.list_releases",
        lambda *a: {
            "releases": [
                normalize_release(release_item()),
                normalize_release(release_item("v1.5.0-beta.1", True)),
            ],
            "page": 1,
            "has_more": True,
        },
    )
    with app.test_client() as client:
        bootstrap(app, client)
        html = get(client, "/updates").text
        assert "1.5.0-beta.1" in html and "Pre-release" in html
        assert "discards changes made since the backup" in html
        assert "More upgrades" in html
        assert "pct exec 201" in get(client, "/connections/providers").text
        token = csrf(client, "/updates")
        assert post(client, "/actions/rollback", {"csrf_token": token}).status_code == 400
        assert (
            post(client, "/actions/update", {"csrf_token": token, "version": "1.4.261"}).status_code
            == 400
        )
        change = post(
            client,
            "/actions/update",
            {"csrf_token": token, "version": "1.4.261", "work_stopped": "1"},
        )
        assert change.status_code == 302
        repeated = post(
            client,
            "/actions/update",
            {"csrf_token": token, "version": "1.5.0-beta.1", "work_stopped": "1"},
        )
        assert repeated.location == change.location
        assert len(list((control / "requests").iterdir())) == 1
        job_id = change.location.rsplit("/", 1)[1]
        atomic_document(
            control / "results" / f"{job_id}.json",
            {"id": job_id, "state": "failed", "message": "Startup failed"},
        )
        assert "Startup failed" in get(client, change.location).text
        rollback = post(
            client, "/actions/rollback", {"csrf_token": token, "mode": "data", "work_stopped": "1"}
        )
        assert rollback.status_code == 302
        new_id = rollback.location.rsplit("/", 1)[1]
        request = read_document(control / "requests" / f"{new_id}.json")
        assert request["restore_data"] is True
        assert controller.result(new_id)["state"] == "queued"


def test_release_outage_keeps_cached_metadata_and_no_controller_never_suggests_success(
    tmp_path, monkeypatch
):
    app = create_app({"TESTING": True, "STATE_DIR": str(tmp_path)})
    data = {"releases": [normalize_release(release_item())], "page": 1, "has_more": False}
    atomic_document(tmp_path / "releases-1.json", {"fetched_at": 1, "data": data})

    def unavailable(*_):
        raise ReleaseError("Official Orca release metadata is currently unavailable.")

    monkeypatch.setattr("manager.app.list_releases", unavailable)
    with app.test_client() as client:
        bootstrap(app, client)
        response = get(client, "/updates")
        assert response.status_code == 200
        assert "installed version is not known" in response.text
        assert 'name="version" value="1.4.261"' not in response.text
        assert "No version change can be started" in response.text


def test_explicit_observation_mode_survives_a_private_worker_umask(tmp_path):
    prior = os.umask(0o077)
    try:
        public = tmp_path / "status.json"
        private = tmp_path / "request.json"
        atomic_document(public, {"runtime": "sanitized"}, mode=0o644)
        atomic_document(private, {"operation": "private"})
        assert public.stat().st_mode & 0o777 == 0o644
        assert private.stat().st_mode & 0o777 == 0o600
    finally:
        os.umask(prior)
