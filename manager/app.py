import hashlib
import os
import secrets
import shutil
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import click
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from manager.control import (
    TERMINAL_STATES,
    ControlError,
    Controller,
    atomic_document,
    read_document,
)
from manager.links import public_web_url
from manager.releases import ReleaseError, list_releases, upgrades_only

STEPS = [
    ("server", "Server", "Inspect the native runtime and persistent data."),
    ("providers", "Agent providers", "Set up accounts with Orca and the provider's native login."),
    ("github", "GitHub", "Optional repository, push and pull request access."),
    ("desktop", "Mac desktop", "Pair through Orca and inspect the current connection."),
    ("mobile", "Mobile app", "Use Orca's native pairing over your LAN or VPN."),
    ("mcp", "Community MCP bridge", "Use the existing bridge for external coordinators."),
    ("tunnel", "OpenAI Secure MCP Tunnel", "Connect the selected OpenAI tunnel to the bridge."),
]


class Admin(UserMixin):
    def __init__(self, fingerprint):
        self.id = hashlib.sha256(fingerprint.encode()).hexdigest()


def private_file(path, content):
    """Create once, without replacing existing state or following existing symlinks."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "w") as stream:
        stream.write(content)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        STATE_DIR=os.environ.get("OSM_STATE_DIR", "state/manager"),
        ORCA_INTERNAL_URL=os.environ.get("ORCA_INTERNAL_URL", "http://runtime:6768"),
        ORCA_WEB_URL=os.environ.get("ORCA_WEB_URL", ""),
        CONTROL_DIR=os.environ.get("OSM_CONTROL_DIR"),
        ARCHITECTURE=os.environ.get("OSM_ARCHITECTURE", "amd64"),
        SESSION_COOKIE_NAME="__Host-osm",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUSTED_HOSTS=[
            h for h in os.environ.get("OSM_TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if h
        ],
    )
    if test_config:
        app.config.update(test_config)
    state = Path(app.config["STATE_DIR"])
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_file(state / "session.key", secrets.token_hex(32))
    app.config["SECRET_KEY"] = (state / "session.key").read_text().strip()
    with sqlite3.connect(state / "manager.sqlite3") as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), hash TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS steps (name TEXT PRIMARY KEY, skipped INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, created REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS preferences (name TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY CHECK(id=1),
            failures INTEGER NOT NULL, until REAL NOT NULL);
        """)
        if not db.execute("SELECT 1 FROM admin").fetchone():
            private_file(state / "bootstrap.token", secrets.token_urlsafe(32))
    os.chmod(state / "manager.sqlite3", 0o600)
    # Only Caddy may reach this socket in Compose. Never publish manager:8080.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    CSRFProtect(app)
    login = LoginManager(app)
    login.login_view = "sign_in"
    login.session_protection = "strong"

    def connect():
        return sqlite3.connect(state / "manager.sqlite3", timeout=10)

    def admin_hash():
        with connect() as db:
            row = db.execute("SELECT hash FROM admin WHERE id=1").fetchone()
        return row[0] if row else None

    @login.user_loader
    def load_user(user_id):
        hashed = admin_hash()
        # A password reset invalidates existing signed sessions.
        if hashed and secrets.compare_digest(user_id, Admin(hashed).id):
            return Admin(hashed)
        return None

    @app.before_request
    def require_https():
        if request.path != "/healthz" and not request.is_secure:
            abort(400, "HTTPS is required. Use the HTTPS address.")

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    def blocked():
        with connect() as db:
            row = db.execute("SELECT until FROM attempts WHERE id=1").fetchone()
        return row and row[0] > time.time()

    def failed():
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT failures,until FROM attempts WHERE id=1").fetchone()
            count = row[0] + 1 if row and (row[1] == 0 or row[1] > time.time()) else 1
            until = time.time() + 300 if count >= 5 else 0
            db.execute("INSERT OR REPLACE INTO attempts VALUES(1,?,?)", (count, until))

    @app.get("/healthz")
    def health():
        with connect() as db:
            db.execute("SELECT 1").fetchone()
        return jsonify(status="ok", service="orca-server-manager")

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if admin_hash():
            return redirect(url_for("sign_in"))
        error = None
        if request.method == "POST":
            if blocked():
                abort(429)
            token_path = state / "bootstrap.token"
            supplied = request.form.get("token", "")
            valid = token_path.exists() and secrets.compare_digest(supplied, token_path.read_text())
            password = request.form.get("password", "")
            if valid and 8 <= len(password) <= 256:
                hashed = generate_password_hash(password)
                with connect() as db:
                    # Atomic claim: concurrent bootstrap requests cannot replace an administrator.
                    result = db.execute("INSERT OR IGNORE INTO admin VALUES(1,?)", (hashed,))
                    if result.rowcount != 1:
                        abort(409)
                    db.execute("DELETE FROM attempts")
                token_path.unlink(missing_ok=True)
                session.clear()
                login_user(Admin(hashed))
                session.permanent = True
                return redirect(url_for("overview"))
            failed()
            error = "Setup failed. Check your code and password (8–256 characters)."
        return render_template("auth.html", bootstrap=True, error=error)

    @app.route("/login", methods=["GET", "POST"])
    def sign_in():
        hashed = admin_hash()
        if not hashed:
            return redirect(url_for("setup"))
        error = None
        if request.method == "POST":
            if blocked():
                abort(429)
            if check_password_hash(hashed, request.form.get("password", "")):
                session.clear()
                login_user(Admin(hashed))
                session.permanent = True
                with connect() as db:
                    db.execute("DELETE FROM attempts")
                return redirect(url_for("overview"))
            failed()
            error = "Sign-in failed."
        return render_template("auth.html", bootstrap=False, error=error)

    @app.post("/logout")
    @login_required
    def sign_out():
        logout_user()
        session.clear()
        return redirect(url_for("sign_in"))

    controller = Controller(app.config["CONTROL_DIR"])

    def current_status():
        snapshot = controller.snapshot()
        connected = snapshot["controller"]["available"]
        raw_runtime = snapshot.get("runtime", {}) if connected else {}
        reachable = raw_runtime.get("reachable") is True
        runtime = {
            "state": "reachable" if reachable else "error" if connected else "unknown",
            "label": "Runtime reachable"
            if reachable
            else "Runtime not reachable"
            if connected
            else "Not verified",
            "detail": "Native Orca RPC responded."
            if reachable
            else "Inspect the runtime or use the saved rollback."
            if connected
            else snapshot["controller"]["detail"],
            "version": str(raw_runtime.get("version") or "Unknown")[:80],
            "active_terminals": raw_runtime.get("active_terminals"),
            "web_url": public_web_url(raw_runtime.get("web_url")),
        }
        integrations = {}
        for key, _, _ in STEPS[1:]:
            result = snapshot.get("integrations", {}).get(key, {}) if connected else {}
            integrations[key] = {
                "state": result.get("state")
                if result.get("state") in {"ready", "partial", "offline", "error", "unknown"}
                else "unknown",
                "label": str(result.get("label") or "Not verified")[:100],
                "detail": str(
                    result.get("detail") or "No current technical observation is available."
                )[:500],
                "checks": [
                    {
                        "name": str(row.get("name", ""))[:100],
                        "value": str(row.get("value", ""))[:200],
                    }
                    for row in result.get("checks", [])[:12]
                    if isinstance(row, dict)
                ],
            }
        deployment = snapshot.get("deployment", {}) if connected else {}
        return {
            "manager": "ok",
            "controller": snapshot["controller"],
            "runtime": runtime,
            "integrations": integrations,
            "observed_at": snapshot.get("observed_at"),
            "deployment": {
                "version": str(deployment.get("version") or runtime["version"])[:80],
                "previous_version": str(deployment.get("previous_version") or "")[:80],
                "backup_at": str(deployment.get("backup_at") or "")[:80],
                "backend": "Proxmox OCI",
                "generation": deployment.get("generation", 0),
                "runtime_id": deployment.get("runtime_id"),
            },
        }

    def active_operation():
        with connect() as db:
            row = db.execute(
                "SELECT value FROM preferences WHERE name='active_operation'"
            ).fetchone()
        if not row:
            return None
        try:
            result = controller.result(row[0])
        except ControlError:
            return None
        return result if result.get("state") not in TERMINAL_STATES else None

    @app.context_processor
    def common_values():
        return {"active_operation": active_operation(), "steps": STEPS}

    @app.get("/")
    @login_required
    def overview():
        snapshot = current_status()
        return render_template(
            "overview.html",
            status=snapshot,
            free_gb=round(shutil.disk_usage(state).free / 2**30, 1),
            orca_url=public_web_url(app.config["ORCA_WEB_URL"])
            or ("/orca/web-index.html" if snapshot["runtime"]["web_url"] else ""),
        )

    @app.get("/connections")
    @login_required
    def connections():
        return render_template("connections.html", status=current_status())

    @app.get("/api/status")
    @login_required
    def status():
        return jsonify(current_status())

    @app.get("/connections/<name>")
    @login_required
    def connection(name):
        if name not in {key for key, _, _ in STEPS}:
            abort(404)
        title = next(title for key, title, _ in STEPS if key == name)
        snapshot = current_status()
        return render_template(
            "connection.html",
            name=name,
            title=title,
            status=snapshot,
            result=snapshot["runtime"] if name == "server" else snapshot["integrations"][name],
        )

    @app.get("/updates")
    @login_required
    def updates():
        try:
            page = int(request.args.get("page", "1"))
            if not 1 <= page <= 100:
                raise ValueError
        except ValueError:
            abort(400)
        cache = state / f"releases-{page}.json"
        release_error = None
        releases = {"releases": [], "has_more": False, "page": page}
        try:
            saved = read_document(cache)
        except ControlError:
            saved = {}
        try:
            if time.time() - saved.get("fetched_at", 0) < 600:
                releases = saved["data"]
            else:
                releases = list_releases(page, app.config["ARCHITECTURE"])
                atomic_document(cache, {"fetched_at": time.time(), "data": releases})
        except (ReleaseError, OSError) as error:
            release_error = str(error)
            releases = saved.get("data", releases)
        snapshot = current_status()
        try:
            releases = upgrades_only(releases, snapshot["deployment"]["version"])
        except ReleaseError:
            releases = {"releases": [], "has_more": False, "page": page}
            release_error = "The installed version is not known yet. Refresh the runtime status before choosing an upgrade."
        return render_template(
            "updates.html", status=snapshot, releases=releases, release_error=release_error
        )

    def queue_operation(action, version=None, restore_data=False):
        # One active operation across browsers; the worker independently fences deployment changes.
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT value FROM preferences WHERE name='active_operation'"
            ).fetchone()
            try:
                if row and controller.result(row[0]).get("state") not in TERMINAL_STATES:
                    return redirect(url_for("operation", job_id=row[0]))
                job = controller.submit(action, version, restore_data)
            except ReleaseError as error:
                return render_template("operation-error.html", error=str(error)), 400
            except (ControlError, OSError) as error:
                return render_template("operation-error.html", error=str(error)), 503
            db.execute("INSERT INTO operations VALUES (?,?)", (job["id"], time.time()))
            db.execute(
                "INSERT OR REPLACE INTO preferences VALUES('active_operation',?)", (job["id"],)
            )
        return redirect(url_for("operation", job_id=job["id"]))

    @app.post("/actions/refresh")
    @login_required
    def refresh():
        return queue_operation("refresh")

    @app.post("/actions/update")
    @login_required
    def update():
        if request.form.get("work_stopped") != "1":
            abort(400, "Stop current work in Orca before changing its container.")
        return queue_operation("update", request.form.get("version", ""))

    @app.post("/actions/rollback")
    @login_required
    def rollback():
        if request.form.get("work_stopped") != "1":
            abort(400, "Stop current work in Orca before changing its container.")
        mode = request.form.get("mode")
        if mode not in {"software", "data"}:
            abort(400)
        return queue_operation("rollback", restore_data=mode == "data")

    @app.get("/operations/<job_id>")
    @login_required
    def operation(job_id):
        with connect() as db:
            found = db.execute("SELECT 1 FROM operations WHERE id=?", (job_id,)).fetchone()
        if not found:
            abort(404)
        try:
            result = controller.result(job_id)
        except ControlError as error:
            return render_template("operation-error.html", error=str(error)), 503
        return render_template(
            "operation.html",
            job=result,
            refresh_seconds=3 if result.get("state") not in TERMINAL_STATES else None,
        )

    @app.post("/steps/<name>/skip")
    @login_required
    def skip(name):
        if name not in {key for key, _, _ in STEPS[1:]}:
            abort(404)
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO steps VALUES(?,?)",
                (name, int(request.form.get("skip") == "1")),
            )
        return redirect(url_for("overview"))

    @app.cli.command("reset-admin")
    @click.password_option(confirmation_prompt=True)
    def reset_admin(password):
        """Reset the administrator from an authorized local terminal."""
        if not 8 <= len(password) <= 256:
            raise click.ClickException("Use 8–256 characters.")
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO admin VALUES(1,?)", (generate_password_hash(password),)
            )
            db.execute("DELETE FROM attempts")
        (state / "bootstrap.token").unlink(missing_ok=True)
        click.echo("Administrator updated; previous sessions invalidated.")

    return app
