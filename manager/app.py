import hashlib
import os
import secrets
import shutil
import sqlite3
import time
from datetime import timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import click
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

STEPS = [
    ("server", "Server prüfen", "Runtime, Erreichbarkeit und persistente Daten prüfen."),
    ("providers", "Agent-Provider", "Codex und OpenCode mit ihren nativen Logins verbinden."),
    ("github", "GitHub verbinden", "Zugriff auf geco91/orca-server-manager prüfen."),
    ("desktop", "Mac-Desktop", "Einen offiziellen Orca-Pairing-Link am Mac verwenden."),
    ("mobile", "Mobile-App", "Mobiles Pairing über Orca im LAN oder VPN einrichten."),
    ("mcp", "MCP Bridge", "Community-Bridge neben der Runtime betreiben."),
    ("tunnel", "Secure MCP Tunnel", "Vorhandenen authentifizierten Tunnel anbinden."),
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
            abort(400, "HTTPS ist erforderlich. Bitte den HTTPS-Zugang verwenden.")

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
            if valid and 14 <= len(password) <= 256:
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
            error = "Einrichtung fehlgeschlagen. Token und Passwort (14–256 Zeichen) prüfen."
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
            error = "Anmeldung fehlgeschlagen."
        return render_template("auth.html", bootstrap=False, error=error)

    @app.post("/logout")
    @login_required
    def sign_out():
        logout_user()
        session.clear()
        return redirect(url_for("sign_in"))

    def runtime_status():
        # Fixed deployment setting, never a browser-controlled URL. No proxy or redirects:
        # this request stays in the private Compose network and sends no credentials.
        from urllib.request import HTTPRedirectHandler

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(
                app.config["ORCA_INTERNAL_URL"].rstrip("/") + "/", timeout=2
            ) as response:
                content = response.read(512 * 1024)
                if response.status == 200 and b"<html" in content.lower():
                    return {
                        "state": "reachable",
                        "label": "Web-Endpunkt erreichbar",
                        "detail": "Orca liefert die WebUI. Client-Authentifizierung separat prüfen.",
                    }
            return {
                "state": "error",
                "label": "Unerwartete Antwort",
                "detail": "Runtime-Logs prüfen.",
            }
        except (OSError, URLError, ValueError):
            return {
                "state": "error",
                "label": "Nicht erreichbar",
                "detail": "Runtime starten und Container-Healthcheck sowie Logs prüfen.",
            }

    @app.get("/")
    @login_required
    def overview():
        with connect() as db:
            skipped = {
                name for name, value in db.execute("SELECT name,skipped FROM steps") if value
            }
        disk = shutil.disk_usage(state)
        return render_template(
            "overview.html",
            steps=STEPS,
            skipped=skipped,
            runtime=runtime_status(),
            free_gb=round(disk.free / 2**30, 1),
            orca_url=app.config["ORCA_WEB_URL"],
        )

    @app.get("/api/status")
    @login_required
    def status():
        return jsonify(
            manager="ok",
            runtime=runtime_status(),
            integrations={key: "unverified" for key, _, _ in STEPS[1:]},
        )

    @app.get("/connections/<name>")
    @login_required
    def connection(name):
        if name not in {key for key, _, _ in STEPS}:
            abort(404)
        title = next(title for key, title, _ in STEPS if key == name)
        return render_template("connection.html", name=name, title=title)

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
        if not 14 <= len(password) <= 256:
            raise click.ClickException("Use 14–256 characters.")
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO admin VALUES(1,?)", (generate_password_hash(password),)
            )
            db.execute("DELETE FROM attempts")
        (state / "bootstrap.token").unlink(missing_ok=True)
        click.echo("Administrator updated; previous sessions invalidated.")

    return app
