"""Copy the one-time setup code into the assigned manager's Proxmox Notes."""

import json
import os
import re
import stat
import subprocess
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import unquote


class SetupNotesError(ValueError):
    pass


UPDATE_DESCRIPTION = """
local $/;
my $p = decode_json(<STDIN>);
PVE::LXC::Config->lock_config($p->{id}, sub {
    my $c = PVE::LXC::Config->load_config($p->{id});
    die "Manager Notes changed; retry on the next worker pass.\n"
        if ($c->{description} // '') ne $p->{expected};
    $c->{description} = $p->{description};
    PVE::LXC::Config->write_config($p->{id}, $c);
});
"""


def read_setup_code(data):
    """Read only a bounded private token; never follow guest-controlled links."""
    with ExitStack() as stack:
        parent = None
        for path, owner in [(Path(data) / "manager", 100000), ("manager", 101000)]:
            try:
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            except FileNotFoundError:
                return None
            except OSError:
                raise SetupNotesError(
                    "Cannot inspect the manager setup directory safely."
                ) from None
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if info.st_uid != owner or info.st_mode & 0o022:
                raise SetupNotesError("Unexpected manager setup directory ownership or mode.")
            parent = fd
        try:
            fd = os.open(
                "bootstrap.token", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        except FileNotFoundError:
            return None
        except OSError:
            raise SetupNotesError("Cannot read the manager setup code safely.") from None
        stack.callback(os.close, fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 101000
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or info.st_size > 128
        ):
            raise SetupNotesError("Unexpected manager setup code ownership, mode or file type.")
        value = os.read(fd, 129)
        if not re.fullmatch(rb"[A-Za-z0-9_-]{32,128}", value):
            raise SetupNotesError("Unexpected manager setup code format.")
        return value.decode("ascii")


def setup_description(existing, installation, code):
    marker = f"OSM:{installation}:manager"
    if marker not in existing.splitlines():
        raise SetupNotesError("Refusing to change Notes of an unrelated container.")
    start = f"<!-- OSM:{installation}:setup:start -->"
    end = f"<!-- OSM:{installation}:setup:end -->"
    if (
        existing.count(start) != existing.count(end)
        or existing.count(start) > 1
        or (start in existing and existing.index(start) > existing.index(end))
    ):
        raise SetupNotesError("Inspect the incomplete managed setup Notes before retrying.")
    if start in existing:
        before, managed = existing.split(start, 1)
        _, after = managed.split(end, 1)
        existing = before.rstrip() + after
    body = [
        start,
        "## Orca Server Manager",
        "",
        "Open this container's HTTPS address to access the manager.",
        "",
    ]
    if code:
        body += [
            "**First-time setup code**",
            "",
            f"`{code}`",
            "",
            "Copy this code into the setup page and choose your administrator password.",
            "The code becomes invalid after setup. The host worker removes this copy on its next pass.",
        ]
    else:
        body += [
            "No setup code is currently available. If you have created your administrator,",
            "sign in with your password. If the manager is still starting, refresh these Notes shortly.",
        ]
    body += [end]
    return existing.rstrip() + "\n\n" + "\n".join(body) + "\n"


def sync_setup_notes(cfg):
    def command(args, **kwargs):
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=20, check=False, **kwargs
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SetupNotesError("Could not synchronize manager setup Notes.") from None
        if result.returncode:
            # Native stderr and payloads can contain private Notes. Never log either.
            raise SetupNotesError("Could not synchronize manager setup Notes.")
        return result.stdout

    raw = command(["pct", "config", str(cfg["manager_id"])])
    existing = unquote(
        next(
            (
                line.removeprefix("description: ")
                for line in raw.splitlines()
                if line.startswith("description: ")
            ),
            "",
        )
    )
    code = read_setup_code(cfg["data"])
    description = setup_description(existing, cfg["installation"], code)
    if description == existing:
        return
    # The token stays on this host: JSON goes through stdin, never argv or logs.
    command(
        ["perl", "-MPVE::LXC::Config", "-MJSON::PP", "-e", UPDATE_DESCRIPTION],
        input=json.dumps(
            {"id": cfg["manager_id"], "expected": existing, "description": description}
        ),
    )
