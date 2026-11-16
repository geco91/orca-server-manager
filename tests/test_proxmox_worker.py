import json
import subprocess
from pathlib import Path

import pytest

from deploy.proxmox.install import plan
from deploy.proxmox.worker import DeploymentError, Worker, validate_request
from manager.control import atomic_document, read_document, utc_now


class PVE:
    """Small native-tool simulator; filesystem backup/restore still runs real cp/rename."""

    def __init__(self):
        self.commands = []
        self.running = {201: True}
        self.terminals = 0
        self.fail_start = set()
        self.backup_fails = False
        self.on_create = None
        self.owned = True

    def __call__(self, args, **_):
        self.commands.append(args)
        if args[:2] == ["pct", "config"]:
            return "description: OSM:pilot:runtime\n" if self.owned else "description: unrelated\n"
        if args[:2] == ["qm", "config"]:
            return "description: unrelated builder\n"
        if args[:2] == ["pvesh", "get"]:
            return "203\n"
        if args[:2] == ["pct", "status"]:
            return "status: " + ("running" if self.running[int(args[2])] else "stopped")
        if args[:2] == ["pct", "exec"]:
            return json.dumps(
                {
                    "schema": 1,
                    "runtime": {
                        "reachable": True,
                        "version": "1.4.261",
                        "active_terminals": self.terminals,
                    },
                    "integrations": {},
                }
            )
        if args[:2] == ["pct", "create"]:
            self.running[int(args[2])] = False
            if self.on_create:
                self.on_create()
        if args[:2] == ["pct", "shutdown"]:
            self.running[int(args[2])] = False
        if args[:2] == ["pct", "start"]:
            if int(args[2]) in self.fail_start:
                raise DeploymentError("pct failed with exit code 1.")
            self.running[int(args[2])] = True
        if args[0] == "cp":
            if self.backup_fails:
                raise DeploymentError("cp failed with exit code 1.")
            subprocess.run(args, check=True)
        return ""


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    cfg = {
        "installation": "pilot",
        "base": str(tmp_path / "base"),
        "data": str(tmp_path / "data"),
        "runtime_id": 201,
        "manager_id": 202,
        "builder_id": 200,
        "storage": "local-lvm",
        "bridge": "vmbr0",
        "runtime_mac": "02:00:00:00:00:01",
        "version": "1.4.259",
        "generation": 2,
        "builder_alias": "existing-builder",
        "builder_checkout": "/srv/orca-server-manager",
        "builder_output": "/srv/orca-oci",
    }
    pve = PVE()
    worker = Worker(cfg, tmp_path / "deployment.json", command=pve)
    for path in [worker.base, worker.results, worker.requests, worker.home, worker.workspaces]:
        path.mkdir(parents=True, exist_ok=True)
    (worker.home / "profile").write_text("before-update")
    (worker.workspaces / "work").write_text("before-update")
    archive = tmp_path / "runtime.oci.tar"
    archive.write_bytes(b"disposable image fixture")
    archive.chmod(0o600)
    monkeypatch.setattr(worker, "build", lambda version: archive)
    monkeypatch.setattr("deploy.proxmox.worker.os.chown", lambda *_: None)
    return worker, pve


def job(action="update", restore=False, generation=2):
    return {
        "schema": 1,
        "id": "a" * 32 if action == "update" else "b" * 32,
        "action": action,
        "version": "1.4.261" if action == "update" else None,
        "restore_data": restore,
        "created_at": utc_now(),
        "generation": generation,
    }


def outcome(worker, request):
    return read_document(worker.results / f"{request['id']}.json")["state"]


def test_native_plan_is_read_only_and_separates_the_manager(deployment, tmp_path):
    worker, pve = deployment
    proposed = plan(worker.cfg, tmp_path / "archives")
    assert not pve.commands
    commands = proposed["commands"]
    assert commands[0][2] == "201" and commands[1][2] == "202"
    for command in commands[:2]:
        assert command[command.index("--unprivileged") + 1] == "1"
        assert "--force" not in command
        assert "--features" not in command
    assert "/control" in " ".join(commands[1])
    assert "/private/runtime-data/home" in " ".join(commands[0])
    assert "/private/runtime-data/home" not in " ".join(commands[1])
    assert proposed["builder"]["create"] is False


