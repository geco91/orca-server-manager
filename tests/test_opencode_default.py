import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / "container/opencode-default.cjs"


@pytest.fixture
def native_settings(tmp_path):
    with tempfile.TemporaryDirectory(prefix="osm-settings-") as directory:
        root = Path(directory)
        listener = socket.socket(socket.AF_UNIX)
        endpoint = root / "rpc.sock"
        listener.bind(str(endpoint))
        listener.listen()
        listener.settimeout(0.1)
        metadata = tmp_path / "orca-runtime.json"
        metadata.write_text(
            json.dumps(
                {
                    "runtimeId": "test-runtime",
                    "authToken": "unit-only-private-token",
                    "transports": [{"kind": "unix", "endpoint": str(endpoint)}],
                }
            )
        )
        metadata.chmod(0o600)
        state = {
            "settings": {"defaultTuiAgent": None, "unrelated": "preserve-me"},
            "runtime_id": "test-runtime",
            "calls": [],
            "errors": [],
        }
        stop = threading.Event()

        def serve():
            while not stop.is_set():
                try:
                    client, _ = listener.accept()
                except TimeoutError:
                    continue
                with client, client.makefile("rwb") as stream:
                    try:
                        request = json.loads(stream.readline(128 * 1024))
                        assert request["authToken"] == "unit-only-private-token"
                        state["calls"].append(request["method"])
                        if request["method"] == "settings.update":
                            assert request["params"] == {"defaultTuiAgent": "opencode"}
                            state["settings"].update(request["params"])
                        else:
                            assert request["method"] == "settings.get"
                        stream.write(
                            json.dumps(
                                {
                                    "id": request["id"],
                                    "ok": True,
                                    "result": {"settings": state["settings"]},
                                    "_meta": {"runtimeId": state["runtime_id"]},
                                }
                            ).encode()
                            + b"\n"
                        )
                        stream.flush()
                    except (AssertionError, ValueError, OSError) as error:
                        state["errors"].append(type(error).__name__)

        thread = threading.Thread(target=serve)
        thread.start()
        yield tmp_path, metadata, state
        stop.set()
        thread.join(timeout=2)
        listener.close()
        assert not thread.is_alive() and not state["errors"]


def configure(data, executable=None):
    node = shutil.which("node")
    assert node, "Native configuration checks require Node.js."
    environment = dict(
        os.environ,
        OSM_TEST_DATA=str(data),
        OSM_TEST_EXECUTABLE=str(executable or node),
        OSM_TEST_MODULE=str(MODULE),
    )
    result = subprocess.run(
        [
            node,
            "-e",
            (
                "const {configure}=require(process.env.OSM_TEST_MODULE);"
                "configure({userData:process.env.OSM_TEST_DATA,executable:process.env.OSM_TEST_EXECUTABLE,"
                "timeout:800}).then(result=>console.log(JSON.stringify(result)))"
                ".catch(()=>{process.exitCode=1});"
            ),
        ],
        check=False,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert "unit-only-private-token" not in result.stdout + result.stderr
    return result


def test_unselected_native_host_gets_opencode_without_other_settings_changes(native_settings):
    data, _, state = native_settings
    result = configure(data)
    assert result.returncode == 0 and json.loads(result.stdout)["state"] == "configured"
    assert state["settings"] == {"defaultTuiAgent": "opencode", "unrelated": "preserve-me"}
    assert state["calls"] == ["settings.get", "settings.update"]
    assert (data / ".osm-opencode-default.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("selected", ["codex", "blank", "opencode"])
def test_native_user_selection_is_preserved(native_settings, selected):
    data, _, state = native_settings
    state["settings"]["defaultTuiAgent"] = selected
    result = configure(data)
    assert result.returncode == 0 and json.loads(result.stdout)["state"] == "preserved"
    assert state["settings"]["defaultTuiAgent"] == selected
    assert state["calls"] == ["settings.get"]


def test_restart_does_not_reapply_a_default_the_operator_later_cleared(native_settings):
    data, _, state = native_settings
    assert configure(data).returncode == 0
    state["settings"]["defaultTuiAgent"] = None
    before = list(state["calls"])
    assert configure(data).returncode == 0
    assert state["settings"]["defaultTuiAgent"] is None and state["calls"] == before


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "public"])
def test_private_runtime_metadata_cannot_be_replaced_with_an_unsafe_file(native_settings, unsafe):
    data, metadata, state = native_settings
    if unsafe == "public":
        metadata.chmod(0o644)
    elif unsafe == "hardlink":
        os.link(metadata, metadata.with_name("another-link"))
    else:
        saved = metadata.with_name("original.json")
        metadata.rename(saved)
        metadata.symlink_to(saved)
    assert configure(data).returncode == 1
    assert not state["calls"] and not (data / ".osm-opencode-default.json").exists()


def test_another_runtime_cannot_acknowledge_the_native_preference_change(native_settings):
    data, _, state = native_settings
    state["runtime_id"] = "different-runtime"
    assert configure(data).returncode == 1
    assert "settings.update" not in state["calls"]
    assert not (data / ".osm-opencode-default.json").exists()


def test_missing_provider_cli_does_not_change_the_native_host(native_settings):
    data, _, state = native_settings
    assert configure(data, data / "not-installed").returncode == 1
    assert not state["calls"] and not (data / ".osm-opencode-default.json").exists()
