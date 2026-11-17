import pytest

from manager.app import create_app
from manager.control import ControlError, atomic_document, read_document, utc_now
from manager.releases import ReleaseError, require_upgrade, upgrades_only
from tests.test_manager import bootstrap, csrf, get, post
from tests.test_updates import controller_files, normalize_release, release_item


@pytest.mark.parametrize(
    "older,newer",
    [
        ("1.4.9", "1.4.10"),
        ("1.9.99", "1.10.0"),
        ("1.99.99", "2.0.0"),
        ("1.5.0-beta.2", "1.5.0-beta.10"),
        ("1.5.0-beta.10", "1.5.0"),
        ("1.5.0-alpha.1", "1.5.0-beta.1"),
        ("1.5.0-beta", "1.5.0-beta.1"),
    ],
)
def test_upgrade_order_respects_numeric_versions_and_native_prereleases(older, newer):
    require_upgrade(newer, older)
    for candidate, installed in [(older, newer), (older, older)]:
        with pytest.raises(ReleaseError):
            require_upgrade(candidate, installed)


def test_release_catalog_contains_only_upgrades_and_cannot_be_mutated_by_filtering():
    releases = [
        normalize_release(release_item("v" + version))
        for version in ("1.4.258", "1.4.259", "1.4.260")
    ]
    catalog = {"releases": releases, "has_more": True, "page": 1}
    assert [r["version"] for r in upgrades_only(catalog, "1.4.259")["releases"]] == ["1.4.260"]
    assert upgrades_only(catalog, "1.4.260")["has_more"] is False
    assert len(catalog["releases"]) == 3


def test_cached_releases_are_refiltered_when_the_installed_version_changes(tmp_path, monkeypatch):
    control = tmp_path / "control"
    controller_files(control)
    state = tmp_path / "state"
    app = create_app({"TESTING": True, "STATE_DIR": str(state), "CONTROL_DIR": str(control)})
    monkeypatch.setattr(
        "manager.app.list_releases",
        lambda *args: {
            "releases": [
                normalize_release(release_item("v1.4.258")),
                normalize_release(release_item("v1.4.259")),
                normalize_release(release_item("v1.4.260")),
            ],
            "has_more": True,
            "page": 1,
        },
    )
    with app.test_client() as client:
        bootstrap(app, client)
        html = get(client, "/updates").text
        assert 'name="version" value="1.4.260"' in html
        assert 'name="version" value="1.4.259"' not in html
        assert 'name="version" value="1.4.258"' not in html
        snapshot = read_document(control / "status.json")
        snapshot["deployment"]["version"] = "1.4.260"
        atomic_document(control / "status.json", snapshot | {"observed_at": utc_now()})
        html = get(client, "/updates").text
        assert 'name="version" value=' not in html
        assert "No newer Orca releases" in html and "More upgrades" not in html


def test_forged_downgrade_request_never_reaches_the_queue_and_missing_rollback_is_unavailable(
    tmp_path,
):
    control = tmp_path / "control"
    controller = controller_files(control)
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    )
    with app.test_client() as client:
        bootstrap(app, client)
        for version in ("1.4.258", "1.4.259"):
            response = post(
                client,
                "/actions/update",
                {"csrf_token": csrf(client, "/"), "version": version, "work_stopped": "1"},
            )
            assert response.status_code == 400
        assert not list((control / "requests").iterdir())
        snapshot = read_document(control / "status.json")
        snapshot["deployment"].pop("previous_version")
        atomic_document(control / "status.json", snapshot)
        with pytest.raises(ControlError, match="no saved previous"):
            controller.submit("rollback")
        assert not list((control / "requests").iterdir())