def test_generation_fence_prevents_a_delayed_request_from_changing_the_runtime(deployment):
    worker, pve = deployment
    request = job(generation=1)
    worker.execute(request)
    assert outcome(worker, request) == "blocked"
    assert not pve.commands


@pytest.mark.parametrize("count", [1, None])
def test_active_or_unknown_terminals_block_before_any_container_change(deployment, count):
    worker, pve = deployment
    pve.terminals = count
    request = job()
    worker.execute(request)
    assert outcome(worker, request) == "failed"
    assert not any(args[:2] in [["pct", "create"], ["pct", "shutdown"]] for args in pve.commands)
    assert pve.running[201]


def test_native_activity_is_rechecked_after_image_preparation(deployment):
    worker, pve = deployment
    pve.on_create = lambda: setattr(pve, "terminals", 1)
    request = job()
    worker.execute(request)
    assert outcome(worker, request) == "failed"
    assert pve.running[201] and not pve.running[203]
    assert "pending" not in worker.cfg
    assert 203 in worker.cfg["retained_containers"]
    assert not any(args[:2] == ["pct", "shutdown"] for args in pve.commands)


def test_update_preserves_stopped_software_and_a_consistent_data_copy(deployment):
    worker, pve = deployment
    request = job()
    worker.execute(request)
    assert outcome(worker, request) == "completed"
    assert worker.cfg["version"] == "1.4.261" and worker.cfg["runtime_id"] == 203
    assert worker.cfg["generation"] == 3
    assert worker.cfg["previous"]["id"] == 201
    assert not pve.running[201] and pve.running[203]
    saved = Path(worker.cfg["previous"]["backup"]) / "data"
    assert (saved / "home/profile").read_text() == "before-update"
    assert (saved / "workspaces/work").read_text() == "before-update"
    shutdown = next(i for i, args in enumerate(pve.commands) if args[:2] == ["pct", "shutdown"])
    backup = next(i for i, args in enumerate(pve.commands) if args[0] == "cp")
    start = next(i for i, args in enumerate(pve.commands) if args[:2] == ["pct", "start"])
    assert shutdown < backup < start
    assert not any("destroy" in args for args in pve.commands)


@pytest.mark.parametrize("restore", [False, True])
def test_rollback_software_and_data_policies_have_different_effects(deployment, restore):
    worker, pve = deployment
    worker.execute(job())
    (worker.home / "profile").write_text("new-profile")
    (worker.workspaces / "work").write_text("new-work")
    request = job("rollback", restore, generation=3)
    worker.execute(request)
    assert outcome(worker, request) == "completed"
    assert pve.running[201] and not pve.running[203]
    assert worker.cfg["version"] == "1.4.259"
    assert (worker.home / "profile").read_text() == ("before-update" if restore else "new-profile")
    assert (worker.workspaces / "work").read_text() == ("before-update" if restore else "new-work")
    if restore:
        retired = worker.private / "retired-data" / request["id"] / "data/workspaces/work"
        assert retired.read_text() == "new-work"


def test_a_failed_new_start_keeps_the_return_path_and_allows_rollback(deployment):
    worker, pve = deployment
    pve.fail_start.add(203)
    update = job()
    worker.execute(update)
    assert outcome(worker, update) == "failed"
    assert worker.cfg["previous"]["id"] == 201
    assert Path(worker.cfg["previous"]["backup"]).is_dir()
    rollback = job("rollback", True, generation=3)
    worker.execute(rollback)
    assert outcome(worker, rollback) == "completed"
    assert pve.running[201]


def test_failed_backup_restarts_the_unchanged_old_runtime(deployment):
    worker, pve = deployment
    pve.backup_fails = True
    request = job()
    worker.execute(request)
    assert outcome(worker, request) == "failed"
    assert worker.cfg["runtime_id"] == 201 and pve.running[201]
    assert not pve.running[203]
    assert "previous" not in worker.cfg and "pending" not in worker.cfg
    assert (worker.workspaces / "work").read_text() == "before-update"


def test_scope_markers_prevent_mutating_an_unrelated_container_or_builder(deployment, monkeypatch):
    worker, pve = deployment
    pve.owned = False
    with pytest.raises(DeploymentError):
        worker.stop(201)
    with pytest.raises(DeploymentError):
        worker.own_builder()
    assert not any(args[1] in {"start", "shutdown"} for args in pve.commands)


