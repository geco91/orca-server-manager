import pytest

from manager.app import create_app
from manager.control import atomic_document, read_document, utc_now
from manager.opencode_releases import normalize_release, require_upgrade, resolve_release
from manager.releases import ReleaseError
from tests.test_manager import bootstrap, csrf, get, post
from tests.test_updates import controller_files


def upstream(tag="v1.19.6", digest="sha256:" + "a" * 64):
    return {
        "tag_name": tag,
        "name": "The upstream name",
        "prerelease": "-" in tag,
        "published_at": "2026-11-17T00:00:00Z",
        "assets": [
            {
                "name": "opencode-linux-x64.tar.gz",
                "digest": digest,
                "browser_download_url": "https://untrusted.invalid/download",
            }
        ],
    }


def test_official_opencode_metadata_preserves_labels_and_pins_the_source(monkeypatch):
    release = normalize_release(upstream("v1.20.0-beta.1"))
    assert release["prerelease"] and release["name"] == "The upstream name"
    assert not {"approved", "stable", "tested"} & release.keys()
    assert release["download_url"].startswith(
        "https://github.com/anomalyco/opencode/releases/download/"
    )
    assert not normalize_release(upstream(digest=None))["package_available"]
    assert normalize_release(upstream("android-v1")) is None
    seen = []

    def fetch(url):
        seen.append(url)
        return upstream()

    monkeypatch.setattr("manager.opencode_releases.read_json", fetch)
    assert resolve_release("1.19.6")["sha256"] == "a" * 64
    assert seen == ["https://api.github.com/repos/anomalyco/opencode/releases/tags/v1.19.6"]
    monkeypatch.setattr("manager.opencode_releases.read_json", lambda _: upstream(digest=None))
    with pytest.raises(ReleaseError):
        resolve_release("1.19.6")


@pytest.mark.parametrize(
    "version",
    [
        "1.19.4",
        "1.19.5",
        "1.19.5-beta.1",
        "../1.20.0",
        "latest",
        "1.20.0;id",
    ],
)
def test_opencode_upgrade_rejects_downgrades_and_non_versions(version):
    with pytest.raises(ReleaseError):
        require_upgrade(version, "1.19.5")


def catalog():
    return {
        "releases": [
            normalize_release(upstream("v" + version)) for version in ["1.19.4", "1.19.5", "1.19.6"]
        ],
        "page": 1,
        "has_more": False,
    }


def test_opencode_ui_checks_csrf_acknowledgement_and_shares_the_operation_lock(
    tmp_path, monkeypatch
):
    control = tmp_path / "control"
    controller_files(control)
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    )
    monkeypatch.setattr(
        "manager.app.list_releases", lambda *a: {"releases": [], "has_more": False, "page": 1}
    )
    monkeypatch.setattr("manager.app.list_opencode_releases", lambda *a: catalog())
    with app.test_client() as client:
        bootstrap(app, client)
        html = get(client, "/updates").text
        assert "OFFICIAL OPENCODE RELEASES" in html
        assert 'name="version" value="1.19.6"' in html
        assert 'name="version" value="1.19.4"' not in html
        assert 'name="version" value="1.19.5"' not in html
        assert "OpenCode 1.19.4" in html
        assert (
            post(
                client, "/actions/update-opencode", {"version": "1.19.6", "work_stopped": "1"}
            ).status_code
            == 400
        )
        token = csrf(client, "/updates")
        assert (
            post(
                client, "/actions/update-opencode", {"csrf_token": token, "version": "1.19.6"}
            ).status_code
            == 400
        )
        assert (
            post(
                client,
                "/actions/update-opencode",
                {"csrf_token": token, "version": "1.19.5", "work_stopped": "1"},
            ).status_code
            == 400
        )
        change = post(
            client,
            "/actions/update-opencode",
            {"csrf_token": token, "version": "1.19.6", "work_stopped": "1"},
        )
        assert change.status_code == 302
        same = post(
            client,
            "/actions/update",
            {"csrf_token": token, "version": "1.4.261", "work_stopped": "1"},
        )
        assert same.location == change.location
        assert len(list((control / "requests").iterdir())) == 1
        request = read_document(next((control / "requests").iterdir()))
        assert request["action"] == "update_opencode" and request["version"] == "1.19.6"
        assert get(client, "/api/status").json["runtime"]["opencode_version"] == "1.19.5"


def test_cached_opencode_catalog_is_filtered_against_the_live_version(tmp_path, monkeypatch):
    control = tmp_path / "control"
    controller_files(control)
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    )
    monkeypatch.setattr(
        "manager.app.list_releases", lambda *a: {"releases": [], "has_more": False, "page": 1}
    )
    monkeypatch.setattr("manager.app.list_opencode_releases", lambda *a: catalog())
    with app.test_client() as client:
        bootstrap(app, client)
        assert 'name="version" value="1.19.6"' in get(client, "/updates").text
        snapshot = read_document(control / "status.json")
        snapshot["runtime"]["opencode_version"] = "1.19.6"
        snapshot["observed_at"] = utc_now()
        atomic_document(control / "status.json", snapshot)
        assert 'name="version" value="1.19.6"' not in get(client, "/updates").text
