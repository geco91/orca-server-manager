import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from deploy.proxmox import notes

CODE = "test-only-setup-code-" + "a" * 32


@pytest.fixture
def manager_state(tmp_path, monkeypatch):
    parent = tmp_path / "manager"
    state = parent / "manager"
    state.mkdir(parents=True)
    parent.chmod(0o711)
    state.chmod(0o700)
    token = state / "bootstrap.token"
    token.write_text(CODE)
    token.chmod(0o600)
    original = os.fstat

    def mapped_stat(fd):
        # Model the standard PVE UID map without requiring root in CI.
        info = original(fd)
        path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        result = list(info)
        result[4] = 100000 if path == parent else 101000
        return os.stat_result(result)

    monkeypatch.setattr(notes.os, "fstat", mapped_stat)
    return tmp_path, token


def test_setup_code_is_read_privately_and_missing_code_is_not_recreated(manager_state):
    data, token = manager_state
    assert notes.read_setup_code(data) == CODE
    token.unlink()
    assert notes.read_setup_code(data) is None
    assert not token.exists()


@pytest.mark.parametrize("replacement", ["symlink", "hardlink", "public", "oversized", "format"])
def test_guest_controlled_setup_file_cannot_expose_another_host_file(manager_state, replacement):
    data, token = manager_state
    if replacement == "symlink":
        token.unlink()
        token.symlink_to("/etc/passwd")
    elif replacement == "hardlink":
        os.link(token, token.with_name("another-link"))
    elif replacement == "public":
        token.chmod(0o644)
    elif replacement == "oversized":
        token.write_text("a" * 129)
    else:
        token.write_text("not a setup code")
    with pytest.raises(notes.SetupNotesError):
        notes.read_setup_code(data)


def test_guest_controlled_state_directory_symlink_is_rejected(manager_state):
    data, token = manager_state
    state = token.parent
    state.rename(state.with_name("moved"))
    state.symlink_to(state.with_name("moved"), target_is_directory=True)
    with pytest.raises(notes.SetupNotesError):
        notes.read_setup_code(data)


def test_notes_keep_the_marker_and_operator_text_then_remove_the_consumed_code():
    existing = "OSM:pilot:manager\n\nOperator note: reserve the DHCP lease.\n"
    pending = notes.setup_description(existing, "pilot", CODE)
    assert "OSM:pilot:manager" in pending.splitlines()
    assert "Operator note: reserve the DHCP lease." in pending
    assert pending.count(CODE) == 1
    assert notes.setup_description(pending, "pilot", CODE) == pending
    completed = notes.setup_description(pending, "pilot", None)
    assert CODE not in completed
    assert "Operator note: reserve the DHCP lease." in completed
    assert notes.setup_description(completed, "pilot", None) == completed
    with pytest.raises(notes.SetupNotesError):
        notes.setup_description("OSM:other:manager", "pilot", CODE)


def test_sync_uses_private_stdin_and_clears_notes_after_bootstrap(
    manager_state, monkeypatch, capsys
):
    data, token = manager_state
    current = "OSM:pilot:manager"
    writes = []

    def native(args, **kwargs):
        nonlocal current
        assert CODE not in str(args)
        if args[0] == "pct":
            return SimpleNamespace(returncode=0, stdout="description: " + quote(current, safe=""))
        assert args[0] == "perl"
        payload = json.loads(kwargs["input"])
        assert payload["id"] == 104
        assert payload["expected"] == current
        current = payload["description"]
        writes.append(current)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(notes.subprocess, "run", native)
    cfg = {"data": str(data), "manager_id": 104, "installation": "pilot"}
    notes.sync_setup_notes(cfg)
    notes.sync_setup_notes(cfg)
    assert len(writes) == 1 and CODE in current
    token.unlink()
    notes.sync_setup_notes(cfg)
    assert len(writes) == 2 and CODE not in current
    assert capsys.readouterr() == ("", "")


def test_native_error_never_returns_private_notes(manager_state, monkeypatch):
    data, _ = manager_state
    monkeypatch.setattr(
        notes.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=CODE, stderr=CODE),
    )
    with pytest.raises(notes.SetupNotesError) as error:
        notes.sync_setup_notes({"data": str(data), "manager_id": 104, "installation": "pilot"})
    assert CODE not in str(error.value)
