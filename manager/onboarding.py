"""First-run setup and session-owned Git authorization offers."""

import secrets
import time

from flask import abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import login_required

from manager.control import ControlError, read_document
from manager.forge import LIFETIME, PROVIDERS, private_offer
from manager.links import public_web_url


def register(app, connect, controller, current_status, active_operation, render_overview):
    def stage():
        with connect() as db:
            row = db.execute("SELECT value FROM preferences WHERE name='setup_stage'").fetchone()
        return row[0] if row else "git"

    def wizard(step):
        return render_template(
            "welcome.html",
            step=step,
            guided=True,
            providers=PROVIDERS,
            status=current_status(),
            orca_url=public_web_url(app.config["ORCA_WEB_URL"]),
        )

    @app.get("/")
    @login_required
    def home():
        step = stage()
        return render_overview() if step == "complete" else wizard(step)

    @app.get("/welcome")
    @login_required
    def welcome():
        step = request.args.get("step") or stage()
        return wizard("launch" if step == "launch" else "git")

    @app.post("/welcome/continue")
    @login_required
    def continue_setup():
        with connect() as db:
            db.execute("""INSERT INTO preferences VALUES('setup_stage','launch')
                          ON CONFLICT(name) DO UPDATE SET value='launch' WHERE value!='complete'""")
        return redirect(url_for("welcome", step="launch"), code=303)

    @app.post("/welcome/finish")
    @login_required
    def finish_setup():
        with connect() as db:
            db.execute("INSERT OR REPLACE INTO preferences VALUES('setup_stage','complete')")
        return redirect(url_for("overview"), code=303)

    def provider_page(provider, job_id=None, error=None, status_code=200):
        return render_template(
            "git-provider.html",
            provider=provider,
            spec=PROVIDERS[provider],
            guided=request.args.get("setup") == "1" or stage() != "complete",
            status=current_status(),
            job_id=job_id,
            error=error,
        ), status_code

    def owner():
        return session.setdefault("pairing_owner", secrets.token_hex(32))

    @app.get("/git/<provider>")
    @login_required
    def git_provider(provider):
        if provider not in PROVIDERS:
            abort(404)
        with connect() as db:
            recent = db.execute(
                """SELECT id FROM git_attempts WHERE provider=? AND owner=? AND created>?
                                   ORDER BY created DESC LIMIT 1""",
                (provider, owner(), time.time() - LIFETIME),
            ).fetchone()
        return provider_page(provider, recent[0] if recent else None)

    @app.post("/git/<provider>/start")
    @login_required
    def start_git(provider):
        if provider not in PROVIDERS:
            abort(404)
        if controller.directory is None:
            return provider_page(
                provider, error="The deployment worker is unavailable.", status_code=503
            )
        if active_operation():
            return provider_page(
                provider, error="Wait for the current server update to finish.", status_code=409
            )
        current_owner = owner()
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM git_attempts WHERE created<=?", (time.time() - LIFETIME,))
            recent = db.execute(
                """SELECT id, owner FROM git_attempts WHERE provider=?
                                   ORDER BY created DESC LIMIT 1""",
                (provider,),
            ).fetchone()
            if recent and controller.result(recent[0]).get("state") in {"queued", "running"}:
                if recent[1] != current_owner:
                    return provider_page(
                        provider,
                        error="A sign-in is already open in another browser. Finish it there or wait for its code to expire.",
                        status_code=409,
                    )
            else:
                try:
                    job = controller.submit(PROVIDERS[provider]["action"])
                except (ControlError, OSError) as exc:
                    return provider_page(provider, error=str(exc), status_code=503)
                db.execute(
                    "INSERT INTO git_attempts VALUES(?,?,?,?)",
                    (job["id"], provider, current_owner, time.time()),
                )
        return redirect(
            url_for(
                "git_provider",
                provider=provider,
                setup="1" if request.args.get("setup") == "1" else None,
            ),
            code=303,
        )

    @app.get("/api/git/<provider>/<job_id>")
    @login_required
    def git_progress(provider, job_id):
        if provider not in PROVIDERS:
            abort(404)
        with connect() as db:
            row = db.execute(
                "SELECT created FROM git_attempts WHERE id=? AND provider=? AND owner=?",
                (job_id, provider, session.get("pairing_owner", "")),
            ).fetchone()
        if not row:
            abort(404)
        if time.time() - row[0] >= LIFETIME:
            return jsonify(state="expired")
        if controller.directory is None:
            return jsonify(state="unavailable")
        result = controller.result(job_id)
        if result.get("state") in {"failed", "blocked", "interrupted"}:
            return jsonify(state="failed")
        snapshot = controller.snapshot()
        if not snapshot["controller"]["available"]:
            return jsonify(state="unavailable")
        try:
            saved = read_document(controller.directory / "pairings" / (job_id + ".json"))
        except ControlError:
            return jsonify(state="expired" if result.get("state") == "completed" else "starting")
        try:
            return jsonify(
                private_offer(
                    saved, provider, job_id, snapshot.get("deployment", {}).get("generation")
                )
            )
        except ValueError:
            return jsonify(state="expired")
