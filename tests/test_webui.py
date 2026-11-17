import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

from manager.app import create_app
from manager.control import atomic_document, read_document
from manager.links import public_web_url
from manager.proxy import proxy_environment, proxy_target
from tests.test_manager import bootstrap, get
from tests.test_updates import controller_files

spec = importlib.util.spec_from_file_location(
    "fetch_web", Path(__file__).parents[1] / "scripts/fetch-web.py"
)
fetch_web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_web)


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "https://user:password@example.com/",
        "https://example.com/#pairing=secret",
        "https://example.com/?token=secret",
        "https://example.com:99999/",
        "https://example.com/\n",
        "//example.com/",
        "http://example.com\\evil/",
        None,
    ],
)
def test_web_links_cannot_carry_scripts_or_pairing_credentials(value):
    assert public_web_url(value) == ""


def test_overview_exposes_the_native_webui_in_new_tabs_via_the_existing_https_origin(tmp_path):
    control = tmp_path / "control"
    controller_files(control)
    snapshot = read_document(control / "status.json")
    snapshot["runtime"]["web_url"] = "http://192.168.50.25:6768/web-index.html"
    atomic_document(control / "status.json", snapshot)
    app = create_app(
        {"TESTING": True, "STATE_DIR": str(tmp_path / "state"), "CONTROL_DIR": str(control)}
    )
    with app.test_client() as client:
        bootstrap(app, client)
        html = get(client, "/overview").text
        assert html.count('action="/actions/web-pairing" target="_blank" rel="noopener"') == 1
        assert 'href="/web-ui"' in html
        assert "Open Orca WebUI" in html
        assert "192.168.50.25" not in html
    assert proxy_target(control) == "192.168.50.25:6768"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:6768/web-index.html",
        "http://8.8.8.8:6768/web-index.html",
        "http://192.168.50.25:8006/web-index.html",
        "http://192.168.50.25:6768/other",
        "https://192.168.50.25:6768/web-index.html",
        "http://example.com:6768/web-index.html",
    ],
)
def test_runtime_status_cannot_turn_caddy_into_an_arbitrary_proxy(tmp_path, url):
    atomic_document(tmp_path / "status.json", {"runtime": {"web_url": url}})
    assert proxy_target(tmp_path) is None
    assert proxy_target(tmp_path, "runtime:6768") == "runtime:6768"


def test_only_the_assigned_runtime_bypasses_the_environment_proxy():
    original = {
        "HTTP_PROXY": "http://proxy.example",
        "NO_PROXY": "localhost",
        "no_proxy": "127.0.0.1",
    }
    result = proxy_environment(original, "runtime:6768")
    assert result["HTTP_PROXY"] == original["HTTP_PROXY"]
    assert result["NO_PROXY"] == result["no_proxy"] == "localhost,127.0.0.1,runtime"
    assert original["NO_PROXY"] == "localhost"


def bundle(members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, data, link in members:
            entry = tarfile.TarInfo("./" + fetch_web.PREFIX + name)
            if link:
                entry.type = tarfile.SYMTYPE
                entry.linkname = link
                archive.addfile(entry)
            else:
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
    output.seek(0)
    return tarfile.open(fileobj=output, mode="r|")


def test_only_manifest_listed_browser_files_are_extracted_without_the_desktop_application(tmp_path):
    raw = json.dumps(["web-index.html", "assets/browser.js"]).encode()
    members = [
        (fetch_web.MANIFEST, raw, None),
        ("web-index.html", b"<html>Orca</html>", None),
        ("assets/browser.js", b"native browser", None),
        ("assets/desktop-only.js", b"desktop", None),
    ]
    with bundle(members) as source:
        manifest, files = fetch_web.browser_manifest(source)
    with bundle(members) as source:
        fetch_web.extract_browser(source, manifest, files, tmp_path)
    assert (tmp_path / "assets/browser.js").read_text() == "native browser"
    assert not (tmp_path / "assets/desktop-only.js").exists()
    assert (tmp_path / fetch_web.MANIFEST).read_bytes() == raw


@pytest.mark.parametrize(
    "name", ["assets/../private", "/web-index.html", "assets/a.map", "assets\\evil", "assets//evil"]
)
def test_web_manifest_cannot_expand_the_native_static_file_boundary(name):
    with pytest.raises(ValueError):
        fetch_web.web_files(json.dumps(["web-index.html", name]))


def test_original_browser_asset_symlinks_and_incomplete_bundles_are_rejected(tmp_path):
    raw = b'["web-index.html"]'
    for members in [[], [("web-index.html", b"", "/etc/passwd")]]:
        with bundle(members) as source, pytest.raises(ValueError):
            fetch_web.extract_browser(source, raw, fetch_web.web_files(raw), tmp_path)


def test_browser_download_checksum_is_checked_before_any_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fetch_web, "urlopen", lambda *args, **kwargs: io.BytesIO(b"tampered package")
    )
    destination = tmp_path / "web"
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch_web.install("1.4.261", "x64", "a" * 64, destination)
    assert not destination.exists()