def test_an_interrupted_request_is_recorded_without_replaying_it(deployment):
    worker, pve = deployment
    worker.inflight.mkdir(parents=True)
    request = job()
    atomic_document(worker.inflight / f"{request['id']}.json", request)
    worker.result(request, "running", "Preparing image")
    worker.tick()
    assert outcome(worker, request) == "interrupted"
    assert not any(args[:2] == ["pct", "create"] for args in pve.commands)


def test_interrupted_data_swap_restores_a_complete_directory_group(deployment):
    worker, _ = deployment
    request = job("rollback", True)
    staged = worker.private / "restore" / request["id"]
    staged.mkdir(parents=True)
    worker.runtime_data.rename(staged / "data")
    worker.cfg["pending"] = {"job": request["id"], "phase": "swapping-data"}
    worker.repair_interrupted_data_swap()
    assert (worker.home / "profile").read_text() == "before-update"
    assert (worker.workspaces / "work").read_text() == "before-update"
    assert worker.cfg["pending"]["phase"] == "rollback-interrupted"


@pytest.mark.parametrize(
    "extra", [{"command": "id"}, {"action": "shell"}, {"generation": True}, {"version": "latest"}]
)
def test_untrusted_queue_cannot_expand_the_scoped_protocol(extra):
    document = job() | extra
    with pytest.raises(ValueError):
        validate_request(document, document["id"])


def test_missing_data_mount_stops_the_host_worker_before_writes(deployment, monkeypatch):
    from deploy.proxmox import worker as module

    worker, pve = deployment
    original = Path.is_dir
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        Path, "is_dir", lambda path: True if str(path) == "/etc/pve" else original(path)
    )
    monkeypatch.setattr(module, "load_config", lambda _: worker.cfg)
    monkeypatch.setattr(module.sys, "argv", ["worker.py", "--config", str(worker.config_path)])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    assert not worker.inflight.exists()
    assert not pve.commands


def test_native_percent_encoded_description_preserves_exact_scope_marker():
    assert Worker.has_marker("description: OSM%3Apilot%3Abuilder%0Anotes", "OSM:pilot:builder")
    assert Worker.has_marker("description: OSM:pilot:runtime", "OSM:pilot:runtime")
    assert not Worker.has_marker("description: OSM%3Apilot%3Aruntime-other", "OSM:pilot:runtime")


def test_native_import_stages_only_an_image_and_removes_it_after_failure(
    deployment, tmp_path, monkeypatch
):
    worker, _ = deployment
    archive = tmp_path / "private-image.tar"
    archive.write_bytes(b"verified image bytes")
    archive.chmod(0o600)
    owners = []
    monkeypatch.setattr(
        "deploy.proxmox.worker.os.chown", lambda path, uid, gid: owners.append((uid, gid))
    )
    with pytest.raises(DeploymentError), worker.import_archive(archive) as staged:
        assert staged.parent == worker.data / "imports"
        assert staged.read_bytes() == archive.read_bytes()
        assert staged.stat().st_mode & 0o777 == 0o400
        assert owners == [(100000, 100000)]
        raise DeploymentError("Native import failed")
    assert not staged.exists()
    assert archive.read_bytes() == b"verified image bytes"
    assert archive.stat().st_mode & 0o777 == 0o600


def test_native_import_rejects_a_writable_shared_staging_directory(deployment, tmp_path):
    worker, _ = deployment
    imports = worker.data / "imports"
    imports.mkdir(mode=0o777)
    imports.chmod(0o777)
    archive = tmp_path / "image.tar"
    archive.write_bytes(b"image")
    with pytest.raises(DeploymentError), worker.import_archive(archive):
        raise AssertionError("Untrusted staging must never reach native import")


@pytest.mark.parametrize(
    "changed",
    [{"generation": 1}, {"runtime_id": 999}, {"previous": {"id": 199}}, {"installation": "other"}],
)
def test_initial_resume_cannot_reinitialize_a_different_or_updated_deployment(deployment, changed):
    from deploy.proxmox.install import validate_resume

    worker, _ = deployment
    saved = worker.cfg | {"generation": 0}
    validate_resume(saved, worker.cfg)
    with pytest.raises(DeploymentError):
        validate_resume(saved | changed, worker.cfg)
